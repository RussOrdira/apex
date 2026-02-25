-- RLS hardening for all public tables surfaced by Supabase linter.

-- Enable RLS on every remaining public table flagged by linter.
alter table if exists users enable row level security;
alter table if exists seasons enable row level security;
alter table if exists events enable row level security;
alter table if exists sessions enable row level security;
alter table if exists drivers enable row level security;
alter table if exists constructors enable row level security;
alter table if exists scoring_rules enable row level security;
alter table if exists question_templates enable row level security;
alter table if exists question_instances enable row level security;
alter table if exists leaderboard_snapshots enable row level security;
alter table if exists ai_previews enable row level security;
alter table if exists ai_insights enable row level security;
alter table if exists ai_generation_logs enable row level security;
alter table if exists provider_sync_logs enable row level security;
alter table if exists job_runs enable row level security;
alter table if exists audit_logs enable row level security;

-- users: allow users to see/update themselves; allow trusted server roles to insert.
drop policy if exists users_select_own on users;
create policy users_select_own on users
for select
using (auth.uid()::text = id);

drop policy if exists users_update_own on users;
create policy users_update_own on users
for update
using (auth.uid()::text = id)
with check (auth.uid()::text = id);

drop policy if exists users_insert_internal on users;
create policy users_insert_internal on users
for insert
with check (current_user in ('postgres', 'supabase_auth_admin', 'service_role'));

-- Public read-only race catalog tables.
drop policy if exists seasons_read_public on seasons;
create policy seasons_read_public on seasons
for select
using (true);

drop policy if exists events_read_public on events;
create policy events_read_public on events
for select
using (true);

drop policy if exists sessions_read_public on sessions;
create policy sessions_read_public on sessions
for select
using (true);

drop policy if exists drivers_read_public on drivers;
create policy drivers_read_public on drivers
for select
using (true);

drop policy if exists constructors_read_public on constructors;
create policy constructors_read_public on constructors
for select
using (true);

-- Internal tables: explicit deny-all policies for PostgREST roles.
drop policy if exists scoring_rules_deny_all on scoring_rules;
create policy scoring_rules_deny_all on scoring_rules
for all
using (false)
with check (false);

drop policy if exists question_templates_deny_all on question_templates;
create policy question_templates_deny_all on question_templates
for all
using (false)
with check (false);

drop policy if exists question_instances_deny_all on question_instances;
create policy question_instances_deny_all on question_instances
for all
using (false)
with check (false);

drop policy if exists leaderboard_snapshots_deny_all on leaderboard_snapshots;
create policy leaderboard_snapshots_deny_all on leaderboard_snapshots
for all
using (false)
with check (false);

drop policy if exists ai_previews_deny_all on ai_previews;
create policy ai_previews_deny_all on ai_previews
for all
using (false)
with check (false);

drop policy if exists ai_insights_deny_all on ai_insights;
create policy ai_insights_deny_all on ai_insights
for all
using (false)
with check (false);

drop policy if exists ai_generation_logs_deny_all on ai_generation_logs;
create policy ai_generation_logs_deny_all on ai_generation_logs
for all
using (false)
with check (false);

drop policy if exists provider_sync_logs_deny_all on provider_sync_logs;
create policy provider_sync_logs_deny_all on provider_sync_logs
for all
using (false)
with check (false);

drop policy if exists job_runs_deny_all on job_runs;
create policy job_runs_deny_all on job_runs
for all
using (false)
with check (false);

drop policy if exists audit_logs_deny_all on audit_logs;
create policy audit_logs_deny_all on audit_logs
for all
using (false)
with check (false);

-- Tighten moderation_actions: not directly readable from public API.
drop policy if exists moderation_actions_select_admin on moderation_actions;
drop policy if exists moderation_actions_deny_all on moderation_actions;
create policy moderation_actions_deny_all on moderation_actions
for all
using (false)
with check (false);
