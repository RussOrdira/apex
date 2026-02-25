-- Supabase production auth + RLS hardening and ingestion metadata columns.

alter table if exists events add column if not exists external_id text;
alter table if exists sessions add column if not exists external_id text;
alter table if exists sessions add column if not exists provider_name text;

create index if not exists idx_events_external_id on events(external_id);
create index if not exists idx_sessions_external_id on sessions(external_id);

create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.users (id, email, created_at)
  values (new.id::text, new.email, now())
  on conflict (id) do update set email = excluded.email;

  insert into public.profiles (user_id, username, created_at)
  values (
    new.id::text,
    coalesce(nullif(split_part(new.email, '@', 1), ''), 'user_' || substr(new.id::text, 1, 8)),
    now()
  )
  on conflict (user_id) do nothing;

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_auth_user();

create or replace function public.is_league_member(target_league_id text)
returns boolean
language sql
stable
set search_path = public
as $$
  select exists (
    select 1
    from public.league_members lm
    where lm.league_id = target_league_id
      and lm.user_id = auth.uid()::text
  );
$$;

create or replace function public.is_league_admin(target_league_id text)
returns boolean
language sql
stable
set search_path = public
as $$
  select exists (
    select 1
    from public.league_members lm
    where lm.league_id = target_league_id
      and lm.user_id = auth.uid()::text
      and lm.role in ('OWNER'::member_role, 'ADMIN'::member_role)
  );
$$;

alter table profiles enable row level security;
alter table predictions enable row level security;
alter table prediction_answers enable row level security;
alter table prediction_confidence_allocations enable row level security;
alter table score_entries enable row level security;
alter table leagues enable row level security;
alter table league_members enable row level security;
alter table league_invites enable row level security;
alter table league_snapshots enable row level security;
alter table moderation_reports enable row level security;
alter table moderation_actions enable row level security;

-- Profiles

drop policy if exists profiles_select_public on profiles;
create policy profiles_select_public on profiles
for select
using (true);

drop policy if exists profiles_insert_own on profiles;
create policy profiles_insert_own on profiles
for insert
with check (auth.uid()::text = user_id);

drop policy if exists profiles_update_own on profiles;
create policy profiles_update_own on profiles
for update
using (auth.uid()::text = user_id)
with check (auth.uid()::text = user_id);

-- Predictions and prediction artifacts

drop policy if exists predictions_select_own on predictions;
create policy predictions_select_own on predictions
for select
using (auth.uid()::text = user_id);

drop policy if exists predictions_insert_own on predictions;
create policy predictions_insert_own on predictions
for insert
with check (auth.uid()::text = user_id);

drop policy if exists predictions_update_own on predictions;
create policy predictions_update_own on predictions
for update
using (auth.uid()::text = user_id)
with check (auth.uid()::text = user_id);

drop policy if exists prediction_answers_select_own on prediction_answers;
create policy prediction_answers_select_own on prediction_answers
for select
using (auth.uid()::text = user_id);

drop policy if exists prediction_answers_insert_own on prediction_answers;
create policy prediction_answers_insert_own on prediction_answers
for insert
with check (auth.uid()::text = user_id);

drop policy if exists prediction_answers_update_own on prediction_answers;
create policy prediction_answers_update_own on prediction_answers
for update
using (auth.uid()::text = user_id)
with check (auth.uid()::text = user_id);

drop policy if exists prediction_allocations_select_own on prediction_confidence_allocations;
create policy prediction_allocations_select_own on prediction_confidence_allocations
for select
using (
  exists (
    select 1 from public.predictions p
    where p.id = prediction_confidence_allocations.prediction_id
      and p.user_id = auth.uid()::text
  )
);

drop policy if exists prediction_allocations_insert_own on prediction_confidence_allocations;
create policy prediction_allocations_insert_own on prediction_confidence_allocations
for insert
with check (
  exists (
    select 1 from public.predictions p
    where p.id = prediction_confidence_allocations.prediction_id
      and p.user_id = auth.uid()::text
  )
);

-- Score visibility (own only)

drop policy if exists score_entries_select_own on score_entries;
create policy score_entries_select_own on score_entries
for select
using (auth.uid()::text = user_id);

-- Leagues and membership

drop policy if exists leagues_select_visible on leagues;
create policy leagues_select_visible on leagues
for select
using (
  visibility = 'PUBLIC'::league_visibility
  or created_by = auth.uid()::text
  or public.is_league_member(id)
);

drop policy if exists leagues_insert_own on leagues;
create policy leagues_insert_own on leagues
for insert
with check (created_by = auth.uid()::text);

drop policy if exists leagues_update_owner on leagues;
create policy leagues_update_owner on leagues
for update
using (
  created_by = auth.uid()::text
  or public.is_league_admin(id)
)
with check (
  created_by = auth.uid()::text
  or public.is_league_admin(id)
);

drop policy if exists league_members_select_scoped on league_members;
create policy league_members_select_scoped on league_members
for select
using (
  auth.uid()::text = user_id
  or public.is_league_member(league_id)
);

drop policy if exists league_members_insert_self_or_admin on league_members;
create policy league_members_insert_self_or_admin on league_members
for insert
with check (
  auth.uid()::text = user_id
  or public.is_league_admin(league_id)
);

drop policy if exists league_invites_select_admin on league_invites;
create policy league_invites_select_admin on league_invites
for select
using (public.is_league_admin(league_id));

drop policy if exists league_invites_insert_admin on league_invites;
create policy league_invites_insert_admin on league_invites
for insert
with check (public.is_league_admin(league_id));

drop policy if exists league_snapshots_select_member on league_snapshots;
create policy league_snapshots_select_member on league_snapshots
for select
using (public.is_league_member(league_id));

-- Moderation

drop policy if exists moderation_reports_select_own on moderation_reports;
create policy moderation_reports_select_own on moderation_reports
for select
using (auth.uid()::text = reporter_id);

drop policy if exists moderation_reports_insert_own on moderation_reports;
create policy moderation_reports_insert_own on moderation_reports
for insert
with check (auth.uid()::text = reporter_id);

drop policy if exists moderation_actions_select_admin on moderation_actions;
create policy moderation_actions_select_admin on moderation_actions
for select
using (true);
