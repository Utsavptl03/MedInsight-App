# MedInsight-App
@IRS Lab, StonyBrook Medicine

Research work for the MedInsight medication reconciliation application associated with Stony Brook Medicine.

This repository contains standalone tools for extracting medication information from medical documents and redacting surrounding text. The goal is to reduce patient information exposure before downstream drug–drug interaction analysis using external LLM services.

## Overview

The current PDF pipeline:

1. Extracts words and page coordinates using PyMuPDF.
2. Flattens the extracted words into continuous text.
3. Uses a local Med7 NLP model to detect medication entities.
4. Validates detected drug names against a locally cached DailyMed vocabulary.
5. Preserves accepted medication entities and black-redacts other extracted words.
6. Saves the processed PDF locally.

The processing script does not send document text to an external inference service.

## Medication Entities

Med7 identifies seven entity types:

| Entity | Example |
|---|---|
| DRUG | Metformin |
| STRENGTH | 500 mg |
| DOSAGE | One tablet |
| FREQUENCY | Twice daily |
| ROUTE | Orally |
| FORM | Tablet |
| DURATION | Seven days |

## Tools

- Python
- spaCy and Med7 — medication named entity recognition
- PyMuPDF — PDF extraction, coordinate mapping, and redaction
- DailyMed — public medication vocabulary cached locally
- Microsoft Presidio — earlier PHI detection experiments
- python-docx — earlier DOCX processing experiments

## Setup

Use Python 3.12 and create a dedicated environment:

```powershell
py -3.12 -m venv .venv-med7
.\.venv-med7\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install pymupdf
python -m pip install "en-core-med7-lg @ https://huggingface.co/kormilitzin/en_core_med7_lg/resolve/main/en_core_med7_lg-1.1.0-py3-none-any.whl"
```

Verify the model:

```powershell
python -c "import spacy; spacy.load('en_core_med7_lg'); print('Med7 loaded successfully')"
```

## Run PDF Processing

Place test PDFs directly inside:

```text
medrec_phi_redaction_test_dataset/
```

Place the local medication vocabulary beside the processing script:

```text
drug_preservation_set.json
```

The vocabulary must be a JSON list of medication-name strings obtained from DailyMed. It is not included in this repository and must be prepared before running the script.

Run:

```powershell
python redact_medication_only.py
```

Processed files are saved as:

```text
output/medication_only_<original_filename>.pdf
```

By default, drug preservation requires both a Med7 DRUG detection and confirmation against the local DailyMed cache:

```python
REQUIRE_DAILYMED_CONFIRMATION = True
```

## Evaluation

Synthetic documents are used to test medication preservation and identifying-information removal.

Earlier PHI-focused experiments included a 34-file PDF and DOCX benchmark. Those results belong to the earlier implementation and should not be interpreted as performance results for the current Med7 pipeline.

Evaluation focuses on:

- Medication detection precision and recall
- Preservation of medication details
- Incorrectly preserved non-medication information
- Incorrectly redacted medication information
- Behavior when no medication is validated

## Current Limitations

- Med7 can miss medication names, including names present in the DailyMed cache.
- Dictionary validation checks model-detected drugs; it does not independently discover missed drugs.
- The current code does not explicitly associate every dosage or duration with a specific drug.
- Scanned PDFs require OCR for medication extraction. Pages without extractable text are fully redacted.
- When a text-containing page has no validated drug, all extracted words are redacted; other PDF content may remain.
- Model predictions and PDF redaction results require validation before external use.
- DOCX and earlier Presidio scripts are separate experiments and do not automatically use the Med7 workflow.

## Privacy

Use synthetic or appropriately authorized data for development and testing. Do not commit patient records, credentials, raw document logs, or private training data.

This is a research prototype supporting privacy-conscious healthcare processing. Its use alone does not establish HIPAA compliance.

## References

- Med7: https://github.com/kormilitzin/med7
- Med7 model: https://huggingface.co/kormilitzin/en_core_med7_lg
- DailyMed: https://dailymed.nlm.nih.gov/
- spaCy: https://spacy.io/
- PyMuPDF: https://pymupdf.readthedocs.io/
