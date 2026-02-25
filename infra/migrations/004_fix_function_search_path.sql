-- Fix mutable search_path warnings for helper functions used by RLS policies.

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
