import argparse
import csv
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import requests


MOOD_KEYS = ["grateful", "satisfied", "sad", "angry"]
REACTION_TO_MOOD = {
    "\U0001f970": "grateful",
    "\u2764": "grateful",
    "\u2764\ufe0f": "grateful",
    "\U0001f642": "satisfied",
    "\U0001f622": "sad",
    "\U0001f621": "angry",
}


def normalize_reaction(emoji: Optional[str]) -> Optional[str]:
    normalized = str(emoji or "").replace("\ufe0f", "").strip()
    return REACTION_TO_MOOD.get(normalized)


def fetch_rows(base_url: str, service_role_key: str, table: str, select: str, page_size: int = 1000) -> List[dict]:
    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
    }
    rows: List[dict] = []
    start = 0

    while True:
        end = start + page_size - 1
        response = requests.get(
            f"{base_url}/rest/v1/{table}",
            params={"select": select},
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


def choose_label(
    breakdown: Dict[str, int],
    latest_by_mood: Dict[str, str],
    min_total: int,
    min_share: float,
) -> Tuple[Optional[str], float, bool]:
    total = sum(breakdown.values())
    if total < min_total:
        return None, 0.0, False

    top_count = max(breakdown.values()) if breakdown else 0
    if top_count <= 0:
        return None, 0.0, False

    top_moods = [mood for mood, count in breakdown.items() if count == top_count]
    if len(top_moods) > 1:
        ranked = sorted(top_moods, key=lambda mood: latest_by_mood.get(mood, ""), reverse=True)
        if len(ranked) > 1 and latest_by_mood.get(ranked[0], "") == latest_by_mood.get(ranked[1], ""):
            return None, 0.0, True
        top_mood = ranked[0]
    else:
        top_mood = top_moods[0]

    share = top_count / total
    if share < min_share:
        return None, share, False

    return top_mood, share, False


def iter_labeled_feedbacks(
    feedbacks: Iterable[dict],
    reactions: Iterable[dict],
    min_total: int,
    min_share: float,
) -> Tuple[List[dict], dict]:
    by_post = defaultdict(lambda: {"breakdown": {key: 0 for key in MOOD_KEYS}, "latest": {}})

    for reaction in reactions:
        mood = normalize_reaction(reaction.get("emoji"))
        post_id = reaction.get("post_id")
        if not post_id or not mood:
            continue
        by_post[post_id]["breakdown"][mood] += 1
        created_at = reaction.get("created_at")
        if created_at:
            current = by_post[post_id]["latest"].get(mood, "")
            if created_at > current:
                by_post[post_id]["latest"][mood] = created_at

    labeled_rows: List[dict] = []
    stats = {
        "feedback_count": 0,
        "reaction_count": 0,
        "labeled_count": 0,
        "tie_skipped": 0,
        "weak_skipped": 0,
        "class_counts": {key: 0 for key in MOOD_KEYS},
    }

    for feedback in feedbacks:
        stats["feedback_count"] += 1
        post_id = feedback.get("id")
        content = str(feedback.get("content") or feedback.get("caption") or "").strip()
        if not post_id or not content:
            continue

        summary = by_post.get(post_id)
        if not summary:
            continue

        breakdown = summary["breakdown"]
        total = sum(breakdown.values())
        stats["reaction_count"] += total
        label, share, is_tie = choose_label(breakdown, summary["latest"], min_total, min_share)
        if is_tie:
            stats["tie_skipped"] += 1
            continue
        if not label:
            stats["weak_skipped"] += 1
            continue

        row = {
            "id": post_id,
            "text": content,
            "label": label,
            "confidence": round(share, 4),
            "reaction_total": total,
            "type": feedback.get("type"),
            "service": feedback.get("service") or feedback.get("subcategory") or feedback.get("category"),
            "barangay": feedback.get("barangay") or feedback.get("incident_location") or feedback.get("location"),
            "created_at": feedback.get("created_at"),
            "breakdown": breakdown,
        }
        labeled_rows.append(row)
        stats["labeled_count"] += 1
        stats["class_counts"][label] += 1

    return labeled_rows, stats


def write_outputs(rows: List[dict], stats: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "feedback_reaction_labels.jsonl"
    csv_path = output_dir / "feedback_reaction_labels.csv"
    report_path = output_dir / "dataset_report.json"

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in rows:
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
                "grateful",
                "satisfied",
                "sad",
                "angry",
            ],
        )
        writer.writeheader()
        for row in rows:
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
                    **row["breakdown"],
                }
            )

    report_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a reaction-labeled mood dataset from Supabase.")
    parser.add_argument("--output-dir", default="emotion-model/exports", help="Where to write the dataset files.")
    parser.add_argument("--min-total", type=int, default=3, help="Minimum total reactions required for a label.")
    parser.add_argument("--min-share", type=float, default=0.6, help="Minimum dominant class share required for a label.")
    args = parser.parse_args()

    base_url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not base_url or not service_role_key:
        raise SystemExit("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY.")

    feedbacks = fetch_rows(
        base_url,
        service_role_key,
        "feedbacks",
        "*",
    )
    reactions = fetch_rows(
        base_url,
        service_role_key,
        "reactions",
        "post_id,emoji,created_at",
    )

    rows, stats = iter_labeled_feedbacks(feedbacks, reactions, args.min_total, args.min_share)
    write_outputs(rows, stats, Path(args.output_dir))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
