import argparse
import json
import os
from pathlib import Path
from typing import List

import requests
from transformers import AutoModelForSequenceClassification, AutoTokenizer, TextClassificationPipeline


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
MODEL_VERSION = "xlm-roberta-base-round1"
DEFAULT_MODEL_DIR = REPO_ROOT / "emotion-model" / "checkpoints" / MODEL_VERSION / "best"
ENV_CANDIDATE_PATHS = [
    REPO_ROOT / ".env",
    SCRIPT_DIR / ".env",
    REPO_ROOT / "emotion-model" / ".env",
    REPO_ROOT / "admin-web" / ".env",
    REPO_ROOT / "citizen-web" / ".env",
    REPO_ROOT / "admin-web" / ".env.local",
    REPO_ROOT / "citizen-web" / ".env.local",
]
MOODS = ("grateful", "satisfied", "sad", "angry")


def load_env_from_files() -> None:
    for env_path in ENV_CANDIDATE_PATHS:
        if not env_path.exists():
            continue
        with env_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def fetch_feedback_rows(base_url: str, service_role_key: str, only_missing: bool, page_size: int) -> List[dict]:
    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
    }
    rows: List[dict] = []
    start = 0

    while True:
        end = start + page_size - 1
        params = {
            "select": "id,caption,predicted_mood",
            "order": "created_at.desc",
        }
        if only_missing:
            params["predicted_mood"] = "is.null"

        response = requests.get(
            f"{base_url}/rest/v1/feedbacks",
            params=params,
            headers={
                **headers,
                "Range-Unit": "items",
                "Range": f"{start}-{end}",
            },
            timeout=60,
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break

        rows.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size

    return rows


def resolve_model_version(model_dir: Path) -> str:
    if model_dir.name == "best" and model_dir.parent.name:
        return model_dir.parent.name
    return model_dir.name


def to_breakdown(scores: List[dict]) -> dict:
    breakdown = {mood: 0.0 for mood in MOODS}
    for item in scores:
        label = str(item.get("label") or "").strip().lower()
        if label not in breakdown:
            continue
        breakdown[label] = round(float(item.get("score") or 0.0), 6)
    return breakdown


def normalize_scores(raw_output) -> List[dict]:
    if isinstance(raw_output, list) and raw_output and isinstance(raw_output[0], list):
        return raw_output[0]
    if isinstance(raw_output, list):
        return raw_output
    return [raw_output]


def patch_feedback(base_url: str, service_role_key: str, feedback_id: str, payload: dict) -> None:
    response = requests.patch(
        f"{base_url}/rest/v1/feedbacks",
        params={"id": f"eq.{feedback_id}"},
        headers={
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json=payload,
        timeout=60,
    )
    response.raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill predicted_mood fields for live feedback rows using the xlm-roberta-base-round1 checkpoint."
    )
    parser.add_argument("--model-dir", default=str(DEFAULT_MODEL_DIR))
    parser.add_argument("--only-missing", action="store_true", default=False)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--page-size", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_env_from_files()
    base_url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not base_url or not service_role_key:
        raise SystemExit("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY.")

    model_dir = Path(args.model_dir)
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    pipeline = TextClassificationPipeline(model=model, tokenizer=tokenizer, top_k=None)
    model_version = resolve_model_version(model_dir)

    rows = fetch_feedback_rows(base_url, service_role_key, args.only_missing, args.page_size)
    eligible_rows = [
        row for row in rows
        if str(row.get("id") or "").strip() and str(row.get("caption") or "").strip()
    ]

    if args.limit > 0:
        eligible_rows = eligible_rows[:args.limit]

    preview = []
    updated = 0
    for row in eligible_rows:
        feedback_id = str(row["id"]).strip()
        caption = str(row["caption"]).strip()
        scores = normalize_scores(pipeline(caption, truncation=True, max_length=256))
        best = max(scores, key=lambda item: float(item.get("score") or 0.0))
        payload = {
            "predicted_mood": str(best.get("label") or "").lower(),
            "predicted_mood_confidence": round(float(best.get("score") or 0.0), 6),
            "predicted_mood_breakdown": to_breakdown(scores),
            "prediction_model_version": model_version,
        }

        if len(preview) < 5:
            preview.append({
                "id": feedback_id,
                "caption": caption[:120],
                **payload,
            })

        if not args.dry_run:
            patch_feedback(base_url, service_role_key, feedback_id, payload)
            updated += 1

    print(json.dumps({
        "model_version": model_version,
        "source_model_dir": str(model_dir),
        "accuracy_reference": 0.82,
        "rows_scanned": len(rows),
        "eligible_rows": len(eligible_rows),
        "updated": updated,
        "dry_run": args.dry_run,
        "only_missing": args.only_missing,
        "preview": preview,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
