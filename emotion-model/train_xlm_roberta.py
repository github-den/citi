import argparse
import inspect
import json
from collections import Counter
from pathlib import Path

import evaluate
import numpy as np
from datasets import Dataset, DatasetDict
from sklearn.model_selection import train_test_split
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)


LABELS = ["grateful", "satisfied", "sad", "angry"]
LABEL_TO_ID = {label: index for index, label in enumerate(LABELS)}
ID_TO_LABEL = {index: label for label, index in LABEL_TO_ID.items()}
MIN_STRATIFIED_CLASS_COUNT = 2
DEFAULT_DATASET = Path("emotion-model/exports/feedback_reaction_labels.jsonl")
DEFAULT_FALLBACK_DATASET = Path("emotion-model/exports/manual_balanced_feedback_labels.jsonl")


def build_training_arguments(output_dir: Path, args):
    training_kwargs = {
        "output_dir": str(output_dir),
        "save_strategy": "epoch",
        "logging_strategy": "epoch",
        "learning_rate": args.learning_rate,
        "per_device_train_batch_size": args.batch_size,
        "per_device_eval_batch_size": args.batch_size,
        "num_train_epochs": args.epochs,
        "weight_decay": 0.01,
        "load_best_model_at_end": True,
        "metric_for_best_model": "macro_f1",
        "greater_is_better": True,
        "save_total_limit": 2,
        "report_to": [],
        "do_train": True,
        "do_eval": True,
    }

    training_signature = inspect.signature(TrainingArguments.__init__)
    if "evaluation_strategy" in training_signature.parameters:
        training_kwargs["evaluation_strategy"] = "epoch"
    else:
        training_kwargs["eval_strategy"] = "epoch"

    return TrainingArguments(**training_kwargs)


def build_trainer(model, training_args, tokenized, tokenizer, data_collator, compute_metrics):
    trainer_kwargs = {
        "model": model,
        "args": training_args,
        "train_dataset": tokenized["train"],
        "eval_dataset": tokenized["validation"],
        "data_collator": data_collator,
        "compute_metrics": compute_metrics,
    }

    trainer_signature = inspect.signature(Trainer.__init__)
    processor_arg_names = []
    if "processing_class" in trainer_signature.parameters:
        processor_arg_names.append("processing_class")
    if "tokenizer" in trainer_signature.parameters:
        processor_arg_names.append("tokenizer")

    for arg_name in processor_arg_names:
        try:
            return Trainer(**trainer_kwargs, **{arg_name: tokenizer})
        except TypeError as error:
            if f"unexpected keyword argument '{arg_name}'" not in str(error):
                raise

    return Trainer(**trainer_kwargs)


def load_rows(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    if not rows:
        raise ValueError(f"Dataset is empty: {path}")
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


def summarize_rows(rows):
    label_counts = Counter(row["label"] for row in rows)
    return {
        "total_rows": len(rows),
        "label_counts": {label: label_counts.get(label, 0) for label in LABELS},
        "missing_labels": [label for label in LABELS if label_counts.get(label, 0) == 0],
        "small_labels": [label for label in LABELS if 0 < label_counts.get(label, 0) < MIN_STRATIFIED_CLASS_COUNT],
    }


def ensure_trainable_or_exit(summary, allow_debug_small_dataset):
    if not summary["missing_labels"] and not summary["small_labels"]:
        return

    message = {
        "error": "Dataset is too small or incomplete for real stratified training.",
        "total_rows": summary["total_rows"],
        "label_counts": summary["label_counts"],
        "missing_labels": summary["missing_labels"],
        "small_labels": summary["small_labels"],
        "next_step": (
            "Collect more reaction-labeled feedback first, or rerun with "
            "--allow-debug-small-dataset for a smoke-test-only training run."
        ),
    }
    if not allow_debug_small_dataset:
        raise SystemExit(json.dumps(message, indent=2))


def build_splits(rows, allow_debug_small_dataset=False):
    labels = [row["label"] for row in rows]
    summary = summarize_rows(rows)
    ensure_trainable_or_exit(summary, allow_debug_small_dataset)

    if summary["missing_labels"] or summary["small_labels"]:
        shuffled = list(rows)
        rng = np.random.default_rng(42)
        rng.shuffle(shuffled)
        total = len(shuffled)
        test_size = 1 if total >= 3 else 0
        validation_size = 1 if total >= 4 else 0
        train_size = max(total - validation_size - test_size, 1)
        train_rows = shuffled[:train_size]
        val_rows = shuffled[train_size:train_size + validation_size]
        test_rows = shuffled[train_size + validation_size:]
    else:
        train_rows, temp_rows, _, temp_labels = train_test_split(
            rows,
            labels,
            test_size=0.3,
            random_state=42,
            stratify=labels,
        )
        val_rows, test_rows = train_test_split(
            temp_rows,
            test_size=0.5,
            random_state=42,
            stratify=temp_labels,
        )

    def to_dataset(split_rows):
        return Dataset.from_list(
            [
                {
                    "text": row["text"],
                    "label": LABEL_TO_ID[row["label"]],
                    "id": row["id"],
                }
                for row in split_rows
            ]
        )

    return DatasetDict(
        train=to_dataset(train_rows),
        validation=to_dataset(val_rows),
        test=to_dataset(test_rows),
    )


def compute_metrics_builder():
    accuracy = evaluate.load("accuracy")
    precision = evaluate.load("precision")
    recall = evaluate.load("recall")
    f1 = evaluate.load("f1")

    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        predictions = np.argmax(logits, axis=-1)
        return {
            "accuracy": accuracy.compute(predictions=predictions, references=labels)["accuracy"],
            "macro_precision": precision.compute(predictions=predictions, references=labels, average="macro")["precision"],
            "macro_recall": recall.compute(predictions=predictions, references=labels, average="macro")["recall"],
            "macro_f1": f1.compute(predictions=predictions, references=labels, average="macro")["f1"],
        }

    return compute_metrics


def main():
    parser = argparse.ArgumentParser(description="Train xlm-roberta-base for 4-class mood detection.")
    parser.add_argument("--dataset", default="emotion-model/exports/feedback_reaction_labels.jsonl")
    parser.add_argument("--output-dir", default="emotion-model/checkpoints/xlm-roberta-base")
    parser.add_argument("--model-name", default="xlm-roberta-base")
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument(
        "--allow-debug-small-dataset",
        action="store_true",
        help="Allow a smoke-test-only training run with a tiny or incomplete dataset.",
    )
    args = parser.parse_args()

    dataset_path = resolve_dataset_path(args.dataset)
    rows = load_rows(dataset_path)
    dataset = build_splits(rows, allow_debug_small_dataset=args.allow_debug_small_dataset)
    dataset_summary = summarize_rows(rows)

    tokenizer = AutoTokenizer.from_pretrained(args.model_name)

    def tokenize(batch):
        return tokenizer(batch["text"], truncation=True, max_length=256)

    tokenized = dataset.map(tokenize, batched=True)
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_name,
        num_labels=len(LABELS),
        id2label=ID_TO_LABEL,
        label2id=LABEL_TO_ID,
    )

    output_dir = Path(args.output_dir)
    training_args = build_training_arguments(output_dir, args)

    trainer = build_trainer(
        model=model,
        training_args=training_args,
        tokenized=tokenized,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics_builder(),
    )

    trainer.train()
    test_metrics = trainer.evaluate(tokenized["test"])

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "dataset_summary.json").write_text(
        json.dumps(
            {
                **dataset_summary,
                "allow_debug_small_dataset": args.allow_debug_small_dataset,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "label_map.json").write_text(
        json.dumps({"labels": LABELS, "label_to_id": LABEL_TO_ID}, indent=2),
        encoding="utf-8",
    )
    (output_dir / "test_metrics.json").write_text(json.dumps(test_metrics, indent=2), encoding="utf-8")
    trainer.save_model(str(output_dir / "best"))
    tokenizer.save_pretrained(str(output_dir / "best"))


if __name__ == "__main__":
    main()
