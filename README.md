# MedRec — Medication-Preserving Clinical Document De-identification
@IRS Lab, Stony Brook Medicine

Research work for the MedRec / MedInsight medication reconciliation application associated with Stony Brook Medicine.

This repository contains standalone tools for extracting medication information from medical documents and redacting surrounding non-medication content. The goal is to reduce patient information exposure before downstream drug–drug interaction analysis using external LLM services.

## Overview

The current PDF pipeline:

1. Extracts words and page coordinates using PyMuPDF.
2. Reconstructs the extracted words into continuous NLP-friendly text while preserving word-to-coordinate mappings.
3. Uses a locally fine-tuned Med7 NLP model to detect medication-related entities.
4. Validates detected drug names against a locally cached DailyMed vocabulary.
5. Preserves accepted medication entities and black-redacts all other extracted words.
6. Applies the PDF redactions and saves the processed document locally.

The processing script does not send document text to an external inference service.

The current approach follows a medication allowlist strategy: medication information is identified and preserved, while non-medication content is redacted.

## Medication Entities

Med7 identifies seven medication-related entity types:

| Entity | Example |
|---|---|
| DRUG | Metformin |
| STRENGTH | 500 mg |
| DOSAGE | One tablet |
| FREQUENCY | Twice daily |
| ROUTE | Orally |
| FORM | Tablet |
| DURATION | Seven days |

For example:

```text
Take Lisinopril 10 mg by mouth once daily for 7 days.
```

Med7 may identify:

```text
Lisinopril   -> DRUG
10 mg        -> STRENGTH
by mouth     -> ROUTE
once daily   -> FREQUENCY
for 7 days   -> DURATION
```

## Fine-Tuned Med7 Model

The original Med7 model was further fine-tuned on a custom labeled dataset designed around the document formats used in this project.

The fine-tuning dataset includes:

- Medication names
- Strengths
- Dosages
- Frequencies
- Routes
- Forms
- Durations
- Multiple medications in the same sentence
- Narrative-style medication mentions
- Negative examples containing names, addresses, phone numbers, and other identifying information
- Negative medication-context examples where words such as "medication" appear without an actual drug entity

All medication entities present in positive training examples are labeled.

The fine-tuning process continues training from the pretrained Med7 model rather than training a new NER model from scratch.

During training, both the `tok2vec` and `ner` components remain active so that the model can update its learned text representations and entity predictions.

Model performance is monitored using:

- Precision
- Recall
- F1 score

The model with the best development-set F1 score is saved for use in the redaction pipeline.

## Tools

### Current Pipeline

- Python
- spaCy
- Fine-tuned Med7
- PyMuPDF
- DailyMed

### Earlier Experiments

- Microsoft Presidio — earlier PHI detection experiments
- python-docx — earlier DOCX processing experiments

## Setup

The current development environment uses macOS.

Use Python 3.12 and create a dedicated virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Upgrade package tools:

```bash
python -m pip install --upgrade pip setuptools wheel
```

Install required dependencies:

```bash
python -m pip install pymupdf spacy
```

Install Med7:

```bash
python -m pip install "en-core-med7-lg @ https://huggingface.co/kormilitzin/en_core_med7_lg/resolve/main/en_core_med7_lg-1.1.0-py3-none-any.whl"
```

Verify that the original Med7 model loads correctly:

```bash
python -c "import spacy; spacy.load('en_core_med7_lg'); print('Med7 loaded successfully')"
```

## Fine-Tuning Setup

The fine-tuning package is stored in:

```text
med7_finetune_package_updated/
```

Activate the project environment:

```bash
source .venv/bin/activate
```

Move into the fine-tuning directory:

```bash
cd med7_finetune_package_updated
```

Convert the labeled JSONL datasets into spaCy format:

```bash
python convert_to_spacy.py
```

This creates:

```text
train.spacy
dev.spacy
```

Fine-tune Med7:

```bash
python train_med7.py
```

The training process saves:

```text
med7_finetuned/
├── best/
└── last/
```

The `best` model corresponds to the highest development-set F1 score observed during training.

Evaluate the fine-tuned model:

```bash
python evaluate_med7.py med7_finetuned/best
```

Verify that the fine-tuned model loads successfully:

```bash
python -c "import spacy; spacy.load('med7_finetuned/best'); print('Fine-tuned Med7 loaded successfully')"
```

## Using the Fine-Tuned Model

The PDF processing script loads the fine-tuned Med7 model instead of the original pretrained model.

Example:

```python
MED7_MODEL_PATH = (
    BASE_DIR
    / "med7_finetune_package_updated"
    / "med7_finetuned"
    / "best"
)

med7 = spacy.load(
    MED7_MODEL_PATH
)
```

## PDF Processing Workflow

The processing workflow is:

```text
PDF
 ↓
PyMuPDF extracts words + coordinates
 ↓
Reconstruct continuous text
 ↓
Fine-tuned Med7 detects medication entities
 ↓
Optional DailyMed drug confirmation
 ↓
Map Med7 character spans back to PDF word coordinates
 ↓
Preserve medication-related words
 ↓
Redact all other extracted words
 ↓
Apply permanent redactions
 ↓
Save processed PDF
```

## Run PDF Processing

Place test PDFs inside:

```text
medrec_phi_redaction_test_dataset/
```

Place the local medication vocabulary beside the processing script:

```text
drug_preservation_set.json
```

The vocabulary must be a JSON list of medication-name strings obtained from DailyMed.

It is used locally during processing and is not required to be downloaded at runtime if the cache is already available.

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Run:

```bash
python redact_medication_only.py
```

Processed files are saved as:

```text
output/medication_only_<original_filename>.pdf
```

By default, drug preservation can require both a Med7 `DRUG` detection and confirmation against the locally cached DailyMed vocabulary:

```python
REQUIRE_DAILYMED_CONFIRMATION = True
```

## How PDF Mapping Works

Med7 operates on text and returns character positions for detected entities.

PyMuPDF provides words together with their physical coordinates on the PDF page.

While reconstructing the page text, the pipeline stores a mapping between:

```text
character positions
        ↕
PDF word rectangles
```

For example:

```text
Jonathan Reynolds takes Lisinopril 10 mg daily.
```

Med7 may identify:

```text
Lisinopril -> DRUG
10 mg      -> STRENGTH
daily      -> FREQUENCY
```

The stored word mapping is then used to locate those entities on the original PDF page.

Medication-related words are preserved and all other word rectangles are marked for redaction.

## Redaction Strategy

The current approach is different from the earlier PHI-focused implementation.

Earlier approach:

```text
Detect PHI
 ↓
Redact detected PHI
 ↓
Preserve everything else
```

Current approach:

```text
Detect medication information
 ↓
Preserve detected medication entities
 ↓
Redact everything else
```

This creates an allowlist-style workflow where only recognized medication information is retained.

## Evaluation

Synthetic documents are used to test medication preservation and non-medication information removal.

Earlier PHI-focused experiments included a separate PDF and DOCX benchmark. Those results belong to the previous implementation and should not be interpreted as performance results for the current fine-tuned Med7 pipeline.

The current evaluation focuses on:

- Medication entity precision
- Medication entity recall
- Overall entity F1 score
- Preservation of medication details
- Incorrectly preserved non-medication information
- Incorrectly redacted medication information
- Behavior when no medication entity is detected
- Performance across different PDF layouts and narrative styles

Evaluation should also be reviewed separately for:

```text
DRUG
STRENGTH
DOSAGE
FREQUENCY
ROUTE
FORM
DURATION
```

A separate independent synthetic PDF dataset is used for final testing and should not be included in the fine-tuning dataset.

This helps avoid evaluating the model on examples it has already seen during training.

## Test Coverage

The synthetic evaluation datasets include cases such as:

- Structured medication fields
- Free-form clinical narratives
- Multiple medications
- Brand and generic drug names
- Drug strength and dosage
- Frequency
- Route
- Form
- Duration
- Table layouts
- Header and footer text
- Names and contact information
- Addresses
- Phone numbers
- Medication-related sentences without actual medications
- Pages containing no valid medication entities

## Current Limitations

- The fine-tuned Med7 model can still miss uncommon or out-of-distribution medication expressions.
- Missed medication entities are redacted because the current workflow preserves only recognized medication information.
- DailyMed validation confirms Med7-detected drug names but does not independently identify drugs that Med7 misses.
- The current code does not explicitly associate every dosage, frequency, duration, route, or form with a specific drug when several medications are present.
- Scanned PDFs require OCR before Med7 can process their text.
- Pages without extractable text are fully redacted by the current fail-closed workflow.
- The quality of medication detection depends on the diversity and representativeness of the fine-tuning dataset.
- Model predictions and PDF redaction results require additional validation before institutional or clinical deployment.
- DOCX and earlier Presidio workflows are separate experiments and do not automatically use the current fine-tuned Med7 pipeline.

## Future Improvements

Potential improvements include:

- Expand the fine-tuning dataset using more diverse medication examples.
- Include more institution-specific document formats.
- Increase coverage of uncommon drug names and abbreviations.
- Add OCR support for scanned medical documents.
- Improve medication-to-attribute association when multiple drugs appear in the same sentence.
- Evaluate per-entity recall and precision on larger independent test sets.
- Add automated regression testing for medication preservation.
- Monitor model failures and incorporate reviewed failure cases into future fine-tuning datasets.
- Validate performance on appropriately authorized institution-specific data before deployment.

## Privacy

Use synthetic or appropriately authorized data for development and testing.

Do not commit:

- Patient records
- Protected health information
- Credentials
- Raw private document logs
- Private institutional datasets
- Sensitive training data

The current medication extraction and redaction process runs locally and does not send document text to an external inference service.

This is a research prototype supporting privacy-conscious healthcare processing.

Its use alone does not establish HIPAA compliance.

## References

- Med7: https://github.com/kormilitzin/med7
- Med7 model: https://huggingface.co/kormilitzin/en_core_med7_lg
- DailyMed: https://dailymed.nlm.nih.gov/
- spaCy: https://spacy.io/
- PyMuPDF: https://pymupdf.readthedocs.io/
