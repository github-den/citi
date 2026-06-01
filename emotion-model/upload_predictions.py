import argparse
import json
import os
from pathlib import Path
from typing import List

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_COLUMNS = [
    "predicted_mood",
    "predicted_mood_confidence",
    "predicted_mood_breakdown",
    "prediction_model_version",
]
ENV_CANDIDATE_PATHS = [
    REPO_ROOT / ".env",
    SCRIPT_DIR / ".env",
    REPO_ROOT / "emotion-model" / ".env",
    REPO_ROOT / "admin-web" / ".env",
    REPO_ROOT / "citizen-web" / ".env",
    REPO_ROOT / "admin-web" / ".env.local",
    REPO_ROOT / "citizen-web" / ".env.local",
]


def load_rows(path: Path) -> List[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def count_manual_ids(rows: List[dict]) -> int:
    return sum(1 for row in rows if str(row.get("id") or "").startswith("manual-"))


def get_confidence(row: dict) -> float:
    try:
        return float(row.get("predicted_mood_confidence") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def prepare_rows_for_upload(rows: List[dict], min_confidence: float, below_threshold: str) -> tuple[List[dict], dict]:
    prepared_rows: List[dict] = []
    skipped_low_confidence = 0
    cleared_low_confidence = 0

    for row in rows:
        confidence = get_confidence(row)
        if confidence >= min_confidence:
            prepared_rows.append(row)
            continue

        if below_threshold == "clear":
            prepared_rows.append(
                {
                    "id": row.get("id"),
                    "text": row.get("text"),
                    "predicted_mood": None,
                    "predicted_mood_confidence": None,
                    "predicted_mood_breakdown": None,
                    "prediction_model_version": None,
                }
            )
            cleared_low_confidence += 1
        else:
            skipped_low_confidence += 1

    return prepared_rows, {
        "eligible_rows": len(prepared_rows),
        "skipped_low_confidence": skipped_low_confidence,
        "cleared_low_confidence": cleared_low_confidence,
    }


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


def patch_feedback(base_url: str, service_role_key: str, row: dict) -> None:
    feedback_id = row.get("id")
    if not feedback_id:
        return

    payload = {
        "predicted_mood": row.get("predicted_mood"),
        "predicted_mood_confidence": row.get("predicted_mood_confidence"),
        "predicted_mood_breakdown": row.get("predicted_mood_breakdown"),
        "prediction_model_version": row.get("prediction_model_version"),
    }

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
    parser = argparse.ArgumentParser(description="Upload predicted mood fields back to Supabase feedbacks.")
    parser.add_argument("--input-jsonl", default="emotion-model/exports/predicted_moods.jsonl")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--min-confidence", type=float, default=0.0)
    parser.add_argument(
        "--below-threshold",
        choices=["skip", "clear"],
        default="skip",
        help="Skip low-confidence rows, or clear existing prediction fields for them.",
    )
    args = parser.parse_args()

    rows = load_rows(Path(args.input_jsonl))
    if not rows:
        raise SystemExit("No prediction rows found.")
    prepared_rows, threshold_stats = prepare_rows_for_upload(rows, args.min_confidence, args.below_threshold)

    if args.dry_run:
        preview = prepared_rows[:5]
        print(json.dumps({
            "rows": len(rows),
            "manual_id_rows": count_manual_ids(rows),
            "min_confidence": args.min_confidence,
            "below_threshold": args.below_threshold,
            **threshold_stats,
            "columns": DEFAULT_COLUMNS,
            "preview": preview,
        }, indent=2))
        return

    load_env_from_files()
    base_url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not base_url or not service_role_key:
        raise SystemExit("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY.")

    manual_id_rows = count_manual_ids(rows)
    if manual_id_rows:
        raise SystemExit(
            f"Refusing upload: found {manual_id_rows} manual training IDs. "
            "Generate predictions from real feedback IDs first."
        )

    updated = 0
    for row in prepared_rows:
        patch_feedback(base_url, service_role_key, row)
        updated += 1

    print(json.dumps({
        "updated": updated,
        "min_confidence": args.min_confidence,
        "below_threshold": args.below_threshold,
        **threshold_stats,
        "columns": DEFAULT_COLUMNS,
    }, indent=2))


if __name__ == "__main__":
    main()
