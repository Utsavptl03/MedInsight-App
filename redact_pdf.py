print("Script Started")

from pathlib import Path
import re
import json
import urllib.request
import urllib.parse

import pymupdf
from presidio_analyzer import AnalyzerEngine


# ------------------------------------------------------
# PATHS
# ------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

INPUT_PDF = BASE_DIR / "sample.pdf"
OUTPUT_PDF = BASE_DIR / "output" / "redacted_all_phi_v3.pdf"

DRUG_CACHE_FILE = BASE_DIR / "drug_preservation_set.json"

OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------
# PRESIDIO
# ------------------------------------------------------

analyzer = AnalyzerEngine()

doc = pymupdf.open(INPUT_PDF)

stats = {}

preserved_stats = {}


# ------------------------------------------------------
# NORMALIZATION
# ------------------------------------------------------

def normalize_text(value):
    """
    Normalize candidate/drug text before comparison.
    """

    value = value.lower().strip()

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    value = value.strip(
        ".,;:()[]{}\"'"
    )

    return value


# ------------------------------------------------------
# DAILYMED DRUG PRESERVATION SET
# ------------------------------------------------------

def download_dailymed_drug_names():
    """
    Downloads all available drug names from DailyMed's
    official /drugnames API.

    The result is cached locally so the API is not called
    every time the redaction script runs.
    """

    print("\nLoading DailyMed drug names...")

    drug_names = set()

    page = 1
    page_size = 100

    while True:

        url = (
            "https://dailymed.nlm.nih.gov/dailymed/services/v2/"
            f"drugnames.json?pagesize={page_size}&page={page}"
        )

        print(
            f"Downloading DailyMed page {page}..."
        )

        try:

            with urllib.request.urlopen(
                url,
                timeout=30
            ) as response:

                data = json.loads(
                    response.read().decode("utf-8")
                )

        except Exception as exc:

            print(
                f"DailyMed download stopped: {exc}"
            )

            break

        # DailyMed JSON normally contains:
        #
        # {
        #     "data": [...]
        # }
        #
        # but this extraction is intentionally tolerant
        # of capitalization/format changes.

        rows = (
            data.get("data")
            or data.get("DATA")
            or []
        )

        if not rows:
            break

        names_added_this_page = 0

        for row in rows:

            # Depending on response format, entries may
            # be strings or dictionaries.

            if isinstance(row, str):

                name = normalize_text(row)

                if name:
                    drug_names.add(name)
                    names_added_this_page += 1

            elif isinstance(row, dict):

                possible_values = [
                    row.get("drug_name"),
                    row.get("name"),
                    row.get("brand_name"),
                    row.get("generic_name"),
                ]

                for value in possible_values:

                    if value:

                        name = normalize_text(
                            str(value)
                        )

                        if name:
                            drug_names.add(name)
                            names_added_this_page += 1

            elif isinstance(row, list):

                for value in row:

                    if isinstance(value, str):

                        name = normalize_text(
                            value
                        )

                        if name:
                            drug_names.add(name)
                            names_added_this_page += 1

        if len(rows) < page_size:
            break

        page += 1


    print(
        f"\nDownloaded {len(drug_names)} unique "
        f"DailyMed drug names."
    )

    return drug_names


def load_drug_preservation_set():
    """
    Load cached DailyMed names if available.
    Otherwise download them once and create the cache.
    """

    if DRUG_CACHE_FILE.exists():

        print(
            "\nLoading medication preservation set "
            "from local cache..."
        )

        with open(
            DRUG_CACHE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            names = json.load(file)

        preservation_set = {
            normalize_text(name)
            for name in names
            if name
        }

        print(
            f"Loaded {len(preservation_set)} "
            f"drug names from cache."
        )

        return preservation_set


    preservation_set = (
        download_dailymed_drug_names()
    )


    with open(
        DRUG_CACHE_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            sorted(preservation_set),
            file,
            indent=2
        )


    print(
        f"Saved drug cache to:\n"
        f"{DRUG_CACHE_FILE}"
    )

    return preservation_set


PRESERVATION_SET = load_drug_preservation_set()


# ------------------------------------------------------
# MEDICATION FAIL-SAFE
# ------------------------------------------------------

def is_preserved_medication(candidate):
    """
    Return True when a redaction candidate matches
    a known medication in the preservation set.
    """

    normalized = normalize_text(candidate)

    if not normalized:
        return False


    # ------------------------------------------
    # Exact medication name match
    # ------------------------------------------

    if normalized in PRESERVATION_SET:
        return True


    # ------------------------------------------
    # Candidate may contain dosage information
    #
    # Example:
    # "Apixaban 2.5 mg"
    #
    # We check whether it begins with a known
    # medication name.
    # ------------------------------------------

    for drug_name in PRESERVATION_SET:

        if len(drug_name) < 3:
            continue

        if normalized.startswith(
            drug_name + " "
        ):
            return True


    return False


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
        r"\b(?:\d{1,3}\.){3}"
        r"\d{1,3}\b"
    ),

    "URL": re.compile(
        r"\b(?:https?://|www\.)"
        r"\S+\b",
        re.IGNORECASE
    ),

    "DATE": re.compile(
        r"\b(?:"
        r"\d{1,2}[/-]"
        r"\d{1,2}[/-]"
        r"\d{2,4}"
        r"|"
        r"(?:Jan(?:uary)?|"
        r"Feb(?:ruary)?|"
        r"Mar(?:ch)?|"
        r"Apr(?:il)?|"
        r"May|"
        r"Jun(?:e)?|"
        r"Jul(?:y)?|"
        r"Aug(?:ust)?|"
        r"Sep(?:tember)?|"
        r"Oct(?:ober)?|"
        r"Nov(?:ember)?|"
        r"Dec(?:ember)?)"
        r"\s+\d{1,2},?"
        r"\s+\d{4}"
        r")\b",
        re.IGNORECASE
    ),

    "ZIP_CODE": re.compile(
        r"\b\d{5}"
        r"(?:-\d{4})?\b"
    ),
}


# ------------------------------------------------------
# FIELD-BASED IDENTIFIERS
# ------------------------------------------------------

FIELD_PATTERNS = {

    "PATIENT_NAME": re.compile(
        r"(?:Patient\s+Name|Name)"
        r"\s*:\s*"
        r"("
        r"[A-Z][A-Za-z'.-]+"
        r"(?:\s+[A-Z][A-Za-z'.-]+){1,3}"
        r")",
        re.IGNORECASE
    ),

    "DOB": re.compile(
        r"(?:DOB|Date\s+of\s+Birth|Birth\s+Date)"
        r"\s*:\s*"
        r"([^\n]+)",
        re.IGNORECASE
    ),

    "MRN": re.compile(
        r"(?:MRN|"
        r"Medical\s+Record(?:\s+Number)?|"
        r"Medical\s+Record\s+#)"
        r"\s*:\s*"
        r"([A-Za-z0-9-]+)",
        re.IGNORECASE
    ),

    "ADDRESS": re.compile(
        r"Address\s*:\s*"
        r"([^\n]+)",
        re.IGNORECASE
    ),

    "RX_NUMBER": re.compile(
        r"(?:Rx|Prescription)"
        r"\s*(?:Number|No\.?|#)?"
        r"\s*:\s*"
        r"([A-Za-z0-9-]+)",
        re.IGNORECASE
    ),

    "ACCOUNT_NUMBER": re.compile(
        r"Account"
        r"\s*(?:Number|No\.?|#)?"
        r"\s*:\s*"
        r"([A-Za-z0-9-]+)",
        re.IGNORECASE
    ),

    "MEMBER_ID": re.compile(
        r"(?:Member|Insurance|Health\s*Plan)"
        r"\s*(?:ID|Number|No\.?|#)"
        r"\s*:\s*"
        r"([A-Za-z0-9-]+)",
        re.IGNORECASE
    ),

    "EMERGENCY_CONTACT": re.compile(
        r"Emergency\s+Contact"
        r"\s*:\s*"
        r"("
        r"[A-Z][A-Za-z'.-]+"
        r"(?:\s+[A-Z][A-Za-z'.-]+){1,3}"
        r")",
        re.IGNORECASE
    ),

    "LICENSE_NUMBER": re.compile(
        r"License\s+"
        r"(?:Number|No\.?|#)"
        r"\s*:\s*"
        r"([A-Za-z0-9-]+)",
        re.IGNORECASE
    ),

    "ADMISSION_DATE": re.compile(
        r"Admission\s+Date"
        r"\s*:\s*"
        r"([^\n]+)",
        re.IGNORECASE
    ),

    "DISCHARGE_DATE": re.compile(
        r"Discharge\s+Date"
        r"\s*:\s*"
        r"([^\n]+)",
        re.IGNORECASE
    ),
}


# ------------------------------------------------------
# REDACTION FUNCTION
# ------------------------------------------------------

def redact_value(
    page,
    value,
    entity_type
):

    value = value.strip()

    if not value:
        return 0


    # ==================================================
    # MEDICATION PRESERVATION FAIL-SAFE
    # ==================================================

    if is_preserved_medication(value):

        print(
            f"PRESERVING [MEDICATION]: "
            f"{value!r}"
        )

        preserved_stats[value] = (
            preserved_stats.get(value, 0)
            + 1
        )

        return 0


    # ==================================================
    # REDACT
    # ==================================================

    rectangles = page.search_for(
        value
    )

    for rect in rectangles:

        page.add_redact_annot(
            rect,
            fill=(0, 0, 0)
        )


    if rectangles:

        print(
            f"REDACTING [{entity_type}]: "
            f"{value!r}"
        )


    return len(rectangles)


# ------------------------------------------------------
# PROCESS PDF
# ------------------------------------------------------

for page_number, page in enumerate(doc):

    text = page.get_text()

    if not text.strip():
        continue


    print(
        f"\nPage {page_number + 1}"
    )


    page_has_redactions = False


    # --------------------------------------------------
    # 1. Structured field-based redaction
    # --------------------------------------------------

    for entity_type, pattern in (
        FIELD_PATTERNS.items()
    ):

        for match in pattern.finditer(
            text
        ):

            value = (
                match.group(1)
                .strip()
            )


            count = redact_value(
                page,
                value,
                entity_type
            )


            if count:

                stats[entity_type] = (
                    stats.get(
                        entity_type,
                        0
                    )
                    + count
                )

                page_has_redactions = True


    # --------------------------------------------------
    # 2. General regex identifiers
    # --------------------------------------------------

    for entity_type, pattern in (
        PATTERNS.items()
    ):

        for match in pattern.finditer(
            text
        ):

            value = match.group()


            count = redact_value(
                page,
                value,
                entity_type
            )


            if count:

                stats[entity_type] = (
                    stats.get(
                        entity_type,
                        0
                    )
                    + count
                )

                page_has_redactions = True


    # --------------------------------------------------
    # 3. Presidio backup
    # --------------------------------------------------

    results = analyzer.analyze(
        text=text,
        entities=[
            "PERSON",
            "EMAIL_ADDRESS",
            "PHONE_NUMBER",
            "US_SSN",
            "IP_ADDRESS",
            "URL"
        ],
        language="en"
    )


    for result in results:

        value = text[
            result.start:
            result.end
        ].strip()


        count = redact_value(
            page,
            value,
            result.entity_type
        )


        if count:

            stats[result.entity_type] = (
                stats.get(
                    result.entity_type,
                    0
                )
                + count
            )

            page_has_redactions = True


    if page_has_redactions:

        page.apply_redactions()


# ------------------------------------------------------
# SAVE
# ------------------------------------------------------

doc.save(
    OUTPUT_PDF,
    garbage=4,
    deflate=True
)

doc.close()


# ------------------------------------------------------
# RESULTS
# ------------------------------------------------------

print(
    "\n================================"
)

print(
    "FINISHED"
)

print(
    "================================"
)


print(
    "\nREDACTION SUMMARY"
)

for entity, count in sorted(
    stats.items()
):

    print(
        f"{entity}: {count}"
    )


print(
    "\nMEDICATIONS PRESERVED"
)

for medication, count in sorted(
    preserved_stats.items()
):

    print(
        f"{medication}: {count}"
    )


print(
    "\nTotal drug names in preservation set:"
)

print(
    len(PRESERVATION_SET)
)


print(
    "\nOutput:"
)

print(
    OUTPUT_PDF
)