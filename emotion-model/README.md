# Emotion Model Workspace

This folder contains the offline training and evaluation flow for the 4-class CitiSense mood model:

- `grateful`
- `satisfied`
- `sad`
- `angry`

The production rule stays the same:

1. strong reaction mood
2. prediction fallback
3. no mood data yet

## 1. Install Python dependencies

```bash
pip install -r emotion-model/requirements.txt
```

## 2. Export the reaction-labeled dataset

Set:

- `NEXT_PUBLIC_SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

Then run:

```bash
python emotion-model/export_dataset.py
```

This creates:

- `emotion-model/exports/feedback_reaction_labels.jsonl`
- `emotion-model/exports/feedback_reaction_labels.csv`
- `emotion-model/exports/dataset_report.json`

Only strong reaction labels are exported by default:

- at least `3` total reactions
- dominant class share at least `60%`
- no unresolved top tie

## 3. Train `xlm-roberta-base`

```bash
python emotion-model/train_xlm_roberta.py
```

If `emotion-model/exports/feedback_reaction_labels.jsonl` is empty, the trainer now
falls back automatically to `emotion-model/exports/manual_balanced_feedback_labels.jsonl`.

Optional flags:

```bash
python emotion-model/train_xlm_roberta.py --epochs 4 --batch-size 8 --learning-rate 2e-5
```

Outputs go to:

- `emotion-model/checkpoints/xlm-roberta-base/`

Saved artifacts include:

- best checkpoint
- tokenizer
- label map
- test metrics

## 4. Evaluate the trained checkpoint

```bash
python emotion-model/evaluate_model.py
```

Evaluation uses the same dataset fallback behavior as training.

This writes:

- `emotion-model/checkpoints/xlm-roberta-base/evaluation.json`

## 5. Predict moods

Single text:

```bash
python emotion-model/predict_mood.py --text "Thank you for fixing the drainage quickly."
```

If you point `--model-dir` at a `.../best` checkpoint, the emitted
`prediction_model_version` now uses the parent checkpoint folder name.

Batch JSONL:

```bash
python emotion-model/predict_mood.py --input-jsonl emotion-model/exports/feedback_reaction_labels.jsonl
```

## 6. Add prediction columns

Run:

```sql
\i emotion-model/add_prediction_columns.sql
```

or execute the SQL in your Supabase SQL editor.

## 6b. Install the reaction-first mood backend

Run:

```sql
\i emotion-model/reaction_first_mood_backend.sql
```

This installs the database-side rules expected by the apps:

- one active reaction per user per feedback
- `react_post`
- persisted `final_mood`, `mood_confidence`, `mood_source`, and `reaction_breakdown`
- `get_city_mood`
- `get_barangay_mood`
- `get_category_mood`
- `get_office_mood`

## 7. Upload predictions back to Supabase

Dry run:

```bash
python emotion-model/upload_predictions.py --dry-run
```

Confidence-gated dry run:

```bash
python emotion-model/upload_predictions.py --input-jsonl emotion-model/exports/predicted_moods_live.jsonl --min-confidence 0.45 --below-threshold clear --dry-run
```

Real upload:

```bash
python emotion-model/upload_predictions.py
```

With thresholding, `--below-threshold skip` uploads only stronger predictions,
while `--below-threshold clear` nulls out weak prediction fields in Supabase.

## Output Contract

Batch predictions use fields that match the app mapping:

- `predicted_mood`
- `predicted_mood_confidence`
- `prediction_model_version`

Those fields are already recognized by:

- `citizen-web`
- `citizen-mobile`
- `admin-web`

But they should only be used as fallback when strong reaction mood is missing.
The shared fallback threshold is now `0.30`; weaker predictions should be cleared or ignored.

## Runtime Note

The app API route `POST /api/feedback-ai` now supports:

- `task: "content_flags"`
- `task: "mood_prediction"`

`mood_prediction` currently uses the existing structured AI provider path as a deployment-friendly fallback interface.

That route is useful for:

- prototyping
- testing the contract
- internal fallback behavior

The fine-tuned `xlm-roberta-base` checkpoint can replace that runtime predictor later without changing the app-facing payload shape.
