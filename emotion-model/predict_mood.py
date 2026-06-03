import argparse
import json
from pathlib import Path

from transformers import AutoModelForSequenceClassification, AutoTokenizer, TextClassificationPipeline


def extract_scores(raw_output):
    if isinstance(raw_output, list) and raw_output and isinstance(raw_output[0], list):
        return raw_output[0]
    if isinstance(raw_output, list) and raw_output and isinstance(raw_output[0], dict):
        return raw_output
    if isinstance(raw_output, dict):
        return [raw_output]
    raise TypeError(f"Unsupported pipeline output shape: {type(raw_output).__name__}")


def resolve_model_version(model_id: str) -> str:
    # Extract the last part of the model ID as the version name
    return model_id.split("/")[-1] if "/" in model_id else model_id


def to_breakdown(scores):
    breakdown = {
        "grateful": 0.0,
        "satisfied": 0.0,
        "sad": 0.0,
        "angry": 0.0,
    }
    for item in scores:
        label = str(item.get("label") or "").lower()
        if label in breakdown:
            breakdown[label] = round(float(item.get("score") or 0.0), 6)
    return breakdown


def main():
    parser = argparse.ArgumentParser(description="Predict 4-class mood labels from feedback text.")
    parser.add_argument("--model-id", default="citisense/emotion-detection", help="Hugging Face model ID or local path")
    parser.add_argument("--text", help="Predict one text directly.")
    parser.add_argument("--input-jsonl", help="Predict a batch of rows with {id,text}.")
    parser.add_argument("--output-jsonl", default="emotion-model/exports/predicted_moods.jsonl")
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model_id)
    model = AutoModelForSequenceClassification.from_pretrained(args.model_id)
    pipeline = TextClassificationPipeline(model=model, tokenizer=tokenizer, top_k=None)
    model_version = resolve_model_version(args.model_id)

    if args.text:
        scores = extract_scores(pipeline(args.text, truncation=True, max_length=256))
        best = max(scores, key=lambda item: item["score"])
        print(json.dumps({
            "mood": best["label"].lower(),
            "confidence": round(float(best["score"]), 6),
            "breakdown": to_breakdown(scores),
            "model_version": model_version,
        }, indent=2))
        return

    if not args.input_jsonl:
        raise SystemExit("Provide --text or --input-jsonl.")

    input_rows = []
    with Path(args.input_jsonl).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                input_rows.append(json.loads(line))

    with Path(args.output_jsonl).open("w", encoding="utf-8") as handle:
        for row in input_rows:
            scores = extract_scores(pipeline(row["text"], truncation=True, max_length=256))
            best = max(scores, key=lambda item: item["score"])
            payload = {
                "id": row.get("id"),
                "text": row.get("text"),
                "predicted_mood": best["label"].lower(),
                "predicted_mood_confidence": round(float(best["score"]), 6),
                "predicted_mood_breakdown": to_breakdown(scores),
                "prediction_model_version": model_version,
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
