import argparse
import csv
import json
from pathlib import Path


LABELS = ["grateful", "satisfied", "sad", "angry"]
LABEL_ALIASES = {
    "grateful": "grateful",
    "satisfied": "satisfied",
    "sad": "sad",
    "angry": "angry",
    "love": "grateful",
    "happy": "satisfied",
}


def normalize_label(raw_label: str) -> str:
    label = str(raw_label or "").strip().lower()
    normalized = LABEL_ALIASES.get(label)
    if not normalized:
        raise ValueError(f"Unsupported label: {raw_label!r}")
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a manually labeled CSV into the emotion-model JSONL/CSV training format."
    )
    parser.add_argument("--input-csv", default="all_feedback_captions_balanced.csv")
    parser.add_argument("--output-dir", default="emotion-model/exports")
    parser.add_argument("--output-name", default="manual_balanced_feedback_labels")
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    if not rows:
        raise SystemExit("Input CSV is empty.")

    jsonl_path = output_dir / f"{args.output_name}.jsonl"
    csv_path = output_dir / f"{args.output_name}.csv"
    report_path = output_dir / f"{args.output_name}_report.json"

    dataset_rows = []
    class_counts = {label: 0 for label in LABELS}

    for index, row in enumerate(rows, start=1):
        text = str(row.get("feedback_text") or row.get("text") or "").strip()
        if not text:
            continue

        label = normalize_label(row.get("emotion_label") or row.get("label"))
        dataset_row = {
            "id": row.get("id") or f"manual-{index:04d}",
            "text": text,
            "label": label,
            "confidence": 1.0,
            "reaction_total": None,
            "type": row.get("type"),
            "service": row.get("service"),
            "barangay": row.get("barangay"),
            "created_at": row.get("created_at"),
            "breakdown": None,
            "label_source": "manual_balanced_csv",
            "source_file": input_path.name,
        }
        dataset_rows.append(dataset_row)
        class_counts[label] += 1

    if not dataset_rows:
        raise SystemExit("No valid labeled rows were found in the input CSV.")

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in dataset_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "id",
                "text",
                "label",
                "confidence",
                "reaction_total",
                "type",
                "service",
                "barangay",
                "created_at",
                "label_source",
                "source_file",
            ],
        )
        writer.writeheader()
        for row in dataset_rows:
            writer.writerow(
                {
                    "id": row["id"],
                    "text": row["text"],
                    "label": row["label"],
                    "confidence": row["confidence"],
                    "reaction_total": row["reaction_total"],
                    "type": row["type"],
                    "service": row["service"],
                    "barangay": row["barangay"],
                    "created_at": row["created_at"],
                    "label_source": row["label_source"],
                    "source_file": row["source_file"],
                }
            )

    report_path.write_text(
        json.dumps(
            {
                "rows": len(dataset_rows),
                "class_counts": class_counts,
                "source_file": str(input_path),
                "label_source": "manual_balanced_csv",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "rows": len(dataset_rows),
                "class_counts": class_counts,
                "jsonl": str(jsonl_path),
                "csv": str(csv_path),
                "report": str(report_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
