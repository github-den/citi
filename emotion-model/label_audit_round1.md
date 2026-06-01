# Balanced Label Audit Round 1

Dataset reviewed: `all_feedback_captions_balanced.csv`

Row numbering below is 1-based data-row indexing and does not count the header.

## What stood out

- The biggest quality issue is `grateful` being used for polite requests or safety complaints that simply end with `salamat`.
- This likely explains why the model collapses `grateful` into `satisfied`: many current `grateful` examples do not describe completed help or clear appreciation.
- There are also a few obvious tone mismatches where `satisfied` should likely be `angry`.
- The CSV contains duplicate texts, which can amplify noisy labels.

## High-confidence relabel candidates

| Row | Current | Suggested | Why |
| --- | --- | --- | --- |
| 45 | grateful | sad | Stray-dog hazard and near-accident concern; distress/request, not appreciation. |
| 61 | grateful | sad | Dangerous leaning tree; worried safety report, not gratitude. |
| 75 | satisfied | angry | Mentions corruption, contractor blame, and investigation; clearly accusatory. |
| 86 | grateful | angry | All-caps garbage complaint about weeks of inaction and foul smell. |
| 118 | grateful | sad | Duplicate of row 45 with the same safety-complaint tone. |
| 156 | grateful | sad | Reports an accident and poor street lighting; concern and distress dominate. |
| 177 | grateful | satisfied | Calm request to finish roadwork safely; no clear completed-action appreciation. |
| 196 | grateful | sad | Flooding worry and disappointment; sadness/concern is stronger than gratitude. |
| 205 | grateful | satisfied | Straightforward request for a pedestrian lane. |
| 215 | grateful | satisfied | Short civic suggestion to add a public CR. |
| 243 | grateful | sad | Concern about stray dogs after the user's spouse had an accident. |
| 279 | grateful | satisfied | Request to schedule a medical mission; polite but not thankful for completed help. |
| 291 | satisfied | angry | Explicit rant with blame, repeated intensity, and "sobra na". |

## Medium-confidence candidates

| Row | Current | Suggested | Why |
| --- | --- | --- | --- |
| 20 | angry | sad | Strong safety distress is present, but blame language may still justify `angry`. |
| 214 | angry | sad | Flooding + repeated inaction reads as suffering first, anger second. |
| 127 | grateful | satisfied | Positive feedback is present, but the message leans toward "keep this up" more than explicit gratitude. |

## Duplicate texts

- Rows 29 and 241 are duplicates with label `sad`.
- Rows 70, 104, and 293 are duplicates with label `sad`.

## Recommended next move

1. Review the high-confidence rows first and update the CSV labels.
2. Keep the 4-class civic emotion scheme exactly as-is.
3. Retrain after relabeling.
4. Re-run `evaluate_model.py` and compare confusion between `grateful` and `satisfied`.
