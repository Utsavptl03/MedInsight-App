print("DOCX Redaction Started")

from pathlib import Path
import re

from docx import Document
from presidio_analyzer import AnalyzerEngine


# ------------------------------------------------------
# PATHS
# ------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

INPUT_DOCX = BASE_DIR / "sample.docx"
OUTPUT_DOCX = BASE_DIR / "output" / "redacted_all_phi.docx"

OUTPUT_DOCX.parent.mkdir(parents=True, exist_ok=True)

if not INPUT_DOCX.exists():
    raise FileNotFoundError(
        f"Could not find: {INPUT_DOCX}"
    )


# ------------------------------------------------------
# PRESIDIO
# ------------------------------------------------------

analyzer = AnalyzerEngine()

stats = {}


# ------------------------------------------------------
# DIRECT REGEX PATTERNS
# ------------------------------------------------------

PATTERNS = {

    "SSN": re.compile(
        r"\b\d{3}-\d{2}-\d{4}\b"
    ),

    "PHONE": re.compile(
        r"\b(?:\+?1[-.\s]?)?"
        r"(?:\(?\d{3}\)?[-.\s]?)"
        r"\d{3}[-.\s]?\d{4}\b"
    ),

    "EMAIL": re.compile(
        r"\b[A-Za-z0-9._%+-]+@"
        r"[A-Za-z0-9.-]+\."
        r"[A-Za-z]{2,}\b"
    ),

    "IP_ADDRESS": re.compile(
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    ),

    "URL": re.compile(
        r"\b(?:https?://|www\.)\S+\b",
        re.IGNORECASE
    ),

    "DATE": re.compile(
        r"\b(?:"
        r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
        r"|"
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
        r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|"
        r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"\s+\d{1,2},?\s+\d{4}"
        r")\b",
        re.IGNORECASE
    ),

    "ZIP_CODE": re.compile(
        r"\b\d{5}(?:-\d{4})?\b"
    ),

    "MRN": re.compile(
        r"\bMRN[-\s]?[A-Za-z0-9]{4,}\b",
        re.IGNORECASE
    ),

    "RX_NUMBER": re.compile(
        r"\bRX[-\s]?[A-Za-z0-9]{4,}\b",
        re.IGNORECASE
    ),

    "ACCOUNT_NUMBER": re.compile(
        r"\bAC\d{4,}\b",
        re.IGNORECASE
    ),

    "MEMBER_ID": re.compile(
        r"\b(?:BCBS|MEMBER|INS)[-]?[A-Za-z0-9]{4,}\b",
        re.IGNORECASE
    ),

    "LICENSE_NUMBER": re.compile(
        r"\b[A-Z]{2}\d{5,10}\b"
    ),

    "STREET_ADDRESS": re.compile(
        r"\b\d{1,6}\s+"
        r"[A-Za-z0-9.'\- ]+\s+"
        r"(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|"
        r"Lane|Ln|Boulevard|Blvd|Court|Ct|Way|Place|Pl)"
        r"\b",
        re.IGNORECASE
    ),
}


# ------------------------------------------------------
# FIELD-BASED IDENTIFIERS
# ------------------------------------------------------

FIELD_PATTERNS = {

    "PATIENT_NAME": re.compile(
        r"(?:Patient\s+Name|Name)\s*:\s*"
        r"([A-Z][A-Za-z'.-]+"
        r"(?:\s+[A-Z][A-Za-z'.-]+){1,3})",
        re.IGNORECASE
    ),

    "DOB": re.compile(
        r"(?:DOB|Date\s+of\s+Birth|Birth\s+Date)"
        r"\s*:\s*([^\n]+)",
        re.IGNORECASE
    ),

    "MRN_FIELD": re.compile(
        r"(?:MRN|Medical\s+Record(?:\s+Number)?|Medical\s+Record\s+#)"
        r"\s*:\s*([A-Za-z0-9-]+)",
        re.IGNORECASE
    ),

    "ADDRESS_FIELD": re.compile(
        r"Address\s*:\s*([^\n]+)",
        re.IGNORECASE
    ),

    "RX_FIELD": re.compile(
        r"(?:Rx|Prescription)"
        r"\s*(?:Number|No\.?|#)?"
        r"\s*:\s*([A-Za-z0-9-]+)",
        re.IGNORECASE
    ),

    "ACCOUNT_FIELD": re.compile(
        r"Account"
        r"\s*(?:Number|No\.?|#)?"
        r"\s*:\s*([A-Za-z0-9-]+)",
        re.IGNORECASE
    ),

    "MEMBER_FIELD": re.compile(
        r"(?:Member|Insurance|Health\s*Plan)"
        r"\s*(?:ID|Number|No\.?|#)"
        r"\s*:\s*([A-Za-z0-9-]+)",
        re.IGNORECASE
    ),

    "EMERGENCY_CONTACT": re.compile(
        r"Emergency\s+Contact\s*:\s*"
        r"([A-Z][A-Za-z'.-]+"
        r"(?:\s+[A-Z][A-Za-z'.-]+){1,3})",
        re.IGNORECASE
    ),

    "LICENSE_FIELD": re.compile(
        r"License\s+(?:Number|No\.?|#)"
        r"\s*:\s*([A-Za-z0-9-]+)",
        re.IGNORECASE
    ),

    "ADMISSION_DATE": re.compile(
        r"Admission\s+Date\s*:\s*([^\n]+)",
        re.IGNORECASE
    ),

    "DISCHARGE_DATE": re.compile(
        r"Discharge\s+Date\s*:\s*([^\n]+)",
        re.IGNORECASE
    ),
}


# ------------------------------------------------------
# REPLACEMENT
# ------------------------------------------------------

REDACTION_TEXT = "[REDACTED]"


def add_stat(entity_type):
    stats[entity_type] = stats.get(entity_type, 0) + 1


def redact_text(text):
    """
    Takes plain text and returns:
        redacted_text
        whether anything changed
    """

    if not text.strip():
        return text, False

    original_text = text
    replacements = []

    # --------------------------------------------------
    # 1. Field-based PHI
    # --------------------------------------------------

    for entity_type, pattern in FIELD_PATTERNS.items():

        for match in pattern.finditer(text):

            value = match.group(1).strip()

            if value:
                replacements.append(
                    (
                        match.start(1),
                        match.end(1),
                        entity_type,
                        value
                    )
                )

    # --------------------------------------------------
    # 2. Regex PHI
    # --------------------------------------------------

    for entity_type, pattern in PATTERNS.items():

        for match in pattern.finditer(text):

            replacements.append(
                (
                    match.start(),
                    match.end(),
                    entity_type,
                    match.group()
                )
            )

    # --------------------------------------------------
    # 3. Presidio backup
    # --------------------------------------------------

    presidio_results = analyzer.analyze(
        text=text,
        entities=[
            "EMAIL_ADDRESS",
            "PHONE_NUMBER",
            "US_SSN",
            "IP_ADDRESS",
            "URL"
        ],
        language="en"
    )

    for result in presidio_results:

        value = text[result.start:result.end]

        replacements.append(
            (
                result.start,
                result.end,
                result.entity_type,
                value
            )
        )

    # Nothing detected
    if not replacements:
        return text, False

    # --------------------------------------------------
    # Remove duplicates / overlapping exact detections
    # --------------------------------------------------

    unique = {}

    for start, end, entity, value in replacements:
        key = (start, end)

        if key not in unique:
            unique[key] = (
                start,
                end,
                entity,
                value
            )

    replacements = list(unique.values())

    # Replace from the end of the string backwards.
    # Otherwise indexes change after each replacement.
    replacements.sort(
        key=lambda x: x[0],
        reverse=True
    )

    for start, end, entity_type, value in replacements:

        print(
            f"REDACTING [{entity_type}]: "
            f"{value!r}"
        )

        text = (
            text[:start]
            + REDACTION_TEXT
            + text[end:]
        )

        add_stat(entity_type)

    return text, text != original_text


# ------------------------------------------------------
# PROCESS A PARAGRAPH
# ------------------------------------------------------

def process_paragraph(paragraph):

    text = paragraph.text

    redacted_text, changed = redact_text(text)

    if not changed:
        return

    # IMPORTANT:
    # This removes the original PHI from the paragraph.
    #
    # Assigning paragraph.text may simplify run-level
    # formatting, which is acceptable for this prototype.
    paragraph.text = redacted_text


# ------------------------------------------------------
# PROCESS TABLES
# ------------------------------------------------------

def process_table(table):

    for row in table.rows:

        for cell in row.cells:

            for paragraph in cell.paragraphs:
                process_paragraph(paragraph)

            # Handle nested tables
            for nested_table in cell.tables:
                process_table(nested_table)


# ------------------------------------------------------
# LOAD DOCX
# ------------------------------------------------------

document = Document(INPUT_DOCX)


# ------------------------------------------------------
# BODY PARAGRAPHS
# ------------------------------------------------------

print("\nProcessing document body...")

for paragraph in document.paragraphs:
    process_paragraph(paragraph)


# ------------------------------------------------------
# TABLES
# ------------------------------------------------------

print("\nProcessing tables...")

for table in document.tables:
    process_table(table)


# ------------------------------------------------------
# HEADERS AND FOOTERS
# ------------------------------------------------------

print("\nProcessing headers and footers...")

for section in document.sections:

    # Header
    for paragraph in section.header.paragraphs:
        process_paragraph(paragraph)

    for table in section.header.tables:
        process_table(table)

    # Footer
    for paragraph in section.footer.paragraphs:
        process_paragraph(paragraph)

    for table in section.footer.tables:
        process_table(table)


# ------------------------------------------------------
# SAVE
# ------------------------------------------------------

document.save(OUTPUT_DOCX)


print("\n================================")
print("FINISHED")
print("================================")

print("\nRedaction summary:")

for entity, count in sorted(stats.items()):
    print(f"{entity}: {count}")

print("\nOutput:")
print(OUTPUT_DOCX)