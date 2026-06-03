import os
import requests
from pathlib import Path

def load_env():
    env_path = Path("citizen-web/.env")
    if not env_path.exists():
        env_path = Path(".env")
    if not env_path.exists():
        raise SystemExit("Missing .env file.")
    
    lines = [l.strip().split("=", 1) for l in env_path.read_text(encoding="utf-8").splitlines() if "=" in l and not l.startswith("#")]
    return {k.strip(): v.strip() for k, v in lines}

def main():
    env = load_env()
    url = env["NEXT_PUBLIC_SUPABASE_URL"]
    key = env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    # Fetch all feedbacks
    r = requests.get(f"{url}/rest/v1/feedbacks?select=*", headers=headers)
    r.raise_for_status()
    feedbacks = r.json()

    print(f"Scanned {len(feedbacks)} feedbacks.")
    updated_count = 0
    PRIORITY = ["angry", "sad", "grateful", "satisfied"]

    for fb in feedbacks:
        fb_id = fb["id"]
        reacts_count = int(fb.get("reacts_count") or 0)
        predicted_mood = fb.get("predicted_mood")
        predicted_conf = float(fb.get("predicted_mood_confidence") or 0.0)
        predicted_breakdown = fb.get("predicted_mood_breakdown") or {}
        post_type = str(fb.get("type") or "complaint").strip().lower()
        
        # Determine predicted breakdown availability
        is_pred_available = (predicted_mood is not None)
        
        # Calculate final mood and source
        final_mood = None
        mood_source = "none"
        mood_confidence = 0.0

        if is_pred_available and reacts_count >= 4:
            mood_source = "caption+reactions"
            # Blended breakdown
            pred_b = predicted_breakdown
            # Normalized reactions breakdown
            react_b = fb.get("reaction_breakdown") or {m: 0 for m in ["grateful", "satisfied", "sad", "angry"]}
            
            blended = {}
            for mood in ["grateful", "satisfied", "sad", "angry"]:
                p_val = float(pred_b.get(mood) or 0.0)
                r_val = float(react_b.get(mood) or 0.0) / reacts_count if reacts_count > 0 else 0.0
                blended[mood] = p_val * 0.70 + r_val * 0.30
                
            # Mask based on type
            if post_type == "compliment":
                blended["sad"] = 0.0
                blended["angry"] = 0.0
            elif post_type == "complaint":
                blended["grateful"] = 0.0
                blended["satisfied"] = 0.0
            
            # Choose top mood with strict priority tie-breaker
            best_mood = max(blended.keys(), key=lambda m: (blended[m], -PRIORITY.index(m)))
            final_mood = best_mood
            mood_confidence = round(blended[best_mood], 6)
        elif is_pred_available:
            mood_source = "prediction"
            # Single prediction with breakdown masking
            pred_b = {m: float(predicted_breakdown.get(m) or 0.0) for m in ["grateful", "satisfied", "sad", "angry"]}
            
            if post_type == "compliment":
                pred_b["sad"] = 0.0
                pred_b["angry"] = 0.0
            elif post_type == "complaint":
                pred_b["grateful"] = 0.0
                pred_b["satisfied"] = 0.0
                
            best_mood = max(pred_b.keys(), key=lambda m: (pred_b[m], -PRIORITY.index(m)))
            final_mood = best_mood
            mood_confidence = round(pred_b[best_mood], 6)
        elif reacts_count > 0:
            mood_source = "reactions-fallback"
            react_b = fb.get("reaction_breakdown") or {m: 0 for m in ["grateful", "satisfied", "sad", "angry"]}
            
            # Mask based on type
            if post_type == "compliment":
                react_b["sad"] = 0.0
                react_b["angry"] = 0.0
            elif post_type == "complaint":
                react_b["grateful"] = 0.0
                react_b["satisfied"] = 0.0
                
            best_mood = max(react_b.keys(), key=lambda m: (react_b[m], -PRIORITY.index(m)))
            final_mood = best_mood
            mood_confidence = round(float(react_b[best_mood]) / reacts_count, 6)
        else:
            mood_source = "none"
            final_mood = None
            mood_confidence = 0.0

        # Patch if changed
        if fb.get("final_mood") != final_mood or fb.get("mood_source") != mood_source or fb.get("mood_confidence") != mood_confidence:
            payload = {
                "final_mood": final_mood,
                "mood_source": mood_source,
                "mood_confidence": mood_confidence
            }
            requests.patch(f"{url}/rest/v1/feedbacks?id=eq.{fb_id}", json=payload, headers=headers).raise_for_status()
            updated_count += 1

    print(f"Instantly synced database records. Updated {updated_count} rows.")

if __name__ == "__main__":
    main()
