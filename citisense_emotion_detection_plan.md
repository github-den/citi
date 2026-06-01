# CitiSense Emotion Detection Plan

## Goal
Build one mood system shared by `citizen-web`, `admin-web`, and `citizen-mobile` where every final mood is only one of:

- `Grateful`
- `Satisfied`
- `Sad`
- `Angry`

The system must work from:

1. single feedback
2. feedback reactions
3. feedback mood summary
4. barangay / category / office summaries
5. city mood

## Core Decision
The official mood must be **reaction-first**.

That means:

- real reactions are the main source of truth
- the model is only a fallback for low-signal or no-reaction cases
- no screen, export, chart, or API should output any mood label outside the four approved moods

This is the most defensible approach for capstone defense, code review, and product reliability.

---

## 1. Allowed Mood Labels

Use one shared enum everywhere:

```js
const MOOD_LABELS = ['grateful', 'satisfied', 'sad', 'angry'];
```

Use it in:

- frontend constants
- database constraints
- RPC outputs
- model label mapping
- exports
- analytics

---

## 2. Source of Truth Rules

## 2.1 Final mood priority
For each feedback:

1. strong reaction result
2. model prediction fallback
3. no mood data yet

## 2.2 Strong reaction result
Treat reaction mood as reliable when:

- total reactions >= `3`
- one mood clearly has the highest count
- dominant mood share >= `60%`

Example:

- `5/7` satisfied -> strong
- `2/4` angry with a tie -> not strong

## 2.3 Tie handling
If two moods tie:

1. use the most recent reaction among the tied top moods
2. if still tied, mark internal result as `undecided`
3. public UI should show `No mood data yet` or `Low confidence`

---

## 3. Single Feedback Flow

## 3.1 Feedback creation
When a citizen submits feedback, store the usual post fields:

- `feedback_id`
- `user_id`
- `content`
- `type`
- `service`
- `location`
- `created_at`

At this stage:

- final mood is empty
- prediction may be generated later if needed

## 3.2 Reaction capture
Each citizen can react using only:

- `Grateful`
- `Satisfied`
- `Sad`
- `Angry`

Recommended reaction fields:

- `id`
- `feedback_id`
- `user_id`
- `reaction_label`
- `created_at`
- `updated_at`

Constraint:

- one active reaction per user per feedback

## 3.3 Per-feedback reaction summary
For each feedback, compute:

- `grateful_count`
- `satisfied_count`
- `sad_count`
- `angry_count`
- `reaction_total`

## 3.4 Final feedback mood
From the counts above, compute:

- `final_mood`
- `mood_confidence`
- `mood_source`

Suggested confidence:

```text
dominant_count / reaction_total
```

Example:

```json
{
  "feedback_id": "fb_001",
  "reaction_total": 10,
  "grateful_count": 2,
  "satisfied_count": 5,
  "sad_count": 1,
  "angry_count": 2,
  "final_mood": "satisfied",
  "mood_confidence": 0.5,
  "mood_source": "reactions"
}
```

---

## 4. Model Purpose

If reacts already define the official mood, the model is still useful for:

- new feedback with zero reactions
- low-engagement feedback
- internal analytics before enough reactions accumulate
- capstone research comparison

The model must never invent new emotions. It may only predict:

- `grateful`
- `satisfied`
- `sad`
- `angry`

## 4.1 Model role
Use the model as:

- `predictive support tool`
- not the main truth source

Best defense framing:

> Reactions provide the official mood, while the classifier is used only for sparse or missing reaction data.

---

## 5. Recommended Model

Use **`xlm-roberta-base`** for the main classifier experiment.

Why:

- supports English, Filipino, and Taglish better than English-only models
- strong on short civic text
- easier to defend academically than a pure keyword approach

Also train two baselines:

1. `TF-IDF + Logistic Regression`
2. `TF-IDF + Linear SVM`
3. `xlm-roberta-base`

Final model selection should be based on:

- macro F1
- per-class recall
- Taglish performance
- inference cost

---

## 6. Training Dataset Plan

## 6.1 Label source
Use real feedback with clear dominant reactions as the main labeled dataset.

Training inclusion rule:

- reactions >= `3`
- dominant share >= `60%`
- no top-count tie

## 6.2 Sample format

```json
{
  "text": "Naayos agad ang drainage, salamat po.",
  "label": "grateful"
}
```

## 6.3 Keep weak samples separate
Do not use weak samples in the main training set:

- no reactions
- one reaction only
- tied top moods
- highly mixed signals

Keep them for:

- manual review
- later experiments
- fallback evaluation

## 6.4 Coverage requirements
Include:

- English
- Filipino
- Taglish
- short feedback
- formal civic complaints
- polite but negative feedback
- positive appreciation posts

---

## 7. Train / Validation / Test Setup

Use stratified split:

- `70%` train
- `15%` validation
- `15%` test

Also prepare a **hard test set** for:

- very short text
- Taglish
- sarcasm
- mixed emotion wording
- factual but negative service reports

If the clean dataset is still small, also run:

- `5-fold cross validation`

---

## 8. Evaluation Plan

Measure:

- accuracy
- macro precision
- macro recall
- macro F1
- per-class F1
- confusion matrix

Main decision metric:

- **macro F1**

Why:

- classes may be imbalanced
- accuracy alone can hide poor performance on `Sad` or `Angry`

## 8.1 Error analysis
Review at least:

- `50` wrong predictions
- `20` Taglish predictions
- `20` short-text predictions
- `20` low-confidence predictions

Look for:

- grateful vs satisfied confusion
- sad vs angry confusion
- sarcasm
- polite dissatisfaction
- vague civic language

---

## 9. Inference Rules

Suggested prediction confidence thresholds:

- `< 0.55`: do not use publicly
- `0.55 - 0.70`: internal only or low confidence
- `> 0.70`: allowed as fallback when no strong reaction result exists

Public display rule:

- strong reactions win
- otherwise high-confidence prediction may be used
- otherwise show `No mood data yet`

---

## 10. Aggregation Plan

## 10.1 Barangay mood
Aggregate reaction counts across all feedback in one barangay.

Output:

- 4 mood counts
- total reactions
- dominant mood
- confidence

## 10.2 Service category mood
Aggregate by service category:

- roads
- health
- sanitation
- transport
- others

## 10.3 Office mood
Aggregate by responsible office in admin views.

## 10.4 City mood
Aggregate all reactions in the selected range.

Example:

```json
{
  "scope": "city",
  "range": "last_7_days",
  "grateful": 140,
  "satisfied": 220,
  "sad": 90,
  "angry": 110,
  "total": 560,
  "final_mood": "satisfied",
  "confidence": 0.39,
  "source": "reactions"
}
```

## 10.5 Date ranges
Support:

- all time
- last 7 days
- last 30 days
- custom range

Only reactions inside the selected range should count.

---

## 11. Shared Backend Needs

Implement or confirm:

- reaction save/update logic
- one-reaction-per-user-per-feedback rule
- per-feedback reaction summary
- final mood calculation
- city mood RPC
- barangay mood RPC
- category mood RPC
- office mood RPC
- optional prediction storage

Recommended output fields:

- `final_mood`
- `mood_confidence`
- `mood_source`
- `breakdown`
- `reaction_total`

Keep prediction separate:

- `predicted_mood`
- `predicted_mood_confidence`
- `prediction_model_version`

---

## 12. Rollout Phases

## Phase 1. Vocabulary and data rules

- standardize the 4 mood labels
- update frontend constants
- remove old generic mood outputs

## Phase 2. Reaction summaries

- compute per-feedback mood from reactions
- compute confidence and source

## Phase 3. Aggregation

- city mood
- barangay mood
- category mood
- office mood

## Phase 4. UI updates

- connect citizen mood cards
- connect mobile mood cards
- connect admin dashboard mood KPI and charts

## Phase 5. Training pipeline

- build clean labeled dataset
- train baselines
- train `xlm-roberta-base`
- compare metrics

## Phase 6. Prediction fallback

- add prediction storage
- apply fallback rules
- keep public output reaction-first

## Phase 7. QA and defense prep

- metric report
- confusion matrix
- sample prediction review
- data flow diagram
- limitations and ethics notes

---

## 13. Defense Position

Best short explanation:

> CitiSense uses real citizen reactions as the official mood source. The classifier is limited to the same four moods and is used only when reaction data is too weak or missing.

Why this is strong:

- easy to explain
- tied to real user input
- avoids invented emotions
- supports analytics and research
- easier to defend than a pure text-only mood system

---

## 14. Success Criteria

Ship only if:

- all systems output only the 4 approved moods
- reaction-based mood works end to end
- city mood uses real aggregated reactions
- fallback prediction never overrides strong reaction truth
- macro F1 is acceptable, ideally `>= 0.75`
- `Sad` and `Angry` recall are strong enough for civic risk monitoring

---

## 15. Applied Plans

This root plan should be applied to:

- [citizen-web/citisense_emotion_detection_plan.md](./citizen-web/citisense_emotion_detection_plan.md)
- [admin-web/citisense_emotion_detection_plan.md](./admin-web/citisense_emotion_detection_plan.md)
- [citizen-mobile/citisense_emotion_detection_plan.md](./citizen-mobile/citisense_emotion_detection_plan.md)
