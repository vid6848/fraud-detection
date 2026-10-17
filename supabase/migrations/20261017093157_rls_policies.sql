-- Phase 4 step 2: who may do what.
--
--   service_role  (API, scripts; server-side only)  bypasses RLS: writes transactions, model_runs
--   authenticated (logged-in analysts)              read all four tables,
--                                                   change alerts.status, add their own feedback
--   anon          (no login)                        nothing at all
--
-- Two layers: table/column GRANTs decide which actions a role may attempt at all,
-- and RLS policies decide which rows those actions may touch.

-- ---------------------------------------------------------------------------
-- Grants. Supabase grants everything to anon/authenticated by default; start
-- from nothing and add back only what analysts need.
-- ---------------------------------------------------------------------------
revoke all on public.transactions, public.alerts, public.feedback, public.model_runs
    from anon, authenticated;

grant select on public.transactions, public.alerts, public.feedback, public.model_runs
    to authenticated;
grant update (status) on public.alerts to authenticated;           -- only the status column
grant insert (alert_id, label, note) on public.feedback to authenticated;  -- analyst comes from the login

-- ---------------------------------------------------------------------------
-- Policies (authenticated only; anon has no policy and no grants)
-- ---------------------------------------------------------------------------
create policy "analysts read transactions" on public.transactions
    for select to authenticated using (true);

create policy "analysts read alerts" on public.alerts
    for select to authenticated using (true);

create policy "analysts review alerts" on public.alerts
    for update to authenticated
    using ((select auth.uid()) is not null)
    with check ((select auth.uid()) is not null);

create policy "analysts read feedback" on public.feedback
    for select to authenticated using (true);

create policy "analysts add own feedback" on public.feedback
    for insert to authenticated
    with check (analyst = (select auth.uid()));

create policy "analysts read model runs" on public.model_runs
    for select to authenticated using (true);

-- ---------------------------------------------------------------------------
-- Review stamp: whoever changes an alert's status is recorded server-side, so
-- reviewed_by / reviewed_at can't be forged (analysts can't write them anyway).
-- ---------------------------------------------------------------------------
create function public.stamp_alert_review()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    if new.status is distinct from old.status then
        if new.status = 'open' then
            new.reviewed_by := null;
            new.reviewed_at := null;
        else
            new.reviewed_by := auth.uid();
            new.reviewed_at := now();
        end if;
    end if;
    return new;
end;
$$;

revoke execute on function public.stamp_alert_review() from public, anon, authenticated;

create trigger alerts_stamp_review
before update on public.alerts
for each row execute function public.stamp_alert_review();
