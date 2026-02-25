-- Apex Predict initial schema (PostgreSQL / Supabase)

create type session_state as enum ('SCHEDULED', 'OPEN', 'LOCKED', 'SCORING', 'FINALIZED');
create type session_type as enum ('FP1', 'FP2', 'FP3', 'SPRINT_QUALIFYING', 'SPRINT', 'QUALIFYING', 'RACE');
create type question_type as enum (
  'POLE',
  'WINNER',
  'TOP5',
  'DNF',
  'FASTEST_LAP',
  'SAFETY_CAR',
  'MIDFIELD_CONSTRUCTOR',
  'FIRST_PIT_STOP_TEAM',
  'FIRST_SAFETY_CAR_LAP'
);
create type league_visibility as enum ('PRIVATE', 'PUBLIC');
create type join_policy as enum ('INVITE_ONLY', 'OPEN');
create type moderation_state as enum ('ACTIVE', 'REVIEW', 'SUSPENDED');
create type member_role as enum ('OWNER', 'ADMIN', 'MEMBER');
create type report_status as enum ('OPEN', 'RESOLVED', 'DISMISSED');
create type job_status as enum ('PENDING', 'RUNNING', 'SUCCESS', 'FAILED');
create type leaderboard_scope as enum ('GLOBAL', 'LEAGUE');

create table if not exists users (
  id text primary key,
  email text unique,
  created_at timestamptz not null default now()
);

create table if not exists profiles (
  user_id text primary key references users(id),
  username text not null unique,
  avatar_url text,
  total_points numeric(10,2) not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists seasons (
  id text primary key,
  year integer not null unique,
  is_current boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists events (
  id text primary key,
  season_id text not null references seasons(id),
  name text not null,
  slug text not null unique,
  country text not null,
  start_at timestamptz not null,
  end_at timestamptz not null,
  created_at timestamptz not null default now()
);

create table if not exists sessions (
  id text primary key,
  event_id text not null references events(id),
  name text not null,
  session_type session_type not null,
  state session_state not null default 'SCHEDULED',
  starts_at timestamptz not null,
  lock_at timestamptz not null,
  ends_at timestamptz not null,
  created_at timestamptz not null default now()
);

create table if not exists drivers (
  id text primary key,
  code text not null unique,
  full_name text not null
);

create table if not exists constructors (
  id text primary key,
  code text not null unique,
  name text not null
);

create table if not exists scoring_rules (
  id text primary key,
  name text not null unique,
  question_type question_type not null,
  base_points integer not null,
  metadata_json jsonb not null default '{}'::jsonb,
  created_by text references users(id),
  created_at timestamptz not null default now()
);

create table if not exists question_templates (
  id text primary key,
  session_type session_type not null,
  question_type question_type not null,
  prompt text not null,
  options jsonb not null,
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists question_instances (
  id text primary key,
  session_id text not null references sessions(id),
  question_type question_type not null,
  prompt text not null,
  options jsonb not null,
  lock_at timestamptz not null,
  scoring_rule_id text not null references scoring_rules(id),
  correct_option text,
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists predictions (
  id text primary key,
  user_id text not null references users(id),
  session_id text not null references sessions(id),
  client_version text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint uq_prediction_user_session unique(user_id, session_id)
);

create table if not exists prediction_answers (
  id text primary key,
  prediction_id text not null references predictions(id) on delete cascade,
  user_id text not null references users(id),
  question_instance_id text not null references question_instances(id),
  selected_option text not null,
  created_at timestamptz not null default now(),
  constraint uq_prediction_user_question unique(user_id, question_instance_id)
);

create table if not exists prediction_confidence_allocations (
  id text primary key,
  prediction_id text not null references predictions(id) on delete cascade,
  question_instance_id text not null references question_instances(id),
  credits integer not null
);

create table if not exists score_entries (
  id text primary key,
  user_id text not null references users(id),
  session_id text not null references sessions(id),
  question_instance_id text references question_instances(id),
  base_points numeric(10,2) not null default 0,
  confidence_multiplier numeric(10,2) not null default 1,
  awarded_points numeric(10,2) not null default 0,
  reason text not null default 'SESSION_SCORE',
  is_correction boolean not null default false,
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint uq_score_entry_reason unique(user_id, session_id, question_instance_id, reason)
);

create table if not exists leaderboard_snapshots (
  id text primary key,
  scope leaderboard_scope not null,
  scope_id text,
  session_id text references sessions(id),
  computed_at timestamptz not null default now(),
  rows_json jsonb not null
);

create table if not exists leagues (
  id text primary key,
  name text not null,
  visibility league_visibility not null,
  join_policy join_policy not null,
  moderation_state moderation_state not null default 'ACTIVE',
  invite_code text unique,
  created_by text not null references users(id),
  created_at timestamptz not null default now()
);

create table if not exists league_members (
  id text primary key,
  league_id text not null references leagues(id),
  user_id text not null references users(id),
  role member_role not null default 'MEMBER',
  joined_at timestamptz not null default now(),
  constraint uq_league_member unique(league_id, user_id)
);

create table if not exists league_invites (
  id text primary key,
  league_id text not null references leagues(id),
  code text not null unique,
  created_by text not null references users(id),
  expires_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists league_snapshots (
  id text primary key,
  league_id text not null references leagues(id),
  computed_at timestamptz not null default now(),
  rows_json jsonb not null
);

create table if not exists ai_previews (
  id text primary key,
  event_id text not null references events(id) unique,
  summary text not null,
  confidence_band text not null,
  data_sources jsonb not null,
  generated_at timestamptz not null default now()
);

create table if not exists ai_insights (
  id text primary key,
  session_id text not null references sessions(id),
  question_instance_id text references question_instances(id),
  explanation text not null,
  confidence_band text not null,
  data_sources jsonb not null,
  generated_at timestamptz not null default now()
);

create table if not exists ai_generation_logs (
  id text primary key,
  entity_type text not null,
  entity_id text not null,
  status job_status not null,
  prompt_hash text not null,
  provider text not null,
  created_at timestamptz not null default now()
);

create table if not exists provider_sync_logs (
  id text primary key,
  provider_name text not null,
  resource text not null,
  status job_status not null,
  details text,
  started_at timestamptz not null default now(),
  finished_at timestamptz
);

create table if not exists job_runs (
  id text primary key,
  idempotency_key text not null unique,
  job_type text not null,
  status job_status not null,
  payload_json jsonb not null default '{}'::jsonb,
  result_json jsonb not null default '{}'::jsonb,
  error_message text,
  created_at timestamptz not null default now(),
  finished_at timestamptz
);

create table if not exists moderation_reports (
  id text primary key,
  reporter_id text not null references users(id),
  target_type text not null,
  target_id text not null,
  reason text not null,
  status report_status not null default 'OPEN',
  created_at timestamptz not null default now()
);

create table if not exists moderation_actions (
  id text primary key,
  report_id text not null references moderation_reports(id),
  actor_id text not null references users(id),
  action text not null,
  notes text,
  created_at timestamptz not null default now()
);

create table if not exists audit_logs (
  id text primary key,
  actor_id text references users(id),
  action text not null,
  entity_type text not null,
  entity_id text not null,
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- Supabase RLS policy hooks (adjust auth mapping before production)
alter table profiles enable row level security;
alter table predictions enable row level security;
alter table prediction_answers enable row level security;
alter table prediction_confidence_allocations enable row level security;
alter table league_members enable row level security;
alter table moderation_reports enable row level security;
