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
    if len(option) > 90:
        return option[:87].rstrip() + "..."
    return option


def reasoning_focus(question: dict, question_text: str) -> str:
    cues = [cue for cue in question.get("cues", []) if cue != "Type C table/accounting calculation"]
    if cues:
        return ", ".join(cues[:2])
    return TOPIC_LANGUAGE.get(question["topic"], "the relevant economic relationship")


def explanation_for(question: dict, question_text: str, answer: str) -> dict:
    options = option_texts(question_text)
    focus = reasoning_focus(question, question_text)
    correct_text = compact_option(options.get(answer, ""))
    conclusion = f"The answer is {answer}: {correct_text} is the option that best follows from {focus} in the question."
    choice_explanations = {}
    for label in "ABCD":
        option = compact_option(options.get(label, ""))
        if label == answer:
            sentences = [
                f"{label} is correct because it matches the answer key and the required {focus}.",
                f"The wording or calculation in {option} is consistent with the data and the economic concept being tested.",
                "It keeps the direction of the change, the relevant formula, or the diagram reading aligned with the question stem.",
                "Therefore it is the strongest choice once the distractors are checked against the same reasoning.",
            ]
        else:
            sentences = [
                f"{label} is not correct because {option} does not follow the required {focus}.",
                f"It is a distractor that usually comes from using the wrong sign, wrong item, wrong comparison, or wrong diagram area.",
                f"Compared with the correct answer {answer}, it misses at least one condition stated in the question stem.",
                "So this option should be rejected after applying the relevant calculation or cause-and-effect relationship.",
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
