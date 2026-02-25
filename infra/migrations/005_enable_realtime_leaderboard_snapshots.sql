-- Enable Supabase Realtime replication for leaderboard snapshot streams.

do $$
begin
  if exists (
    select 1
    from pg_publication
    where pubname = 'supabase_realtime'
  ) then
    if not exists (
      select 1
      from pg_publication_tables
      where pubname = 'supabase_realtime'
        and schemaname = 'public'
        and tablename = 'leaderboard_snapshots'
    ) then
      alter publication supabase_realtime add table public.leaderboard_snapshots;
    end if;

    if not exists (
      select 1
      from pg_publication_tables
      where pubname = 'supabase_realtime'
        and schemaname = 'public'
        and tablename = 'league_snapshots'
    ) then
      alter publication supabase_realtime add table public.league_snapshots;
    end if;
  end if;
end $$;
