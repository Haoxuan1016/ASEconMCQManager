from __future__ import annotations

import contextlib
import io
import json
import re
import urllib.request
from pathlib import Path

from pypdf import PdfReader

import generate_question_data as qdata


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "web"

PAPER_TO_MS = {
    "qp-202305-econimics-p12.pdf": ("9708_s23_ms_12", "https://pastpapers.co/caie/A-Level/Economics-9708/2023-May-June/9708_s23_ms_12.pdf"),
    "qp-202310-econimics-p12.pdf": ("9708_w23_ms_12", "https://pastpapers.co/caie/A-Level/Economics-9708/2023-Oct-Nov/9708_w23_ms_12.pdf"),
    "qp-202403-economics-p12.pdf": ("9708_m24_ms_12", "https://pastpapers.co/caie/A-Level/Economics-9708/2024-March/9708_m24_ms_12.pdf"),
    "qp-202406-economics-p11.pdf": ("9708_s24_ms_11", "https://xtrapapers.co/papers/caie/as-and-a-level/economics-9708/2024-may-june/9708_s24_ms_11.pdf/raw"),
    "qp-202406-economics-p13.pdf": ("9708_s24_ms_13", "https://xtrapapers.co/papers/caie/as-and-a-level/economics-9708/2024-may-june/9708_s24_ms_13.pdf/raw"),
    "qp-202410-economics-p11.pdf": ("9708_w24_ms_11", "https://pastpapers.co/caie/A-Level/Economics-9708/2024-Oct-Nov/9708_w24_ms_11.pdf"),
    "qp-202410-economics-p12.pdf": ("9708_w24_ms_12", "https://pastpapers.co/caie/A-Level/Economics-9708/2024-Oct-Nov/9708_w24_ms_12.pdf"),
    "qp-202410-economics-p13.pdf": ("9708_w24_ms_13", "https://pastpapers.co/caie/A-Level/Economics-9708/2024-Oct-Nov/9708_w24_ms_13.pdf"),
    "qp-202503-economics-p12.pdf": ("9708_m25_ms_12", "https://pastpapers.co/caie/A-Level/Economics-9708/2025-March/9708_m25_ms_12.pdf"),
    "qp-202505-economics-p11.pdf": ("9708_s25_ms_11", "https://pastpapers.co/caie/A-Level/Economics-9708/2025-May-June/9708_s25_ms_11.pdf"),
    "qp-202505-economics-p12.pdf": ("9708_s25_ms_12", "https://pastpapers.co/caie/A-Level/Economics-9708/2025-May-June/9708_s25_ms_12.pdf"),
    "qp-202505-economics-p13.pdf": ("9708_s25_ms_13", "https://pastpapers.co/caie/A-Level/Economics-9708/2025-May-June/9708_s25_ms_13.pdf"),
    "qp-202505-economics-p14.pdf": ("9708_s25_ms_14", "https://pastpapers.co/caie/A-Level/Economics-9708/2025-May-June/9708_s25_ms_14.pdf"),
    "qp-202510-economics-p11.pdf": ("9708_w25_ms_11", "https://pastpapers.co/caie/A-Level/Economics-9708/2025-Oct-Nov/9708_w25_ms_11.pdf"),
    "qp-202510-economics-p12.pdf": ("9708_w25_ms_12", "https://pastpapers.co/caie/A-Level/Economics-9708/2025-Oct-Nov/9708_w25_ms_12.pdf"),
    "qp-202510-economics-p13.pdf": ("9708_w25_ms_13", "https://pastpapers.co/caie/A-Level/Economics-9708/2025-Oct-Nov/9708_w25_ms_13.pdf"),
    "qp-202510-economics-p14.pdf": ("9708_w25_ms_14", "https://pastpapers.co/caie/A-Level/Economics-9708/2025-Oct-Nov/9708_w25_ms_14.pdf"),
}

TOPIC_LANGUAGE = {
    "basic-economic-ideas": "basic resource-allocation principle",
    "price-system": "demand, supply, elasticity, or surplus relationship",
    "government-micro-intervention": "market-failure or microeconomic intervention effect",
    "macroeconomy": "macroeconomic measurement or aggregate-demand relationship",
    "government-macro-intervention": "macroeconomic policy effect",
    "international-economic-issues": "trade, balance-of-payments, or exchange-rate relationship",
}

COMPACT_PHRASE_REPLACEMENTS = [
    ("Abudgetsurplusbecomesabudgetdeficitinyear3", "A budget surplus becomes a budget deficit in year 3"),
    ("Nationaldebtislikelytobefallingbytheendofyear3", "National debt is likely to be falling by the end of year 3"),
    ("Thecurrentaccountbalanceisinequilibriuminyear2", "The current account balance is in equilibrium in year 2"),
    ("Theeconomyisatfullemploymentequilibriuminyear2", "The economy is at full employment equilibrium in year 2"),
    ("budgetsurplus", "budget surplus"),
    ("budgetdeficit", "budget deficit"),
    ("Nationaldebt", "National debt"),
    ("currentaccount", "current account"),
    ("fullemployment", "full employment"),
    ("equilibriuminyear", "equilibrium in year"),
    ("likelytobe", "likely to be"),
    ("fallingby", "falling by"),
    ("theendofyear", "the end of year"),
]


def download_pdf(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read()
    if not data.startswith(b"%PDF-"):
        raise RuntimeError(f"Downloaded non-PDF content from {url}")
    return data


def extract_answer_key(pdf_bytes: bytes) -> dict[int, str]:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    parts = []
    for page in reader.pages:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            parts.append(page.extract_text() or "")
    text = "\n".join(parts)
    pairs = re.findall(r"(?m)^\s*([1-9]|[12][0-9]|30)\s+([A-D])\s+1\s*$", text)
    answers = {int(number): letter for number, letter in pairs}
    for number in re.findall(r"(?m)^\s*([1-9]|[12][0-9]|30)\s+Question\s+Discounted\s+0\s*$", text):
        answers[int(number)] = "Discounted"
    if len(answers) != 30:
        raise RuntimeError(f"Expected 30 answers, found {len(answers)}")
    return answers


def option_texts(question_text: str) -> dict[str, str]:
    text = re.sub(r"\s+", " ", question_text).strip()
    matches = list(re.finditer(r"(?:^|\s)([ABCD])\s+", text))
    options: dict[str, str] = {}
    for index, match in enumerate(matches):
        label = match.group(1)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        body = re.sub(r"\s*©UCLES.*$", "", body).strip()
        body = re.sub(r"\s*Permission to reproduce.*$", "", body).strip()
        if label in "ABCD" and body:
            options[label] = body
    return {label: options.get(label, "") for label in "ABCD"}


def compact_option(option: str) -> str:
    option = option.strip()
    if not option:
        return "this option"
    if " " not in option and len(option) > 36 and not re.fullmatch(r"[$£€]?\d[\d,.]*(?:\.\d+)?(?:%|bn|m)?", option, re.IGNORECASE):
        repaired = option
        for before, after in COMPACT_PHRASE_REPLACEMENTS:
            repaired = repaired.replace(before, after)
        repaired = re.sub(r"([a-z])([A-Z])", r"\1 \2", repaired)
        repaired = re.sub(r"(year)(\d)", r"\1 \2", repaired)
        repaired = re.sub(r"\s+", " ", repaired).strip()
        if repaired != option:
            return repaired
    if len(option) > 90:
        return option[:87].rstrip() + "..."
    return option


def norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def has_any(text: str, phrases: list[str]) -> bool:
    lower = norm_text(text)
    compact = compact_text(text)
    return any(phrase in lower or phrase.replace(" ", "") in compact for phrase in phrases)


def sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    return text if text[-1] in ".?!" else text + "."


def reasoning_focus(question: dict, question_text: str) -> str:
    cues = [cue for cue in question.get("cues", []) if cue != "Type C table/accounting calculation"]
    if cues:
        return ", ".join(cues[:2])
    return TOPIC_LANGUAGE.get(question["topic"], "the relevant economic relationship")


def question_family(question: dict, question_text: str) -> dict:
    if has_any(question_text, ["budget deficit", "budget surplus", "government spending", "government revenue", "interest rate", "monetary policy", "fiscal policy", "contractionary", "expansionary"]):
        return {
            "name": "macroeconomic policy or budget balance",
            "rule": "Compare government revenue with government spending for the budget position, and classify policy by its effect on aggregate demand: higher taxes, lower spending, and higher interest rates are contractionary.",
            "correct": "The correct option follows the budget arithmetic or policy direction asked for in the stem.",
            "wrong": "This option has the wrong policy direction, confuses a budget surplus with a deficit, or describes an outcome not supported by the data.",
        }
    if question.get("typeC") or has_any(question_text, ["gross national income", "gross domestic product", "national income", "gdp", "gni", "basic prices", "market prices", "income accounts"]):
        return {
            "name": "national income accounting",
            "rule": "Use the national-income identity stated in the question, such as GNI = GDP + net factor income from abroad, GDP at market prices = GDP at basic prices + indirect taxes - subsidies, or injections = withdrawals for equilibrium income.",
            "correct": "The correct option is the only one that uses the named rows in the table with the right add/subtract direction and keeps the units unchanged.",
            "wrong": "This option is inconsistent with the national-income identity, usually because it adds an item that should be subtracted, subtracts an item that should be added, or uses a row that is not part of the requested measure.",
        }
    if has_any(question_text, ["cross elasticity", "income elasticity", "price elasticity of demand", "price elasticity of supply", "ped", "pes"]):
        return {
            "name": "elasticity calculation or interpretation",
            "rule": "Use elasticity = percentage change in quantity divided by percentage change in the relevant price or income, and keep the sign because substitutes, inferior goods, and supply responses have different signs.",
            "correct": "The correct option gives the percentage-change ratio, sign, or curve interpretation that matches the elasticity definition in the stem.",
            "wrong": "This option fails the elasticity test because it uses the wrong denominator, ignores the sign, reverses cause and effect, or treats an elastic response as inelastic.",
        }
    if has_any(question_text, ["exchange rate", "depreciation", "appreciation", "tariff", "quota", "terms of trade", "balance of payments", "current account", "exports", "imports"]):
        return {
            "name": "international trade or exchange-rate analysis",
            "rule": "Apply the trade rule directly: exports minus imports gives a trade balance, terms of trade compare export prices with import prices, and a depreciation makes domestic currency cheaper while an appreciation makes it dearer.",
            "correct": "The correct option follows the direction of the trade balance, exchange-rate movement, or terms-of-trade change implied by the data.",
            "wrong": "This option reverses the currency or trade effect, uses the goods balance when the question asks for a wider balance, or treats a cause as if it were the final outcome.",
        }
    if has_any(question_text, ["inflation", "cpi", "consumer prices index", "real gdp", "real value", "index number", "recession", "unemployment rate", "labour force"]):
        return {
            "name": "macroeconomic data interpretation",
            "rule": "Use the data definition: inflation is a rise in the price level, disinflation is a falling positive inflation rate, real values adjust for inflation, unemployment rate = unemployed / labour force x 100, and a recession needs falling real GDP over the relevant period.",
            "correct": "The correct option applies the macroeconomic definition to the numbers rather than only noticing whether a number is high or low.",
            "wrong": "This option misuses the macro definition, for example by confusing disinflation with deflation, nominal with real values, or population with the labour force.",
        }
    if has_any(question_text, ["comparative advantage", "specialisation", "production possibility", "ppc", "opportunity cost"]):
        return {
            "name": "PPC, opportunity cost, or specialisation",
            "rule": "Compare opportunity costs from the PPC or output data, then allocate specialisation to the producer with the lower opportunity cost rather than the larger absolute output.",
            "correct": "The correct option follows the opportunity-cost comparison and then applies the resulting specialisation or PPC movement.",
            "wrong": "This option is wrong because it relies on absolute output, an inefficient point, or the wrong opportunity-cost trade-off.",
        }
    if has_any(question_text, ["tax", "subsidy", "gini", "inequality", "progressive", "proportional", "regressive", "market failure", "external"]):
        return {
            "name": "government intervention or inequality data",
            "rule": "Apply the intervention rule: taxes and subsidies shift costs or prices, proportional tax keeps the tax rate constant, progressive tax raises the average tax rate, and a higher Gini coefficient means more inequality.",
            "correct": "The correct option matches the policy or inequality definition after comparing the relevant rates, shifts, or coefficients.",
            "wrong": "This option uses the wrong policy effect, compares absolute tax paid instead of tax rate, or reads the inequality measure in the wrong direction.",
        }
    if has_any(question_text, ["consumer surplus", "producer surplus", "area", "diagram", "curve", "equilibrium", "supply curve", "demand curve"]):
        return {
            "name": "diagram or surplus reading",
            "rule": "Read the diagram by matching each labelled point or area to the correct economic meaning: equilibrium is where curves meet, consumer surplus is above price and below demand, and producer surplus is below price and above supply.",
            "correct": "The correct option identifies the labelled movement, point, or area that has the economic meaning asked for in the stem.",
            "wrong": "This option misreads the diagram by choosing the wrong area, treating a movement along a curve as a shift, or confusing the buyer and seller side of the market.",
        }
    return {
        "name": reasoning_focus(question, question_text),
        "rule": f"Apply the relevant {reasoning_focus(question, question_text)} carefully to the exact wording and data in the question.",
        "correct": "The correct option is the one that satisfies all the conditions in the question rather than only one visible clue.",
        "wrong": "This option misses at least one condition in the stem or applies the right concept in the wrong direction.",
    }


def worked_method(question: dict, question_text: str, family: dict) -> str:
    text = norm_text(question_text)
    compact = compact_text(question_text)
    if "grossnationalincome" in compact or "gni" in compact:
        return "For GNI, start with GDP, add factor income earned by residents abroad, and subtract factor income earned domestically by non-residents."
    if "gdpatbasicprices" in compact and "marketprices" in compact:
        return "To move from GDP at basic prices to market prices, add indirect taxes and subtract subsidies."
    if "grossdomesticproductatbasicprices" in compact or ("basicprices" in compact and "marketprices" in compact):
        return "To move from GDP at market prices to basic prices, subtract indirect taxes and add subsidies."
    if "equilibriumrealoutput" in compact:
        return "For equilibrium real output, calculate aggregate demand as C + I + G + X - M and choose the row where this equals real output."
    if "equilibriumlevelofnationalincome" in compact:
        return "For equilibrium national income, compare injections with withdrawals and choose the income level where they are equal."
    if "unemploymentrate" in compact:
        return "The unemployment rate is unemployed people divided by the labour force, multiplied by 100."
    if "open economy" in text or "openeconomy" in compact:
        return "Use Y = C + I + G + X - M and the injections-withdrawals condition to infer the export-import combination."
    if "cross elasticity" in text:
        return "Cross elasticity equals percentage change in demand for the related good divided by percentage change in the other good's price."
    if "income elasticity" in text or "incomeelasticity" in compact:
        return "Income elasticity equals percentage change in quantity demanded divided by percentage change in income, so the sign shows whether the good is normal or inferior."
    if "price elasticity of demand" in text or "ped" in text:
        return "Price elasticity of demand compares the percentage change in quantity demanded with the percentage change in price."
    if "price elasticity of supply" in text or "pes" in text:
        return "Price elasticity of supply compares the percentage change in quantity supplied with the percentage change in price."
    if "consumer surplus" in text and "producer surplus" in text:
        return "Consumer surplus is the area below demand and above price, while producer surplus is the area above supply and below price."
    if "consumer surplus" in text:
        return "Consumer surplus is the difference between what buyers are willing to pay and what they actually pay."
    if "producer surplus" in text:
        return "Producer surplus is the difference between the market price received and the minimum price producers would accept."
    if "terms of trade" in text or "termsoftrade" in compact:
        return "Terms of trade is export price index divided by import price index, multiplied by 100."
    if "balance of payments" in text or "current account" in text:
        return "For balance-of-payments questions, keep goods, services, income, and transfers separate and add only the components requested."
    if "exchange rate" in text or "exchangerate" in compact:
        return "For exchange rates, check which currency is being priced and whether the change is an appreciation or depreciation before judging exports, imports, or prices."
    if "inflation" in text and "disinflation" in text:
        return "Disinflation means the inflation rate is still positive but falling, whereas deflation means the price level is falling."
    if "consumer prices index" in text or "cpi" in text:
        return "For CPI questions, convert nominal values into real values by adjusting for the price index."
    if "real gdp" in text or "index of gdp" in text:
        return "For real GDP index data, compare consecutive quarters and remember that a recession requires a sustained fall in real output."
    if "comparative advantage" in text:
        return "Comparative advantage is based on lower opportunity cost, not lower money cost or higher absolute output."
    if "specialisation" in text or "productionpossibilit" in compact:
        return "For specialisation/PPC questions, calculate what each country gives up to produce one more unit of the other good."
    if "gini" in text:
        return "A higher Gini coefficient means greater income inequality, while a lower Gini coefficient means more equal income distribution."
    if "proportionalincometax" in compact:
        return "A proportional income tax keeps the same average tax rate at each income level, even though the amount paid rises."
    if "progressive" in text and "tax" in text:
        return "A progressive income tax makes the average tax rate rise as income rises."
    if "budget" in text and ("spending" in text or "revenue" in text):
        return "Budget balance equals government revenue minus government spending, so a positive value is a surplus and a negative value is a deficit."
    if "contractionary" in text:
        return "A contractionary policy reduces aggregate demand, usually through higher taxes, lower government spending, or higher interest rates."
    return family["rule"]


def option_numbers(option: str) -> list[float]:
    values = []
    for raw in re.findall(r"[-+]?\d+(?:\.\d+)?", option.replace(",", "")):
        try:
            values.append(float(raw))
        except ValueError:
            pass
    return values


def is_numeric_option(option: str) -> bool:
    stripped = option.strip()
    if not stripped:
        return False
    nums = option_numbers(stripped)
    if re.search(r"[$£€%]", stripped):
        return bool(nums)
    if len(nums) >= 2 and len(re.sub(r"[\d\s.,+\-–$£€%A-Za-z]", "", stripped)) <= 2:
        return True
    return bool(re.fullmatch(r"\s*[$£€]?\s*[-+]?\d[\d\s,.]*(?:\.\d+)?\s*(?:%|bn|m|million|billion)?\s*", stripped, re.IGNORECASE))


def option_specific_reason(option: str, answer_text: str, is_correct: bool) -> str:
    option = compact_option(option)
    answer_text = compact_option(answer_text)
    if is_correct:
        return f"The option '{option}' is the final answer after applying the method, so it is not merely a keyword match."
    if option == "this option":
        return f"Compared with the correct option '{answer_text}', this choice cannot be supported by the data shown."
    option_vals = option_numbers(option)
    answer_vals = option_numbers(answer_text)
    if option_vals and answer_vals and is_numeric_option(option) and is_numeric_option(answer_text):
        if len(option_vals) == 1 and len(answer_vals) == 1:
            if option_vals[0] < answer_vals[0]:
                return f"The value in this option is below the required result '{answer_text}', so it usually comes from omitting an addition or subtracting too much."
            if option_vals[0] > answer_vals[0]:
                return f"The value in this option is above the required result '{answer_text}', so it usually comes from adding too much or failing to subtract the relevant item."
        return f"The numerical pattern in '{option}' does not match the correct pattern '{answer_text}', so at least one row, percentage change, or sign has been used incorrectly."
    return f"Compared with the correct option '{answer_text}', the statement '{option}' applies the concept in the wrong direction or to the wrong part of the question."


def explanation_for(question: dict, question_text: str, answer: str) -> dict:
    options = option_texts(question_text)
    family = question_family(question, question_text)
    method = worked_method(question, question_text, family)
    correct_text = compact_option(options.get(answer, ""))
    conclusion = f"The answer is {answer}: {correct_text} follows from {family['name']}."
    choice_explanations = {}
    for label in "ABCD":
        option = compact_option(options.get(label, ""))
        if label == answer:
            sentences = [
                sentence(f"{label} is correct because the required method gives '{option}'"),
                sentence(method),
                sentence(family["correct"]),
                sentence(option_specific_reason(options.get(label, ""), options.get(answer, ""), True)),
            ]
        else:
            sentences = [
                sentence(f"{label} is not correct because it gives '{option}' instead of the required answer '{correct_text}'"),
                sentence(method),
                sentence(family["wrong"]),
                sentence(option_specific_reason(options.get(label, ""), options.get(answer, ""), False)),
            ]
        choice_explanations[label] = sentences
    return {
        "answer": answer,
        "conclusion": conclusion,
        "choices": choice_explanations,
    }


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    bank = json.loads((OUT_DIR / "questions.json").read_text(encoding="utf-8"))
    hard_by_id = {question["id"]: question for question in bank["questions"] if question["difficulty"] == "Hard"}

    answer_keys = {}
    for file_name, (code, url) in PAPER_TO_MS.items():
        answer_keys[file_name] = {
            "code": code,
            "url": url,
            "answers": extract_answer_key(download_pdf(url)),
        }

    explanations = {}
    for pdf_path in sorted(ROOT.glob("*.pdf")):
        extracted = qdata.extract_questions(pdf_path)
        for question_text_item in extracted:
            qid = f"{pdf_path.stem}-q{question_text_item['number']:02d}"
            if qid not in hard_by_id:
                continue
            answer = answer_keys[pdf_path.name]["answers"][question_text_item["number"]]
            explanations[qid] = explanation_for(hard_by_id[qid], question_text_item["text"], answer)

    output = {
        "schemaVersion": 1,
        "generatedFrom": "Hard-question answer letters are extracted from matching 9708 Paper 1 mark schemes; explanations are concise generated study notes.",
        "hardQuestionCount": len(hard_by_id),
        "explanationCount": len(explanations),
        "sources": [
            {"file": file_name, "markSchemeCode": data["code"], "url": data["url"]}
            for file_name, data in sorted(answer_keys.items())
        ],
        "explanations": explanations,
    }
    if len(explanations) != len(hard_by_id):
        raise RuntimeError(f"Expected {len(hard_by_id)} explanations, wrote {len(explanations)}")

    json_text = json.dumps(output, indent=2, ensure_ascii=False)
    (OUT_DIR / "hard-explanations.json").write_text(json_text + "\n", encoding="utf-8")
    (OUT_DIR / "hard-explanations.js").write_text(
        "window.HARD_EXPLANATIONS = " + json_text + ";\n", encoding="utf-8"
    )
    print(f"Wrote {len(explanations)} hard-question explanations.")


if __name__ == "__main__":
    main()
