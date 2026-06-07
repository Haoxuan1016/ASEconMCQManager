# AS Economics MCQ Browser

Interactive local browser for Cambridge International AS Economics Paper 1 multiple-choice past papers.

The app lets you filter questions by difficulty, AS Economics topic, and a special Type C category for named-value table/list calculation questions. It displays the original PDF question paper and jumps to the page for the selected question.

## Features

- Browse 510 questions from 17 AS Economics Paper 1 PDFs.
- Filter by difficulty: Easy, Medium, Hard.
- Filter by AS Economics topic:
  - Basic Economic Ideas and Resource Allocation
  - The Price System and the Microeconomy
  - Government Microeconomic Intervention
  - The Macroeconomy
  - Government Macroeconomic Intervention
  - International Economic Issues
- Toggle Type C questions for named-value table/list calculation questions.
- View original PDFs directly in the browser.
- Hard questions include sample answer letters and choice-by-choice explanations.

## Run Locally

Use a local HTTP server for reliable PDF display. Opening `index.html` with `file://` can cause browser PDF frame security issues.

```bash
python -m http.server 8765 --bind 127.0.0.1
```

Then open:

```text
http://127.0.0.1:8765/index.html
```

## Project Structure

```text
.
├── index.html
├── qp-*.pdf
├── web/
│   ├── app.js
│   ├── styles.css
│   ├── question-data.js
│   ├── questions.json
│   ├── hard-explanations.js
│   └── hard-explanations.json
└── tools/
    ├── generate_question_data.py
    └── generate_hard_explanations.py
```

## Regenerate Data

Install/use Python with `pypdf` available.

Regenerate question categories:

```bash
python tools/generate_question_data.py
```

Regenerate hard-question explanations:

```bash
python tools/generate_hard_explanations.py
```

The explanation generator downloads matching 9708 Paper 1 mark-scheme PDFs from public past-paper mirrors to extract answer letters. The generated JSON includes source URLs under the `sources` key.

## Notes

- The app does not copy full question text into the interface; it uses the original PDFs for question display.
- Categorisation is generated from extracted PDF text and heuristic topic/difficulty rules.
- Explanations are generated study notes, not official mark-scheme commentary.
- PDF page navigation uses cache-busted iframe URLs so repeated jumps within the same PDF reload reliably.

## Disclaimer

This project is an independent study tool. Cambridge International and the past-paper mirrors are not affiliated with this project. Past-paper and mark-scheme files remain subject to their original copyright and usage terms.
