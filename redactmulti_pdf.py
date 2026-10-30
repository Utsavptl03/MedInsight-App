print("Script Started")

from pathlib import Path
import json

import pymupdf
import spacy


# ------------------------------------------------------
# PATHS
# ------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

INPUT_FOLDER = (
    BASE_DIR
    / "med7_test_dataset_v2_download"
)

OUTPUT_FOLDER = (
    BASE_DIR
    / "output"
)

DRUG_CACHE_FILE = (
    BASE_DIR
    / "drug_preservation_set.json"
)

OUTPUT_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)


# ------------------------------------------------------
# SETTINGS
# ------------------------------------------------------

# True:
# Med7 must detect a DRUG AND DailyMed must confirm it.
#
# False:
# Trust Med7 DRUG detection by itself.

REQUIRE_DAILYMED_CONFIRMATION = True


# ------------------------------------------------------
# LOAD LOCAL MED7 MODEL
# ------------------------------------------------------

print("\nLoading local Med7 model...")

try:

    MED7_MODEL_PATH = (
        BASE_DIR
        / "med7_finetune_package_updated"
        / "med7_finetuned"
        / "best"
    )

    med7 = spacy.load(
    MED7_MODEL_PATH
    )

except OSError:

    raise RuntimeError(
        "\nMed7 model is not installed.\n"
        "Install en_core_med7_lg first, "
        "then run this script again."
    )


print("Med7 loaded successfully.")


# ------------------------------------------------------
# MED7 MEDICATION ENTITY TYPES
# ------------------------------------------------------

MEDICATION_ENTITIES = {

    "DRUG",

    "STRENGTH",

    "DOSAGE",

    "DURATION",

    "FREQUENCY",

    "FORM",

    "ROUTE",
}


# ------------------------------------------------------
# NORMALIZE TEXT
#
# NO REGEX
# ------------------------------------------------------

def normalize_text(value):

    value = (
        value
        .lower()
        .strip()
    )

    # Collapse repeated whitespace
    # without regular expressions.

    value = " ".join(
        value.split()
    )

    value = value.strip(
        ".,;:()[]{}\"'"
    )

    return value


# ------------------------------------------------------
# LOAD LOCAL DAILYMED CACHE
#
# IMPORTANT:
# NO NETWORK REQUEST IS MADE.
# ------------------------------------------------------

def load_drug_preservation_set():

    if not DRUG_CACHE_FILE.exists():

        raise FileNotFoundError(
            "\nLocal DailyMed drug cache "
            "was not found:\n"
            f"{DRUG_CACHE_FILE}\n\n"
            "The new pipeline is configured "
            "to run locally."
        )


    print(
        "\nLoading local DailyMed "
        "drug preservation set..."
    )


    with open(
        DRUG_CACHE_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        names = json.load(
            file
        )


    preservation_set = {

        normalize_text(
            str(name)
        )

        for name in names

        if name
    }


    print(
        "Loaded "
        f"{len(preservation_set)} "
        "drug names."
    )


    return preservation_set


PRESERVATION_SET = (
    load_drug_preservation_set()
)


# ------------------------------------------------------
# DAILYMED DRUG VALIDATION
#
# NO REGEX
# ------------------------------------------------------

def is_known_medication(
    candidate
):

    normalized = normalize_text(
        candidate
    )


    if not normalized:

        return False


    # Exact match

    if normalized in PRESERVATION_SET:

        return True


    # --------------------------------------------------
    # Handle longer DailyMed names.
    #
    # Example:
    #
    # detected:
    # lisinopril
    #
    # cache might contain:
    # lisinopril tablet
    # --------------------------------------------------

    for drug_name in PRESERVATION_SET:

        if not drug_name:

            continue


        if drug_name.startswith(
            normalized + " "
        ):

            return True


        if normalized.startswith(
            drug_name + " "
        ):

            return True


    return False


# ------------------------------------------------------
# BUILD FLATTENED PAGE
#
# We flatten directly from PyMuPDF words.
#
# This also stores each word's PDF coordinates.
# ------------------------------------------------------

def build_flattened_page(
    page
):

    words = page.get_text(
        "words",
        sort=True
    )


    flattened_parts = []

    word_map = []

    current_position = 0


    for word in words:

        word_text = str(
            word[4]
        ).strip()


        if not word_text:

            continue


        # One space between PDF words

        if flattened_parts:

            current_position += 1


        start = current_position


        flattened_parts.append(
            word_text
        )


        current_position += len(
            word_text
        )


        end = current_position


        word_map.append({

            "start": start,

            "end": end,

            "text": word_text,

            "rect": pymupdf.Rect(
                word[0],
                word[1],
                word[2],
                word[3]
            )
        })


    flattened_text = " ".join(
        flattened_parts
    )


    return (
        flattened_text,
        word_map
    )


# ------------------------------------------------------
# CHECK TEXT-SPAN / PDF-WORD OVERLAP
# ------------------------------------------------------

def spans_overlap(
    start1,
    end1,
    start2,
    end2
):

    return (
        end1 > start2
        and
        start1 < end2
    )


# ------------------------------------------------------
# FIND MEDICATION INFORMATION
# ------------------------------------------------------

def find_medication_spans(
    flattened_text
):

    # --------------------------------------------------
    # Run local clinical NLP model
    # --------------------------------------------------

    doc = med7(
        flattened_text
    )


    entities = list(
        doc.ents
    )


    print(
        "\nMed7 detected:"
    )


    if not entities:

        print(
            "  No medication entities detected."
        )


    for entity in entities:

        print(
            f"  {entity.label_:10} "
            f"{entity.text!r}"
        )


    # --------------------------------------------------
    # First find validated drugs.
    # --------------------------------------------------

    accepted_drugs = []


    for entity in entities:

        if entity.label_ != "DRUG":

            continue


        if REQUIRE_DAILYMED_CONFIRMATION:

            valid = is_known_medication(
                entity.text
            )

        else:

            valid = True


        if valid:

            accepted_drugs.append(
                entity
            )


            print(
                "  CONFIRMED DRUG: "
                f"{entity.text!r}"
            )

        else:

            print(
                "  REJECTED DRUG: "
                f"{entity.text!r}"
            )


    # --------------------------------------------------
    # If no validated drug exists,
    # preserve nothing.
    # --------------------------------------------------

    if not accepted_drugs:

        return []


    # --------------------------------------------------
    # Medication spans that will be preserved.
    #
    # A span is kept only when it is one of Med7's
    # medication-specific entities.
    # --------------------------------------------------

    medication_spans = []


    for entity in entities:

        if (
            entity.label_
            not in MEDICATION_ENTITIES
        ):

            continue


        # --------------------------------------------------
        # DRUG entities themselves must be validated.
        # --------------------------------------------------

        if entity.label_ == "DRUG":

            accepted = False


            for drug in accepted_drugs:

                if (
                    drug.start_char
                    == entity.start_char

                    and

                    drug.end_char
                    == entity.end_char
                ):

                    accepted = True

                    break


            if not accepted:

                continue


        medication_spans.append({

            "start": entity.start_char,

            "end": entity.end_char,

            "label": entity.label_,

            "text": entity.text
        })


    return medication_spans


# ------------------------------------------------------
# GET WORDS WHICH SHOULD BE PRESERVED
# ------------------------------------------------------

def get_preserved_word_indexes(
    medication_spans,
    word_map
):

    preserved_indexes = set()


    for span in medication_spans:

        for index, word in enumerate(
            word_map
        ):

            if spans_overlap(

                span["start"],
                span["end"],

                word["start"],
                word["end"]
            ):

                preserved_indexes.add(
                    index
                )


    return preserved_indexes


# ------------------------------------------------------
# REDACT EVERYTHING EXCEPT MEDICATION
# ------------------------------------------------------

def redact_non_medication_words(
    page,
    word_map,
    preserved_indexes
):

    redacted_count = 0


    for index, word in enumerate(
        word_map
    ):

        # Medication information survives

        if index in preserved_indexes:

            continue


        # Everything else is black-redacted

        page.add_redact_annot(
            word["rect"],
            fill=(
                0,
                0,
                0
            )
        )


        redacted_count += 1


    return redacted_count


# ------------------------------------------------------
# FAIL-CLOSED REDACTION
#
# If a page has no extractable text,
# redact the entire page.
# ------------------------------------------------------

def redact_entire_page(
    page
):

    page.add_redact_annot(
        page.rect,
        fill=(
            0,
            0,
            0
        )
    )


    page.apply_redactions()


# ------------------------------------------------------
# PROCESS ONE PDF
# ------------------------------------------------------

def process_pdf(
    input_pdf
):

    print(
        "\n\n"
        "================================"
    )


    print(
        "PROCESSING: "
        f"{input_pdf.name}"
    )


    print(
        "================================"
    )


    output_pdf = (

        OUTPUT_FOLDER

        / f"medication_only_{input_pdf.name}"
    )


    doc = pymupdf.open(
        input_pdf
    )


    total_preserved_words = 0

    total_redacted_words = 0


    # --------------------------------------------------
    # PROCESS EACH PAGE
    # --------------------------------------------------

    for page_number, page in enumerate(
        doc
    ):

        print(
            "\n--------------------------------"
        )


        print(
            "Page "
            f"{page_number + 1}"
        )


        print(
            "--------------------------------"
        )


        # --------------------------------------------------
        # FLATTEN PAGE
        # --------------------------------------------------

        (
            flattened_text,
            word_map

        ) = build_flattened_page(
            page
        )


        # --------------------------------------------------
        # NO EXTRACTABLE TEXT
        #
        # Fail closed.
        # --------------------------------------------------

        if not flattened_text:

            print(
                "No extractable text."
            )


            print(
                "Redacting entire page."
            )


            redact_entire_page(
                page
            )


            continue


        print(
            "\nFlattened text:"
        )


        print(
            flattened_text
        )


        # --------------------------------------------------
        # NLP MEDICATION DETECTION
        # --------------------------------------------------

        medication_spans = (
            find_medication_spans(
                flattened_text
            )
        )


        # --------------------------------------------------
        # NO VALID MEDICATION
        #
        # Nothing is allowed to survive.
        # --------------------------------------------------

        if not medication_spans:

            print(
                "\nNo validated medication "
                "information found."
            )


            print(
                "Redacting all page text."
            )


            preserved_indexes = set()


        else:

            print(
                "\nMedication information "
                "being preserved:"
            )


            for span in medication_spans:

                print(
                    f"  [{span['label']}] "
                    f"{span['text']!r}"
                )


            preserved_indexes = (
                get_preserved_word_indexes(
                    medication_spans,
                    word_map
                )
            )


        # --------------------------------------------------
        # REDACT ALL NON-MEDICATION WORDS
        # --------------------------------------------------

        redacted_count = (
            redact_non_medication_words(
                page,
                word_map,
                preserved_indexes
            )
        )


        total_redacted_words += (
            redacted_count
        )


        total_preserved_words += len(
            preserved_indexes
        )


        # --------------------------------------------------
        # APPLY REDACTIONS
        # --------------------------------------------------

        if redacted_count:

            page.apply_redactions()


        print(
            "\nPreserved words: "
            f"{len(preserved_indexes)}"
        )


        print(
            "Redacted words: "
            f"{redacted_count}"
        )


    # --------------------------------------------------
    # SAVE RESULT
    # --------------------------------------------------

    doc.save(
        output_pdf,
        garbage=4,
        deflate=True
    )


    doc.close()


    # --------------------------------------------------
    # SUMMARY
    # --------------------------------------------------

    print(
        "\n================================"
    )


    print(
        "FILE SUMMARY"
    )


    print(
        "================================"
    )


    print(
        "Medication words preserved: "
        f"{total_preserved_words}"
    )


    print(
        "Other words redacted: "
        f"{total_redacted_words}"
    )


    print(
        "\nOutput:"
    )


    print(
        output_pdf
    )


# ------------------------------------------------------
# PROCESS ALL PDF FILES
# ------------------------------------------------------

pdf_files = sorted(

    INPUT_FOLDER.glob(
        "*.pdf"
    )
)


if not pdf_files:

    raise FileNotFoundError(

        "No PDF files found in:\n"
        f"{INPUT_FOLDER}"
    )


print(
    "\nFound "
    f"{len(pdf_files)} "
    "PDF files."
)


for pdf_file in pdf_files:

    process_pdf(
        pdf_file
    )


# ------------------------------------------------------
# FINAL
# ------------------------------------------------------

print(
    "\n\n"
    "================================"
)


print(
    "ALL FILES FINISHED"
)


print(
    "================================"
)


print(
    "\nProcessed PDFs: "
    f"{len(pdf_files)}"
)


print(
    "\nDrug names available locally: "
    f"{len(PRESERVATION_SET)}"
)


print(
    "\nOutput folder:"
)


print(
    OUTPUT_FOLDER
)