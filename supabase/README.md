# Database (Supabase)

One table: `interactions` (one row per event click). The backend uses the service key; nothing else reads the table.

## Applying a migration

1. **Dry run:** in Supabase → SQL Editor, run the checks below and confirm the current state.
2. Run the migration file from `migrations/`.
3. Run the checks again; the new columns and index should be listed.

```sql
-- Columns
select column_name, data_type, is_nullable
from information_schema.columns
where table_schema = 'public' and table_name = 'interactions'
order by ordinal_position;

-- Indexes
select indexname, indexdef from pg_indexes
where schemaname = 'public' and tablename = 'interactions';

-- Row-level security (should be true: with RLS on and no policies, only the service key can read or write)
select relrowsecurity from pg_class where oid = 'public.interactions'::regclass;

-- Row count (unchanged by migrations)
select count(*) from public.interactions;
```

## Migrations

| File | What |
|---|---|
| `20261106_interactions_category_series.sql` | Adds nullable `category` and `series_key`; index on `hashed_netid` |
