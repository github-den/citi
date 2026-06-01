begin;

drop trigger if exists citisense_feedback_prediction_sync_trigger on public.feedbacks;
drop trigger if exists citisense_feedback_prediction_guard_trigger on public.feedbacks;
drop function if exists public.citisense_feedback_prediction_sync();
drop function if exists public.citisense_feedback_prediction_guard();
drop function if exists public.citisense_feedback_final_mood_summary(uuid);
drop function if exists public.citisense_predicted_mood_breakdown(text, double precision, jsonb);
drop function if exists public.citisense_empty_mood_breakdown();
drop function if exists public.citisense_prediction_is_public(double precision);

alter table public.feedbacks
  add column if not exists final_mood text,
  add column if not exists mood_confidence double precision,
  add column if not exists mood_source text,
  add column if not exists reaction_breakdown jsonb default jsonb_build_object(
    'grateful', 0,
    'satisfied', 0,
    'sad', 0,
    'angry', 0
  );

alter table public.feedbacks
  add column if not exists predicted_mood text,
  add column if not exists predicted_mood_confidence double precision,
  add column if not exists predicted_mood_breakdown jsonb default jsonb_build_object(
    'grateful', 0,
    'satisfied', 0,
    'sad', 0,
    'angry', 0
  ),
  add column if not exists prediction_model_version text;

create unique index if not exists reactions_one_per_user_per_post_idx
  on public.reactions (post_id, user_id);

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'feedbacks_final_mood_allowed'
  ) then
    alter table public.feedbacks
      add constraint feedbacks_final_mood_allowed
      check (final_mood is null or final_mood in ('grateful', 'satisfied', 'sad', 'angry'));
  end if;

  if not exists (
    select 1
    from pg_constraint
    where conname = 'feedbacks_predicted_mood_allowed'
  ) then
    alter table public.feedbacks
      add constraint feedbacks_predicted_mood_allowed
      check (predicted_mood is null or predicted_mood in ('grateful', 'satisfied', 'sad', 'angry'));
  end if;
end
$$;

drop function if exists public.react_post(uuid, text);
drop function if exists public.get_city_mood(integer);
drop function if exists public.get_barangay_mood(text, integer);
drop function if exists public.get_category_mood(text, integer);
drop function if exists public.get_office_mood(text, integer);
drop function if exists public.citisense_feedback_reaction_summary(uuid);
drop function if exists public.citisense_scope_mood_summary(integer, text, text, text);

create or replace function public.citisense_normalize_reaction_mood(p_value text)
returns text
language sql
immutable
as $$
  select case lower(replace(trim(coalesce(p_value, '')), U&'\FE0F', ''))
    when '❤' then 'grateful'
    when 'grateful' then 'grateful'
    when '🙂' then 'satisfied'
    when 'satisfied' then 'satisfied'
    when '😢' then 'sad'
    when 'sad' then 'sad'
    when '😡' then 'angry'
    when 'angry' then 'angry'
    else null
  end
$$;

create or replace function public.citisense_mood_display_emoji(p_mood text)
returns text
language sql
immutable
as $$
  select case lower(trim(coalesce(p_mood, '')))
    when 'grateful' then '🥰'
    when 'satisfied' then '🙂'
    when 'sad' then '😔'
    when 'angry' then '😠'
    else '😶'
  end
$$;

create or replace function public.citisense_office_for_service(p_service text)
returns text
language sql
immutable
as $$
  select case lower(trim(coalesce(p_service, '')))
    when 'health' then 'City Health Office'
    when 'infrastructure' then 'City Engineers Office'
    when 'social welfare' then 'City Social Welfare and Development Office'
    when 'environment' then 'City Environment and Natural Resources Office'
    when 'peace & order' then 'Public Order and Safety Office - Security Division'
    when 'public facilities' then 'City Engineers Office'
    when 'economic services' then 'Business Permits and Licensing Office, City Planning and Development Office'
    when 'agriculture' then 'City Agriculture Office'
    when 'education' then 'City Schools Division Office'
    when 'housing' then 'City Housing Office, City Planning and Development Office'
    when 'tourism' then 'City Tourism Office'
    when 'transportation' then 'City Transport and Traffic Management Office'
    else null
  end
$$;

create or replace function public.citisense_empty_mood_breakdown()
returns jsonb
language sql
immutable
as $$
  select jsonb_build_object(
    'grateful', 0,
    'satisfied', 0,
    'sad', 0,
    'angry', 0
  )
$$;

create or replace function public.citisense_prediction_is_public(p_confidence double precision)
returns boolean
language sql
immutable
as $$
  select coalesce(p_confidence, 0) >= 0.30
$$;

create or replace function public.citisense_predicted_mood_breakdown(
  p_predicted_mood text,
  p_confidence double precision,
  p_breakdown jsonb default null
)
returns jsonb
language plpgsql
immutable
as $$
declare
  v_mood text := lower(trim(coalesce(p_predicted_mood, '')));
  v_confidence double precision := greatest(0, least(1, coalesce(p_confidence, 0)));
  v_fallback_other double precision := greatest(0, 1 - v_confidence) / 3;
  v_grateful double precision;
  v_satisfied double precision;
  v_sad double precision;
  v_angry double precision;
  v_total double precision;
begin
  if v_mood not in ('grateful', 'satisfied', 'sad', 'angry') then
    return public.citisense_empty_mood_breakdown();
  end if;

  if p_breakdown is null then
    return jsonb_build_object(
      'grateful', case when v_mood = 'grateful' then v_confidence else v_fallback_other end,
      'satisfied', case when v_mood = 'satisfied' then v_confidence else v_fallback_other end,
      'sad', case when v_mood = 'sad' then v_confidence else v_fallback_other end,
      'angry', case when v_mood = 'angry' then v_confidence else v_fallback_other end
    );
  end if;

  v_grateful := greatest(0, coalesce((p_breakdown->>'grateful')::double precision, 0));
  v_satisfied := greatest(0, coalesce((p_breakdown->>'satisfied')::double precision, 0));
  v_sad := greatest(0, coalesce((p_breakdown->>'sad')::double precision, 0));
  v_angry := greatest(0, coalesce((p_breakdown->>'angry')::double precision, 0));
  v_total := v_grateful + v_satisfied + v_sad + v_angry;

  if coalesce(v_total, 0) <= 0 then
    return jsonb_build_object(
      'grateful', case when v_mood = 'grateful' then v_confidence else v_fallback_other end,
      'satisfied', case when v_mood = 'satisfied' then v_confidence else v_fallback_other end,
      'sad', case when v_mood = 'sad' then v_confidence else v_fallback_other end,
      'angry', case when v_mood = 'angry' then v_confidence else v_fallback_other end
    );
  end if;

  return jsonb_build_object(
    'grateful', v_grateful / v_total,
    'satisfied', v_satisfied / v_total,
    'sad', v_sad / v_total,
    'angry', v_angry / v_total
  );
end
$$;

create or replace function public.citisense_feedback_reaction_summary(p_post_id uuid)
returns table (
  final_mood text,
  dominant_mood text,
  mood_confidence double precision,
  mood_source text,
  reaction_total bigint,
  breakdown jsonb,
  has_tie boolean,
  emoji text
)
language sql
stable
as $$
  with counts as (
    select
      public.citisense_normalize_reaction_mood(r.emoji) as mood,
      count(*)::bigint as amount,
      max(r.created_at) as latest_at
    from public.reactions r
    where r.post_id = p_post_id
    group by 1
    having public.citisense_normalize_reaction_mood(r.emoji) is not null
  ),
  totals as (
    select
      coalesce(sum(amount), 0)::bigint as reaction_total,
      jsonb_build_object(
        'grateful', coalesce((select amount from counts where mood = 'grateful'), 0),
        'satisfied', coalesce((select amount from counts where mood = 'satisfied'), 0),
        'sad', coalesce((select amount from counts where mood = 'sad'), 0),
        'angry', coalesce((select amount from counts where mood = 'angry'), 0)
      ) as breakdown
    from counts
  ),
  top_amount as (
    select max(amount) as amount
    from counts
  ),
  top_candidates as (
    select c.*
    from counts c
    join top_amount t on c.amount = t.amount
  ),
  latest_top as (
    select max(latest_at) as latest_at
    from top_candidates
  ),
  chosen as (
    select
      tc.mood,
      tc.amount,
      tc.latest_at,
      (
        select count(*)
        from top_candidates tc2
        join latest_top lt2 on tc2.latest_at = lt2.latest_at
      ) as latest_tied
    from top_candidates tc
    join latest_top lt on tc.latest_at = lt.latest_at
    order by tc.mood
    limit 1
  )
  select
    case
      when t.reaction_total = 0 then null
      when coalesce(c.latest_tied, 0) = 1
        and c.amount::double precision / nullif(t.reaction_total, 0) >= 0.60
        and t.reaction_total >= 3
      then c.mood
      else null
    end as final_mood,
    case
      when coalesce(c.latest_tied, 0) = 1 then c.mood
      else null
    end as dominant_mood,
    case
      when coalesce(c.latest_tied, 0) = 1 and t.reaction_total > 0
      then c.amount::double precision / t.reaction_total
      else 0
    end as mood_confidence,
    case
      when t.reaction_total = 0 then 'none'
      when coalesce(c.latest_tied, 0) = 1
        and c.amount::double precision / nullif(t.reaction_total, 0) >= 0.60
        and t.reaction_total >= 3
      then 'reactions'
      else 'none'
    end as mood_source,
    t.reaction_total,
    t.breakdown,
    case
      when (select count(*) from top_candidates) > 1 and coalesce(c.latest_tied, 0) <> 1 then true
      else false
    end as has_tie,
    public.citisense_mood_display_emoji(
      case
        when t.reaction_total = 0 then null
        when coalesce(c.latest_tied, 0) = 1
          and c.amount::double precision / nullif(t.reaction_total, 0) >= 0.60
          and t.reaction_total >= 3
        then c.mood
        else null
      end
    ) as emoji
  from totals t
  left join chosen c on true
$$;

create or replace function public.citisense_feedback_final_mood_summary(p_post_id uuid)
returns table (
  final_mood text,
  dominant_mood text,
  mood_confidence double precision,
  mood_source text,
  reaction_total bigint,
  reaction_breakdown jsonb,
  predicted_breakdown jsonb,
  blended_breakdown jsonb,
  has_tie boolean,
  emoji text
)
language sql
stable
as $$
  with feedback as (
    select
      f.predicted_mood,
      f.predicted_mood_confidence,
      f.predicted_mood_breakdown
    from public.feedbacks f
    where f.id = p_post_id
  ),
  reaction as (
    select *
    from public.citisense_feedback_reaction_summary(p_post_id)
  ),
  predicted as (
    select
      public.citisense_predicted_mood_breakdown(
        fb.predicted_mood,
        fb.predicted_mood_confidence,
        fb.predicted_mood_breakdown
      ) as breakdown,
      lower(trim(coalesce(fb.predicted_mood, ''))) as mood,
      fb.predicted_mood is not null as is_available
    from feedback fb
  ),
  reaction_normalized as (
    select
      coalesce(r.reaction_total, 0)::bigint as reaction_total,
      coalesce(r.breakdown, public.citisense_empty_mood_breakdown()) as raw_breakdown,
      jsonb_build_object(
        'grateful', case when coalesce(r.reaction_total, 0) > 0 then coalesce((r.breakdown->>'grateful')::double precision, 0) / r.reaction_total else 0 end,
        'satisfied', case when coalesce(r.reaction_total, 0) > 0 then coalesce((r.breakdown->>'satisfied')::double precision, 0) / r.reaction_total else 0 end,
        'sad', case when coalesce(r.reaction_total, 0) > 0 then coalesce((r.breakdown->>'sad')::double precision, 0) / r.reaction_total else 0 end,
        'angry', case when coalesce(r.reaction_total, 0) > 0 then coalesce((r.breakdown->>'angry')::double precision, 0) / r.reaction_total else 0 end
      ) as normalized_breakdown,
      coalesce(r.final_mood is not null, false) as is_strong,
      r.dominant_mood
    from reaction r
  ),
  combined as (
    select
      rn.reaction_total,
      rn.raw_breakdown as reaction_breakdown,
      pr.breakdown as predicted_breakdown,
      case
        when pr.is_available and rn.reaction_total >= 5 then jsonb_build_object(
          'grateful', coalesce((pr.breakdown->>'grateful')::double precision, 0) * 0.60 + coalesce((rn.normalized_breakdown->>'grateful')::double precision, 0) * 0.40,
          'satisfied', coalesce((pr.breakdown->>'satisfied')::double precision, 0) * 0.60 + coalesce((rn.normalized_breakdown->>'satisfied')::double precision, 0) * 0.40,
          'sad', coalesce((pr.breakdown->>'sad')::double precision, 0) * 0.60 + coalesce((rn.normalized_breakdown->>'sad')::double precision, 0) * 0.40,
          'angry', coalesce((pr.breakdown->>'angry')::double precision, 0) * 0.60 + coalesce((rn.normalized_breakdown->>'angry')::double precision, 0) * 0.40
        )
        when pr.is_available then pr.breakdown
        when rn.reaction_total > 0 then rn.normalized_breakdown
        else public.citisense_empty_mood_breakdown()
      end as blended_breakdown,
      case
        when pr.is_available and rn.reaction_total >= 5 then 'caption+reactions'
        when pr.is_available then 'caption'
        when rn.reaction_total > 0 then 'reactions-fallback'
        else 'none'
      end as mood_source,
      pr.mood as predicted_mood,
      rn.dominant_mood as reaction_mood
    from reaction_normalized rn
    cross join predicted pr
  ),
  scored as (
    select
      c.*,
      score_rows.mood,
      score_rows.score,
      dense_rank() over (order by score_rows.score desc) as score_rank
    from combined c
    cross join lateral (
      values
        ('grateful', coalesce((c.blended_breakdown->>'grateful')::double precision, 0)),
        ('satisfied', coalesce((c.blended_breakdown->>'satisfied')::double precision, 0)),
        ('sad', coalesce((c.blended_breakdown->>'sad')::double precision, 0)),
        ('angry', coalesce((c.blended_breakdown->>'angry')::double precision, 0))
    ) as score_rows(mood, score)
  ),
  chosen as (
    select
      mood,
      score
    from scored
    where score_rank = 1
    order by
      case
        when mood = predicted_mood then 0
        when mood = reaction_mood then 1
        else 2
      end,
      mood
    limit 1
  ),
  top_scores as (
    select count(*)::integer as top_count
    from scored
    where score_rank = 1
  )
  select
    case
      when c.mood_source = 'none' or coalesce(ch.score, 0) <= 0 then null
      else ch.mood
    end as final_mood,
    case
      when c.mood_source = 'none' or coalesce(ch.score, 0) <= 0 then null
      else ch.mood
    end as dominant_mood,
    case
      when c.mood_source = 'none' or coalesce(ch.score, 0) <= 0 then 0
      else ch.score
    end as mood_confidence,
    c.mood_source,
    c.reaction_total,
    c.reaction_breakdown,
    c.predicted_breakdown,
    c.blended_breakdown,
    coalesce(ts.top_count, 0) > 1 as has_tie,
    public.citisense_mood_display_emoji(
      case
        when c.mood_source = 'none' or coalesce(ch.score, 0) <= 0 then null
        else ch.mood
      end
    ) as emoji
  from combined c
  left join chosen ch on true
  left join top_scores ts on true
$$;

create or replace function public.citisense_sync_feedback_mood(p_post_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_summary record;
begin
  select *
  into v_summary
  from public.citisense_feedback_final_mood_summary(p_post_id);

  update public.feedbacks
  set
    reacts_count = coalesce(v_summary.reaction_total, 0),
    reaction_breakdown = coalesce(v_summary.reaction_breakdown, jsonb_build_object(
      'grateful', 0,
      'satisfied', 0,
      'sad', 0,
      'angry', 0
    )),
    final_mood = v_summary.final_mood,
    mood_confidence = coalesce(v_summary.mood_confidence, 0),
    mood_source = coalesce(v_summary.mood_source, 'none')
  where id = p_post_id;
end
$$;

create or replace function public.citisense_feedback_prediction_guard()
returns trigger
language plpgsql
as $$
begin
  if new.predicted_mood is null
    or new.predicted_mood_confidence is null
  then
    new.predicted_mood := null;
    new.predicted_mood_confidence := null;
    new.predicted_mood_breakdown := null;
    new.prediction_model_version := null;
    return new;
  end if;

  if new.predicted_mood_confidence < 0 then
    new.predicted_mood_confidence := 0;
  elsif new.predicted_mood_confidence > 1 then
    new.predicted_mood_confidence := 1;
  end if;

  return new;
end
$$;

create or replace function public.citisense_feedback_prediction_sync()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  perform public.citisense_sync_feedback_mood(coalesce(new.id, old.id));
  return coalesce(new, old);
end
$$;

create trigger citisense_feedback_prediction_guard_trigger
before insert or update of predicted_mood, predicted_mood_confidence, predicted_mood_breakdown, prediction_model_version
on public.feedbacks
for each row
execute function public.citisense_feedback_prediction_guard();

create trigger citisense_feedback_prediction_sync_trigger
after insert or update of predicted_mood, predicted_mood_confidence, predicted_mood_breakdown, prediction_model_version
on public.feedbacks
for each row
execute function public.citisense_feedback_prediction_sync();

create or replace function public.react_post(p_post_id uuid, p_emoji text default null)
returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  v_user_id uuid := auth.uid();
  v_reaction_label text;
begin
  if v_user_id is null then
    raise exception 'Not authenticated';
  end if;

  if coalesce(trim(p_emoji), '') = '' then
    delete from public.reactions
    where post_id = p_post_id
      and user_id = v_user_id;

    perform public.citisense_sync_feedback_mood(p_post_id);

    return jsonb_build_object(
      'post_id', p_post_id,
      'user_id', v_user_id,
      'removed', true
    );
  end if;

  v_reaction_label := public.citisense_normalize_reaction_mood(p_emoji);
  if v_reaction_label is null then
    raise exception 'Unsupported reaction label: %', p_emoji;
  end if;

  insert into public.reactions (
    post_id,
    user_id,
    emoji,
    created_at,
    updated_at
  )
  values (
    p_post_id,
    v_user_id,
    p_emoji,
    timezone('utc', now()),
    timezone('utc', now())
  )
  on conflict (post_id, user_id)
  do update
    set emoji = excluded.emoji,
        updated_at = timezone('utc', now());

  perform public.citisense_sync_feedback_mood(p_post_id);

  return jsonb_build_object(
    'post_id', p_post_id,
    'user_id', v_user_id,
    'emoji', p_emoji,
    'reaction_label', v_reaction_label
  );
end
$$;

create or replace function public.citisense_reaction_change_trigger()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  perform public.citisense_sync_feedback_mood(coalesce(new.post_id, old.post_id));
  return coalesce(new, old);
end
$$;

drop trigger if exists citisense_reaction_change_trigger on public.reactions;

create trigger citisense_reaction_change_trigger
after insert or update or delete on public.reactions
for each row
execute function public.citisense_reaction_change_trigger();

create or replace function public.citisense_scope_mood_summary(
  p_days integer default 7,
  p_barangay text default null,
  p_service text default null,
  p_office text default null
)
returns table (
  mood text,
  emoji text,
  total bigint,
  breakdown jsonb,
  confidence double precision,
  source text
)
language sql
stable
as $$
  with filtered as (
    select
      lower(trim(coalesce(f.final_mood, ''))) as mood,
      f.created_at
    from public.feedbacks f
    where f.final_mood is not null
      and (
        p_days is null
        or p_days <= 0
        or f.created_at >= timezone('utc', now()) - make_interval(days => p_days)
      )
      and (
        p_barangay is null
        or lower(coalesce(
          to_jsonb(f)->>'barangay',
          to_jsonb(f)->>'incident_location',
          to_jsonb(f)->>'location',
          ''
        )) like '%' || lower(p_barangay) || '%'
      )
      and (
        p_service is null
        or lower(coalesce(
          to_jsonb(f)->>'service',
          to_jsonb(f)->>'subcategory',
          to_jsonb(f)->>'category',
          ''
        )) = lower(p_service)
      )
      and (
        p_office is null
        or lower(coalesce(
          public.citisense_office_for_service(coalesce(
            to_jsonb(f)->>'service',
            to_jsonb(f)->>'subcategory',
            to_jsonb(f)->>'category',
            ''
          )),
          ''
        )) = lower(p_office)
      )
  ),
  counts as (
    select
      mood,
      count(*)::bigint as amount,
      max(created_at) as latest_at
    from filtered
    group by 1
  ),
  totals as (
    select
      coalesce(sum(amount), 0)::bigint as total,
      jsonb_build_object(
        'grateful', coalesce((select amount from counts where mood = 'grateful'), 0),
        'satisfied', coalesce((select amount from counts where mood = 'satisfied'), 0),
        'sad', coalesce((select amount from counts where mood = 'sad'), 0),
        'angry', coalesce((select amount from counts where mood = 'angry'), 0)
      ) as breakdown
    from counts
  ),
  top_amount as (
    select max(amount) as amount
    from counts
  ),
  top_candidates as (
    select c.*
    from counts c
    join top_amount t on c.amount = t.amount
  ),
  latest_top as (
    select max(latest_at) as latest_at
    from top_candidates
  ),
  chosen as (
    select
      tc.mood,
      tc.amount,
      tc.latest_at,
      (
        select count(*)
        from top_candidates tc2
        join latest_top lt2 on tc2.latest_at = lt2.latest_at
      ) as latest_tied
    from top_candidates tc
    join latest_top lt on tc.latest_at = lt.latest_at
    order by tc.mood
    limit 1
  )
  select
    case
      when t.total = 0 then null
      else c.mood
    end as mood,
    public.citisense_mood_display_emoji(
      case
        when t.total = 0 then null
        else c.mood
      end
    ) as emoji,
    t.total,
    t.breakdown,
    case
      when c.mood is not null and t.total > 0
      then c.amount::double precision / t.total
      else 0
    end as confidence,
    case
      when t.total = 0 then 'none'
      else 'posts'
    end as source
  from totals t
  left join chosen c on true
$$;

create or replace function public.citisense_sync_all_feedback_moods()
returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
  v_updated bigint := 0;
begin
  with summaries as (
    select
      f.id,
      s.reaction_total,
      s.reaction_breakdown,
      s.final_mood,
      s.mood_confidence,
      s.mood_source
    from public.feedbacks f
    cross join lateral public.citisense_feedback_final_mood_summary(f.id) s
  )
  update public.feedbacks f
  set
    reacts_count = coalesce(s.reaction_total, 0),
    reaction_breakdown = coalesce(s.reaction_breakdown, public.citisense_empty_mood_breakdown()),
    final_mood = s.final_mood,
    mood_confidence = coalesce(s.mood_confidence, 0),
    mood_source = coalesce(s.mood_source, 'none')
  from summaries s
  where f.id = s.id;

  get diagnostics v_updated = row_count;
  return v_updated;
end
$$;

create or replace function public.get_city_mood(p_days integer default 7)
returns table (
  mood text,
  emoji text,
  total bigint,
  breakdown jsonb,
  confidence double precision,
  source text
)
language sql
stable
as $$
  select *
  from public.citisense_scope_mood_summary(p_days => p_days)
$$;

create or replace function public.get_barangay_mood(
  p_barangay text,
  p_days integer default 7
)
returns table (
  mood text,
  emoji text,
  total bigint,
  breakdown jsonb,
  confidence double precision,
  source text
)
language sql
stable
as $$
  select *
  from public.citisense_scope_mood_summary(
    p_days => p_days,
    p_barangay => p_barangay
  )
$$;

create or replace function public.get_category_mood(
  p_service text,
  p_days integer default 7
)
returns table (
  mood text,
  emoji text,
  total bigint,
  breakdown jsonb,
  confidence double precision,
  source text
)
language sql
stable
as $$
  select *
  from public.citisense_scope_mood_summary(
    p_days => p_days,
    p_service => p_service
  )
$$;

create or replace function public.get_office_mood(
  p_office text,
  p_days integer default 7
)
returns table (
  mood text,
  emoji text,
  total bigint,
  breakdown jsonb,
  confidence double precision,
  source text
)
language sql
stable
as $$
  select *
  from public.citisense_scope_mood_summary(
    p_days => p_days,
    p_office => p_office
  )
$$;

comment on function public.react_post(uuid, text) is
  'Stores exactly one active reaction per user per feedback and refreshes the persisted caption-plus-reactions mood fields.';

comment on function public.get_city_mood(integer) is
  'Post-level city mood summary. Aggregates each feedback final_mood into one collective city mood.';

comment on function public.get_barangay_mood(text, integer) is
  'Post-level barangay mood summary using the selected date range.';

comment on function public.get_category_mood(text, integer) is
  'Post-level service-category mood summary using the selected date range.';

comment on function public.get_office_mood(text, integer) is
  'Post-level office mood summary derived from the shared service-to-office mapping.';

select public.citisense_sync_all_feedback_moods();

comment on function public.citisense_prediction_is_public(double precision) is
  'Returns true only when a stored model prediction meets the minimum public fallback confidence threshold of 0.30.';

create or replace function public.citisense_normalize_reaction_mood(p_value text)
returns text
language sql
immutable
as $$
  select case lower(replace(trim(coalesce(p_value, '')), U&'\FE0F', ''))
    when '🥰' then 'grateful'
    when '❤' then 'grateful'
    when 'grateful' then 'grateful'
    when '🙂' then 'satisfied'
    when 'satisfied' then 'satisfied'
    when '😢' then 'sad'
    when 'sad' then 'sad'
    when '😡' then 'angry'
    when 'angry' then 'angry'
    else null
  end
$$;

create or replace function public.citisense_mood_display_emoji(p_mood text)
returns text
language sql
immutable
as $$
  select case lower(trim(coalesce(p_mood, '')))
    when 'grateful' then '🥰'
    when 'satisfied' then '🙂'
    when 'sad' then '😢'
    when 'angry' then '😡'
    else '😶'
  end
$$;

commit;
