# supabase/

Database schema for the Supabase project, as plain SQL. See the README's [Database](../README.md#database) section for the diagram, the RLS summary and setup steps.

## migrations/ (apply in filename order)

| File | What it does |
|---|---|
| `20261017093040_create_tables.sql` | `transactions`, `alerts`, `feedback`, `model_runs`; alert trigger for MEDIUM/HIGH rows; indexes; RLS switched on (deny-all) |
| `20261017093157_rls_policies.sql` | Grants and policies: anon gets nothing; analysts read everything, update `alerts.status` only, insert their own feedback; review-stamp trigger |
| `20261017094224_realtime.sql` | Adds `transactions` and `alerts` to the `supabase_realtime` publication |

File names match the versions recorded in the project (`supabase_migrations.schema_migrations`), so the Supabase CLI sees them as already applied.

## tests/

`rls_checks.sql`: run it in the SQL editor as the owner. It creates test users and rows, tries every allowed and forbidden action as `anon` and as an analyst, and rolls everything back. Success prints `ALL RLS CHECKS PASSED`.
