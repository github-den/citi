import argparse
import csv
from pathlib import Path


def load_audit_rows(audit_path: Path, min_confidence: str):
    allowed = {"high"} if min_confidence == "high" else {"high", "medium"}
    updates = {}
    with audit_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            confidence = (row.get("confidence") or "").strip().lower()
            if confidence not in allowed:
                continue
            row_number = int(row["row_number"])
            updates[row_number] = {
                "current_label": row["current_label"].strip().lower(),
                "suggested_label": row["suggested_label"].strip().lower(),
                "confidence": confidence,
                "reason": (row.get("reason") or "").strip(),
            }
    return updates


def main():
    parser = argparse.ArgumentParser(description="Apply audited relabel suggestions to a CSV without overwriting the source.")
    parser.add_argument("--input-csv", default="all_feedback_captions_balanced.csv")
    parser.add_argument("--audit-csv", default="emotion-model/exports/balanced_label_audit_round1.csv")
    parser.add_argument("--output-csv", default="emotion-model/exports/all_feedback_captions_balanced_round1.csv")
    parser.add_argument(
        "--min-confidence",
        choices=["high", "medium"],
        default="high",
        help="Apply only high-confidence updates, or both high and medium updates.",
    )
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    audit_path = Path(args.audit_csv)
    output_path = Path(args.output_csv)

    updates = load_audit_rows(audit_path, args.min_confidence)

    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    label_field = "emotion_label" if "emotion_label" in fieldnames else "label"
    applied = 0

    for row_number, row in enumerate(rows, start=1):
        update = updates.get(row_number)
        if not update:
            continue

        current_label = (row.get(label_field) or "").strip().lower()
        if current_label != update["current_label"]:
            raise ValueError(
                f"Row {row_number} label mismatch: expected {update['current_label']!r}, found {current_label!r}."
            )

        row[label_field] = update["suggested_label"]
        applied += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(
        {
            "input_csv": str(input_path),
            "audit_csv": str(audit_path),
            "output_csv": str(output_path),
            "applied_updates": applied,
            "min_confidence": args.min_confidence,
        }
    )


if __name__ == "__main__":
    main()
