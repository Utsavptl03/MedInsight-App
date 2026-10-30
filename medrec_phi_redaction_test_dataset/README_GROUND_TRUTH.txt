Matching ground truth for allcases.zip

This package contains the 18 uploaded PDF cases plus:
- ground_truth.json
- ground_truth.csv

The evaluator should look for:
  medrec_phi_redaction_test_dataset/ground_truth.json

Important:
- There are 18 PDFs in the uploaded ZIP, not 20.
- case_18_scanned_image.pdf has no searchable text layer and is expected to fail with the current text-only PyMuPDF redactor unless OCR is added.
- case_14_false_positive_medications.pdf intentionally contains no PHI and is primarily a medication-preservation test.
