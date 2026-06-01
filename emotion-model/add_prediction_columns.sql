alter table public.feedbacks
  add column if not exists predicted_mood text,
  add column if not exists predicted_mood_confidence double precision,
  add column if not exists prediction_model_version text;

comment on column public.feedbacks.predicted_mood is
  'Fallback model-predicted mood label. Must stay within grateful, satisfied, sad, angry.';

comment on column public.feedbacks.predicted_mood_confidence is
  'Confidence score for the fallback predicted mood.';

comment on column public.feedbacks.prediction_model_version is
  'Checkpoint or runtime model version that produced the fallback mood.';
