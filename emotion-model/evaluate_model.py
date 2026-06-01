import argparse
import json
from pathlib import Path

from sklearn.metrics import classification_report, confusion_matrix
from transformers import AutoModelForSequenceClassification, AutoTokenizer, TextClassificationPipeline


LABELS = ["grateful", "satisfied", "sad", "angry"]
DEFAULT_DATASET = Path("emotion-model/exports/feedback_reaction_labels.jsonl")
DEFAULT_FALLBACK_DATASET = Path("emotion-model/exports/manual_balanced_feedback_labels.jsonl")


def load_rows(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def resolve_dataset_path(dataset_arg: str) -> Path:
    requested_path = Path(dataset_arg)
    if requested_path != DEFAULT_DATASET:
        return requested_path

    if requested_path.exists() and requested_path.stat().st_size > 0:
        return requested_path

    if DEFAULT_FALLBACK_DATASET.exists() and DEFAULT_FALLBACK_DATASET.stat().st_size > 0:
        print(
            f"Primary dataset is empty or missing at {requested_path}. "
            f"Falling back to {DEFAULT_FALLBACK_DATASET}."
        )
        return DEFAULT_FALLBACK_DATASET

    return requested_path


def extract_scores(raw_output):
    if isinstance(raw_output, list) and raw_output and isinstance(raw_output[0], list):
        return raw_output[0]
    if isinstance(raw_output, list) and raw_output and isinstance(raw_output[0], dict):
        return raw_output
    if isinstance(raw_output, dict):
        return [raw_output]
    raise TypeError(f"Unsupported pipeline output shape: {type(raw_output).__name__}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate a trained mood classifier.")
    parser.add_argument("--model-dir", default="emotion-model/checkpoints/xlm-roberta-base/best")
    parser.add_argument("--dataset", default="emotion-model/exports/feedback_reaction_labels.jsonl")
    parser.add_argument("--output", default="emotion-model/checkpoints/xlm-roberta-base/evaluation.json")
    args = parser.parse_args()

    rows = load_rows(resolve_dataset_path(args.dataset))
    tokenizer = AutoTokenizer.from_pretrained(args.model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(args.model_dir)
    pipeline = TextClassificationPipeline(model=model, tokenizer=tokenizer, top_k=None)

    truths = []
    predictions = []

    for row in rows:
        scores = extract_scores(pipeline(row["text"], truncation=True, max_length=256))
        best = max(scores, key=lambda item: item["score"])
        truths.append(row["label"])
        predictions.append(best["label"].lower())

    report = classification_report(truths, predictions, labels=LABELS, output_dict=True, zero_division=0)
    matrix = confusion_matrix(truths, predictions, labels=LABELS)

    payload = {
        "classification_report": report,
        "confusion_matrix": matrix.tolist(),
        "labels": LABELS,
    }
    Path(args.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
