Med7 Test Dataset V2

Purpose:
- Independent test set for the fine-tuned Med7 medication-only redaction pipeline.
- Do NOT add these examples to training if you want an unbiased test.

Expected behavior:
- Preserve only medication entities.
- Redact names, addresses, phones, IDs, dates, narrative text, and other non-medication content.
- Negative cases should preserve nothing.

Coverage:
- DRUG, STRENGTH, DOSAGE, FREQUENCY, ROUTE, FORM, DURATION
- Multiple drugs
- Brand names
- Narrative text
- Table layout
- Header/footer noise
- Punctuation
- Medication-context negative examples
