import json
from pathlib import Path
import spacy
from spacy.tokens import DocBin

BASE = Path(__file__).resolve().parent

def convert(jsonl_path, output_path):
    nlp = spacy.load("en_core_med7_lg")
    doc_bin = DocBin()

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            row = json.loads(line)
            text = row["text"]
            doc = nlp.make_doc(text)

            spans = []
            for start, end, label in row["entities"]:
                span = doc.char_span(
                    start,
                    end,
                    label=label,
                    alignment_mode="strict"
                )
                if span is None:
                    raise ValueError(
                        f"Could not align entity on line {line_no}: "
                        f"{text[start:end]!r} ({start}, {end}, {label})"
                    )
                spans.append(span)

            doc.ents = spans
            doc_bin.add(doc)

    doc_bin.to_disk(output_path)
    print(f"Saved: {output_path}")

convert(BASE / "train.jsonl", BASE / "train.spacy")
convert(BASE / "dev.jsonl", BASE / "dev.spacy")
