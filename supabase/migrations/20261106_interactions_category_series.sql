-- Store each clicked event's category and series with the click, so the
-- recommender keeps the signal after one-off events leave the calendar.
-- Safe to run more than once. Run in Supabase → SQL Editor, BEFORE deploying
-- the backend that writes these columns.

alter table public.interactions
  add column if not exists category text,
  add column if not exists series_key text;

-- Per-user lookups (one query per recommendation request).
create index if not exists interactions_hashed_netid_idx
  on public.interactions (hashed_netid);
