-- Phase 4 step 4: stream inserts/updates on transactions and alerts to the dashboard.
--
-- Realtime checks each subscriber against the table's RLS select policy, so only
-- logged-in analysts receive these events; anon subscribers get nothing.
alter publication supabase_realtime add table public.transactions, public.alerts;
