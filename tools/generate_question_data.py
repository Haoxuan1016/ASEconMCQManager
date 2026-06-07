from __future__ import annotations

import contextlib
import io
import json
import logging
import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "web"
logging.getLogger("pypdf").setLevel(logging.ERROR)

TOPICS = [
    {
        "id": "basic-economic-ideas",
        "name": "Basic Economic Ideas and Resource Allocation",
        "description": "Scarcity, opportunity cost, economic methodology, factors of production, economic systems, production possibility curves, and classification of goods.",
    },
    {
        "id": "price-system",
        "name": "The Price System and the Microeconomy",
        "description": "Demand and supply, price/income/cross elasticities, market equilibrium, and consumer and producer surplus.",
    },
    {
        "id": "government-micro-intervention",
        "name": "Government Microeconomic Intervention",
        "description": "Market failure, externalities, taxes, subsidies, price controls, direct provision, and addressing inequality.",
    },
    {
        "id": "macroeconomy",
        "name": "The Macroeconomy",
        "description": "National income statistics, circular flow of income, aggregate demand and supply, economic growth, unemployment, and inflation.",
    },
    {
        "id": "government-macro-intervention",
        "name": "Government Macroeconomic Intervention",
        "description": "Macroeconomic objectives, fiscal policy, monetary policy, and supply-side policy.",
    },
    {
        "id": "international-economic-issues",
        "name": "International Economic Issues",
        "description": "International trade, protectionism, balance of payments, exchange rates, and policies to correct imbalances.",
    },
]

TOPIC_KEYWORDS = {
    "basic-economic-ideas": [
        "scarcity",
        "scarce",
        "opportunity cost",
        "production possibility",
        "ppc",
        "factor of production",
        "land",
        "labour",
        "capital",
        "enterprise",
        "entrepreneur",
        "division of labour",
        "specialisation",
        "market economy",
        "planned economy",
        "mixed economy",
        "economic system",
        "free good",
        "private good",
        "public good",
        "classification of goods",
    ],
    "price-system": [
        "demand",
        "supply",
        "market equilibrium",
        "equilibrium price",
        "equilibrium quantity",
        "price elasticity",
        "income elasticity",
        "cross elasticity",
        "elasticity",
        "consumer surplus",
        "producer surplus",
        "substitute",
        "complement",
        "shortage",
        "excess supply",
        "excess demand",
        "rationing function",
        "incentivising function",
    ],
    "government-micro-intervention": [
        "market failure",
        "externality",
        "external cost",
        "external benefit",
        "social cost",
        "social benefit",
        "private cost",
        "private benefit",
        "tax",
        "subsidy",
        "maximum price",
        "minimum price",
        "price ceiling",
        "price floor",
        "direct provision",
        "indirect tax",
        "specific tax",
        "ad valorem",
        "demerit good",
        "merit good",
        "imperfect information",
        "inequality",
        "poverty",
        "gini",
        "transfer payment",
        "pollution permit",
    ],
    "macroeconomy": [
        "national income",
        "gdp",
        "gross domestic product",
        "gni",
        "real income",
        "nominal",
        "circular flow",
        "aggregate demand",
        "aggregate supply",
        "ad curve",
        "as curve",
        "economic growth",
        "growth rate",
        "unemployment",
        "inflation",
        "consumer prices index",
        "cpi",
        "deflation",
        "recession",
        "multiplier",
        "injection",
        "withdrawal",
        "saving",
        "investment",
    ],
    "government-macro-intervention": [
        "fiscal policy",
        "monetary policy",
        "supply-side policy",
        "government spending",
        "budget deficit",
        "budget surplus",
        "interest rate",
        "central bank",
        "money supply",
        "macroeconomic objective",
        "macroeconomic policy",
        "reduce inflation",
        "reduce unemployment",
        "expansionary",
        "contractionary",
        "tax rates",
        "exchange control",
    ],
    "international-economic-issues": [
        "international trade",
        "exports",
        "imports",
        "trade",
        "protectionism",
        "tariff",
        "quota",
        "embargo",
        "balance of payments",
        "current account",
        "exchange rate",
        "currency",
        "depreciation",
        "appreciation",
        "comparative advantage",
        "absolute advantage",
        "terms of trade",
        "trade deficit",
        "trade surplus",
        "floating exchange",
        "fixed exchange",
    ],
}

DIRECT_EASY_PATTERNS = [
    "what is ",
    "which factor",
    "which statement defines",
    "which is an example",
    "what best describes",
    "what is considered",
    "which type of",
]

HARD_WORDS = [
    "calculate",
    "what is the value",
    "what is the change",
    "what is the amount",
    "what is the equilibrium level",
    "consumer surplus",
    "producer surplus",
    "elasticity",
    "terms of trade",
    "comparative advantage",
    "absolute advantage",
    "inflation rate",
    "index",
    "multiplier",
    "national income",
    "balance of payments",
    "exchange rate",
]

MEDIUM_WORDS = [
    "most likely",
    "least likely",
    "best explains",
    "best illustrates",
    "which policy",
    "what will be the effect",
    "what is likely",
    "assuming nothing else changes",
    "ceteris paribus",
]

QUESTION_START = re.compile(r"(?m)^\s*([1-9]|[12][0-9]|30)\s+(?=\S)")


def has_phrase(text: str, phrase: str) -> bool:
    lower = text.lower()
    compact = re.sub(r"\s+", "", lower)
    return phrase in lower or phrase.replace(" ", "") in compact


def has_any(text: str, phrases: list[str]) -> bool:
    return any(has_phrase(text, phrase) for phrase in phrases)


def clean_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    lines = []
    for raw in text.splitlines():
        line = " ".join(raw.split())
        if not line:
            continue
        if re.fullmatch(r"\d{1,2}", line):
            continue
        if "© UCLES" in line or "[Turn over" in line:
            continue
        if re.fullmatch(r"\*?\d{8,12}\*?", line):
            continue
        if "BLANK PAGE" in line:
            continue
        lines.append(line)
    return "\n".join(lines)


def paper_label(pdf_name: str) -> str:
    match = re.search(r"qp-(\d{4})(\d{2})-(?:economics|econimics)-p(\d{2})", pdf_name)
    if not match:
        return pdf_name.replace(".pdf", "")
    year, month, paper = match.groups()
    session = {
        "03": "March",
        "05": "May",
        "06": "June",
        "10": "October",
    }.get(month, month)
    return f"{session} {year} Paper {paper}"


def find_question_starts(pages: list[str]) -> list[dict]:
    candidates = []
    for page_index, page_text in enumerate(pages):
        if page_index == 0:
            continue
        for match in QUESTION_START.finditer(page_text):
            candidates.append(
                {
                    "number": int(match.group(1)),
                    "page_index": page_index,
                    "start": match.start(),
                }
            )

    starts = []
    expected = 1
    for candidate in candidates:
        if candidate["number"] == expected:
            starts.append(candidate)
            expected += 1
            if expected == 31:
                break

    return starts


def extract_page_set(reader: PdfReader, mode: str) -> list[str]:
    pages = []
    for page in reader.pages:
        if mode == "layout":
            try:
                with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                    text = page.extract_text(extraction_mode="layout") or ""
            except TypeError:
                text = page.extract_text() or ""
        else:
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                text = page.extract_text() or ""
        pages.append(clean_text(text))
    return pages


def extract_questions(pdf_path: Path) -> list[dict]:
    reader = PdfReader(str(pdf_path))
    plain_pages = extract_page_set(reader, "plain")
    plain_starts = find_question_starts(plain_pages)
    layout_pages = extract_page_set(reader, "layout")
    layout_starts = find_question_starts(layout_pages)

    if len(layout_starts) > len(plain_starts):
        pages, starts = layout_pages, layout_starts
    else:
        pages, starts = plain_pages, plain_starts

    if len(starts) != 30:
        raise RuntimeError(f"Expected 30 questions in {pdf_path.name}, found {len(starts)}")

    questions = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else None
        if end and end["page_index"] == start["page_index"]:
            question_text = pages[start["page_index"]][start["start"] : end["start"]]
        else:
            parts = [pages[start["page_index"]][start["start"] :]]
            last_page = end["page_index"] if end else len(pages)
            for page_index in range(start["page_index"] + 1, last_page):
                parts.append(pages[page_index])
            if end:
                parts.append(pages[end["page_index"]][: end["start"]])
            question_text = "\n".join(parts)
        questions.append(
            {
                "number": start["number"],
                "page": start["page_index"] + 1,
                "text": question_text.strip(),
            }
        )
    return questions


def visible_stem(text: str) -> str:
    text = re.sub(r"(?m)^\s*[ABCD]\s+.*$", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^\d+\s+", "", text)
    return text


def numeric_option_count(text: str) -> int:
    count = 0
    for label in "ABCD":
        pattern = r"(?:^|\s)" + label + r"\s+([+\-–−$£€]?\s*\d[\d\s,.]*(?:\.\d+)?\s*(?:%|bn|m|million|billion|cents|units|tonnes|years|months)?)"
        if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            count += 1
    return count


def classify_topic(text: str) -> str:
    scores = Counter()
    for topic_id, words in TOPIC_KEYWORDS.items():
        for word in words:
            if has_phrase(text, word):
                scores[topic_id] += 2 if " " in word else 1

    # Resolve common syllabus overlaps.
    if has_any(text, ["mixed economy", "market economy", "planned economy", "production possibility", "factor of production", "division of labour", "opportunity cost"]):
        scores["basic-economic-ideas"] += 5
    if has_any(text, ["tariff", "quota", "exchange rate", "balance of payments", "comparative advantage", "terms of trade"]):
        scores["international-economic-issues"] += 5
    if has_any(text, ["externality", "market failure", "tax", "subsidy", "maximum price", "minimum price", "gini", "inequality"]):
        scores["government-micro-intervention"] += 4
    if has_any(text, ["fiscal policy", "monetary policy", "supply-side policy", "interest rate", "budget deficit", "government spending"]):
        scores["government-macro-intervention"] += 5
    if has_any(text, ["aggregate demand", "aggregate supply", "inflation", "unemployment", "national income", "gdp", "circular flow"]):
        scores["macroeconomy"] += 3
    if has_any(text, ["national income", "gross domestic product", "gdp", "gni", "recorded level of national income"]):
        scores["macroeconomy"] += 6
    if has_any(text, ["equilibrium real output", "consumption expenditure", "real output", "open economy with a government"]):
        scores["macroeconomy"] += 6
    if has_any(text, ["elasticity", "consumer surplus", "producer surplus", "demand", "supply"]):
        scores["price-system"] += 2

    if not scores:
        return "basic-economic-ideas"
    return scores.most_common(1)[0][0]


def is_type_c(text: str) -> bool:
    stem = visible_stem(text).lower()
    number_count = len(re.findall(r"(?<!\w)[+$£€-]?\d+(?:\.\d+)?(?:%|m|bn| million| billion)?(?!\w)", text))
    if numeric_option_count(text) < 3 or number_count < 6:
        return False

    data_signal = has_any(
        text,
        [
            "table shows",
            "table below shows",
            "data for",
            "some data",
            "selected statistics",
            "publishes the following",
            "the following",
            "information shows data",
            "income accounts",
            "open economy with a government",
            "households spend",
            "firms spend",
            "government spends",
        ],
    )
    question_signal = has_any(
        stem,
        [
            "what is",
            "what was",
            "how much",
            "what can be concluded",
            "equilibrium level",
            "unemployment rate",
        ],
    )
    accounting_signal = has_any(
        text,
        [
            "gross domestic product",
            "gross national income",
            "gross value added",
            "national income",
            "income accounts",
            "gdp",
            "gni",
            "net domestic product",
            "basic prices",
            "market prices",
            "factor income",
            "indirect taxes",
            "subsidies",
            "unemployment rate",
            "labour market statistics",
            "labour force",
            "working age",
            "open economy",
            "exports and imports",
            "withdrawal",
            "injection",
            "savings",
            "investment",
            "taxation",
            "recorded level of national income",
            "wealth",
            "assets",
        ],
    )
    non_type_c_calculation = has_any(
        text,
        [
            "elasticity",
            "consumer prices index",
            "cpi",
            "worker's salary",
            "worker’s salary",
            "exchange rate",
            "comparative advantage",
            "market share",
            "supply and demand",
            "price per",
        ],
    )
    if non_type_c_calculation and not has_any(text, ["national income", "gdp", "gni", "income accounts", "gross domestic product", "gross national income"]):
        return False

    return data_signal and question_signal and accounting_signal


def classify_difficulty(text: str, type_c: bool) -> str:
    stem = visible_stem(text).lower()
    number_count = len(re.findall(r"(?<!\w)[+$£€-]?\d+(?:\.\d+)?%?(?!\w)", text))
    has_visual = has_any(text, ["diagram shows", "table shows", "graph shows", "chart shows", "the diagram", "the table"])
    hard_score = 0
    medium_score = 0

    if type_c:
        hard_score += 3
    if has_visual:
        hard_score += 2
    if number_count >= 8:
        hard_score += 2
    if numeric_option_count(text) >= 3:
        hard_score += 1
    for word in HARD_WORDS:
        if has_phrase(text, word):
            hard_score += 2
    for word in MEDIUM_WORDS:
        if has_phrase(text, word):
            medium_score += 2
    if has_any(text, ["not", "except", "least"]):
        medium_score += 1
    if has_any(text, ["shift", "increase", "decrease", "effect", "cause", "result"]):
        medium_score += 1

    if hard_score >= 4:
        return "Hard"
    if medium_score >= 2 or hard_score >= 2:
        return "Medium"
    compact_stem = re.sub(r"\s+", "", stem)
    if any(stem.startswith(pattern) or compact_stem.startswith(pattern.replace(" ", "")) for pattern in DIRECT_EASY_PATTERNS) and number_count <= 4:
        return "Easy"
    return "Medium"


def cue_for(text: str, topic_id: str, type_c: bool, difficulty: str) -> list[str]:
    cues = []
    for word in TOPIC_KEYWORDS[topic_id]:
        if has_phrase(text, word):
            cues.append(word)
        if len(cues) == 3:
            break
    if type_c:
        cues.append("Type C table/accounting calculation")
    if difficulty == "Hard":
        for word in HARD_WORDS:
            if has_phrase(text, word) and word not in cues:
                cues.append(word)
                break
    return cues[:4]


def build_bank() -> dict:
    questions = []
    papers = []
    for pdf_path in sorted(ROOT.glob("*.pdf")):
        paper = {
            "file": pdf_path.name,
            "label": paper_label(pdf_path.name),
        }
        papers.append(paper)
        for question in extract_questions(pdf_path):
            topic_id = classify_topic(question["text"])
            type_c = is_type_c(question["text"])
            difficulty = classify_difficulty(question["text"], type_c)
            questions.append(
                {
                    "id": f"{pdf_path.stem}-q{question['number']:02d}",
                    "paper": paper["label"],
                    "file": pdf_path.name,
                    "questionNumber": question["number"],
                    "page": question["page"],
                    "difficulty": difficulty,
                    "topic": topic_id,
                    "typeC": type_c,
                    "cues": cue_for(question["text"], topic_id, type_c, difficulty),
                }
            )

    topics_by_id = {topic["id"]: topic for topic in TOPICS}
    difficulty_counts = Counter(question["difficulty"] for question in questions)
    topic_counts = Counter(question["topic"] for question in questions)
    for topic in TOPICS:
        topic["count"] = topic_counts[topic["id"]]

    return {
        "schemaVersion": 1,
        "generatedFrom": "Original PDFs in the workspace; question text is displayed from the PDFs, not copied into this data file.",
        "topics": TOPICS,
        "difficulties": [
            {"id": "Easy", "name": "Easy", "count": difficulty_counts["Easy"]},
            {"id": "Medium", "name": "Medium", "count": difficulty_counts["Medium"]},
            {"id": "Hard", "name": "Hard", "count": difficulty_counts["Hard"]},
        ],
        "papers": papers,
        "questions": questions,
        "summary": {
            "paperCount": len(papers),
            "questionCount": len(questions),
            "typeCCount": sum(1 for question in questions if question["typeC"]),
            "topicCounts": dict(topic_counts),
            "difficultyCounts": dict(difficulty_counts),
        },
    }


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    bank = build_bank()
    json_text = json.dumps(bank, indent=2, ensure_ascii=False)
    (OUT_DIR / "questions.json").write_text(json_text + "\n", encoding="utf-8")
    (OUT_DIR / "question-data.js").write_text(
        "window.QUESTION_BANK = " + json_text + ";\n", encoding="utf-8"
    )
    print(f"Wrote {len(bank['questions'])} questions from {len(bank['papers'])} papers.")
    print("Difficulty:", dict(bank["summary"]["difficultyCounts"]))
    print("Topics:", dict(bank["summary"]["topicCounts"]))
    print("Type C:", bank["summary"]["typeCCount"])


if __name__ == "__main__":
    main()
