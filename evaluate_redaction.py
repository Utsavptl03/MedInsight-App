from pathlib import Path
import json
import pymupdf


# ------------------------------------------------------
# PATHS
# ------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

GROUND_TRUTH_FILE = (
    BASE_DIR
    / "medrec_phi_redaction_test_dataset"
    / "ground_truth.json"
)

OUTPUT_FOLDER = BASE_DIR / "output"


# ------------------------------------------------------
# LOAD GROUND TRUTH
# ------------------------------------------------------

with open(
    GROUND_TRUTH_FILE,
    "r",
    encoding="utf-8"
) as file:

    ground_truth = json.load(file)


# ------------------------------------------------------
# HELPER: EXTRACT TEXT FROM PDF
# ------------------------------------------------------

def extract_pdf_text(pdf_path):

    doc = pymupdf.open(pdf_path)

    full_text = []

    for page in doc:

        full_text.append(
            page.get_text()
        )

    doc.close()

    return "\n".join(full_text)


# ------------------------------------------------------
# COUNTERS
# ------------------------------------------------------

total_phi = 0
correctly_redacted_phi = 0
missed_phi = 0

total_medications = 0
preserved_medications = 0
removed_medications = 0


results = []


# ------------------------------------------------------
# EVALUATE EACH FILE
# ------------------------------------------------------

for case in ground_truth["cases"]:

    input_name = case["file"]

    output_name = (
        "redacted_"
        + input_name
    )

    output_pdf = (
        OUTPUT_FOLDER
        / output_name
    )


    if not output_pdf.exists():

        print(
            f"WARNING: Missing output file: "
            f"{output_pdf.name}"
        )

        continue


    text = extract_pdf_text(
        output_pdf
    )


    text_lower = text.lower()


    # --------------------------------------------------
    # PHI EVALUATION
    # --------------------------------------------------

    phi_values = case[
        "phi_values"
    ]


    phi_correct = 0
    phi_missed = 0


    for value in phi_values:

        total_phi += 1

        if value.lower() not in text_lower:

            correctly_redacted_phi += 1
            phi_correct += 1

        else:

            missed_phi += 1
            phi_missed += 1


    # --------------------------------------------------
    # MEDICATION PRESERVATION
    # --------------------------------------------------

    medications = case[
        "medications_to_preserve"
    ]


    meds_preserved = 0
    meds_removed = 0


    for medication in medications:

        total_medications += 1

        if medication.lower() in text_lower:

            preserved_medications += 1
            meds_preserved += 1

        else:

            removed_medications += 1
            meds_removed += 1


    # --------------------------------------------------
    # STORE RESULT
    # --------------------------------------------------

    result = {

        "file": input_name,

        "phi_total": len(
            phi_values
        ),

        "phi_redacted": phi_correct,

        "phi_missed": phi_missed,

        "medications_total": len(
            medications
        ),

        "medications_preserved":
            meds_preserved,

        "medications_removed":
            meds_removed
    }


    results.append(
        result
    )


# ------------------------------------------------------
# CALCULATE METRICS
# ------------------------------------------------------

if total_phi > 0:

    phi_recall = (
        correctly_redacted_phi
        / total_phi
    )

else:

    phi_recall = 0


if total_medications > 0:

    medication_preservation_accuracy = (
        preserved_medications
        / total_medications
    )

else:

    medication_preservation_accuracy = 0


# ------------------------------------------------------
# DISPLAY PER-FILE RESULTS
# ------------------------------------------------------

print(
    "\n================================"
)

print(
    "PER-FILE RESULTS"
)

print(
    "================================"
)


for result in results:

    print(
        f"\n{result['file']}"
    )

    print(
        f"PHI redacted: "
        f"{result['phi_redacted']}"
        f"/{result['phi_total']}"
    )

    print(
        f"PHI missed: "
        f"{result['phi_missed']}"
    )

    print(
        f"Medications preserved: "
        f"{result['medications_preserved']}"
        f"/{result['medications_total']}"
    )

    print(
        f"Medications removed incorrectly: "
        f"{result['medications_removed']}"
    )


# ------------------------------------------------------
# FINAL SUMMARY
# ------------------------------------------------------

print(
    "\n\n================================"
)

print(
    "FINAL EVALUATION"
)

print(
    "================================"
)


print(
    f"\nTotal PHI items: "
    f"{total_phi}"
)

print(
    f"Correctly redacted PHI: "
    f"{correctly_redacted_phi}"
)

print(
    f"Missed PHI: "
    f"{missed_phi}"
)

print(
    f"\nPHI Recall: "
    f"{phi_recall * 100:.2f}%"
)


print(
    f"\nTotal medications: "
    f"{total_medications}"
)

print(
    f"Medications preserved: "
    f"{preserved_medications}"
)

print(
    f"Medications incorrectly removed: "
    f"{removed_medications}"
)

print(
    f"\nMedication Preservation Accuracy: "
    f"{medication_preservation_accuracy * 100:.2f}%"
)