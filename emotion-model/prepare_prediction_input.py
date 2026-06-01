import argparse
import csv
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert a feedback CSV export into JSONL input for predict_mood.py.")
    parser.add_argument("--input-csv", default="emotion-model/exports/all_feedback_captions.csv")
    parser.add_argument("--output-jsonl", default="emotion-model/exports/all_feedback_captions.jsonl")
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    output_path = Path(args.output_jsonl)

    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    if not rows:
        raise SystemExit("Input CSV is empty.")

    written = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            feedback_id = str(row.get("id") or "").strip()
            text = str(row.get("feedback_text") or row.get("text") or "").strip()
            if not feedback_id or not text:
                continue
            handle.write(
                json.dumps(
                    {
                        "id": feedback_id,
                        "text": text,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            written += 1

    print(
        json.dumps(
            {
                "input_csv": str(input_path),
                "output_jsonl": str(output_path),
                "rows_written": written,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
