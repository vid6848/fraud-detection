-- RLS / grant checks for the Phase 4 tables.
--
-- Run as the database owner (Supabase SQL editor, or the MCP `execute_sql` tool).
-- Everything happens inside one transaction that is rolled back at the end, so
-- the test user and rows it creates never persist. Any broken rule raises
-- "RLS CHECK FAILED: ..."; success returns a single row "ALL RLS CHECKS PASSED".

begin;

-- Run `stmt` as `role_name` (with an optional user id in the JWT claims) and
-- return the number of rows it touched. The role switch is local to this call.
create function pg_temp.run_as(role_name text, user_id uuid, stmt text)
returns bigint language plpgsql as $$
declare
    n bigint;
begin
    perform set_config('request.jwt.claims',
        json_build_object('role', role_name, 'sub', user_id)::text, true);
    perform set_config('role', role_name, true);
    execute stmt;
    get diagnostics n = row_count;
    reset role;
    return n;
end;
$$;

-- `stmt` must fail with "permission denied" / RLS violation (SQLSTATE 42501).
create function pg_temp.expect_denied(role_name text, user_id uuid, label text, stmt text)
returns void language plpgsql as $$
begin
    perform pg_temp.run_as(role_name, user_id, stmt);
    raise exception 'RLS CHECK FAILED: % was allowed', label;
exception when insufficient_privilege then
    null;  -- denied, as expected (the role switch is rolled back with the error)
end;
$$;

create function pg_temp.expect(ok boolean, label text)
returns void language plpgsql as $$
begin
    if not coalesce(ok, false) then
        raise exception 'RLS CHECK FAILED: %', label;
    end if;
end;
$$;

do $$
declare
    analyst_id  constant uuid := '11111111-1111-4111-8111-111111111111';
    stranger_id constant uuid := '22222222-2222-4222-8222-222222222222';
    tx_id    constant uuid := '33333333-3333-4333-8333-333333333333';
    alert    bigint;
    tbl      text;
    n        bigint;
    row_     record;
    insert_tx constant text := format(
        $f$insert into public.transactions (id, time_seconds, amount, hour_of_day, features,
           probability, risk_level, model_version)
           values (%L, 0, 1, 0, '{}', 0.1, 'LOW', 'rls-check')$f$, gen_random_uuid());
begin
    -- Setup as owner: two auth users and one HIGH transaction (the trigger adds its alert).
    insert into auth.users (id, email) values
        (analyst_id, 'rls-analyst@example.test'), (stranger_id, 'rls-stranger@example.test');
    insert into public.transactions (id, time_seconds, amount, hour_of_day, features,
                                     probability, risk_level, model_version)
    values (tx_id, 3600, 99.5, 1, '{"V1": 1.0}', 0.93, 'HIGH', 'rls-check');
    select id into alert from public.alerts where transaction_id = tx_id;
    perform pg_temp.expect(alert is not null, 'HIGH transaction did not create an alert');

    -- anon: no access to anything
    foreach tbl in array array['transactions', 'alerts', 'feedback', 'model_runs'] loop
        perform pg_temp.expect_denied('anon', null, 'anon select ' || tbl,
            format('select * from public.%I', tbl));
    end loop;
    perform pg_temp.expect_denied('anon', null, 'anon insert transactions', insert_tx);
    perform pg_temp.expect_denied('anon', null, 'anon update alerts',
        format('update public.alerts set status = %L where id = %s', 'false_alarm', alert));
    perform pg_temp.expect_denied('anon', null, 'anon insert feedback',
        format('insert into public.feedback (alert_id, label) values (%s, %L)', alert, 'false_alarm'));

    -- analyst: may read
    foreach tbl in array array['transactions', 'alerts', 'feedback', 'model_runs'] loop
        perform pg_temp.run_as('authenticated', analyst_id, format('select * from public.%I', tbl));
    end loop;
    n := pg_temp.run_as('authenticated', analyst_id,
        format('select * from public.transactions where id = %L', tx_id));
    perform pg_temp.expect(n = 1, 'analyst cannot see the stored transaction');

    -- analyst: may not write transactions or model_runs
    perform pg_temp.expect_denied('authenticated', analyst_id, 'analyst insert transactions', insert_tx);
    perform pg_temp.expect_denied('authenticated', analyst_id, 'analyst update transactions',
        format('update public.transactions set probability = 0 where id = %L', tx_id));
    perform pg_temp.expect_denied('authenticated', analyst_id, 'analyst delete transactions',
        format('delete from public.transactions where id = %L', tx_id));
    perform pg_temp.expect_denied('authenticated', analyst_id, 'analyst insert model_runs',
        $f$insert into public.model_runs (version, metrics, trained_at) values ('x', '{}', now())$f$);

    -- analyst: only alerts.status is writable, and the review stamp is set server-side
    perform pg_temp.expect_denied('authenticated', analyst_id, 'analyst update alerts.severity',
        format('update public.alerts set severity = %L where id = %s', 'MEDIUM', alert));
    perform pg_temp.expect_denied('authenticated', analyst_id, 'analyst forge alerts.reviewed_by',
        format('update public.alerts set reviewed_by = %L where id = %s', stranger_id, alert));
    perform pg_temp.expect_denied('authenticated', analyst_id, 'analyst delete alerts',
        format('delete from public.alerts where id = %s', alert));
    n := pg_temp.run_as('authenticated', analyst_id,
        format('update public.alerts set status = %L where id = %s', 'confirmed_fraud', alert));
    perform pg_temp.expect(n = 1, 'analyst cannot update alert status');
    select reviewed_by, reviewed_at into row_ from public.alerts where id = alert;
    perform pg_temp.expect(row_.reviewed_by = analyst_id and row_.reviewed_at is not null,
        'review stamp not set to the analyst');

    -- a token with no user id can't review alerts (policy needs auth.uid())
    n := pg_temp.run_as('authenticated', null,
        format('update public.alerts set status = %L where id = %s', 'false_alarm', alert));
    perform pg_temp.expect(n = 0, 'update without a user id was allowed');

    -- analyst: may add feedback as themselves only
    n := pg_temp.run_as('authenticated', analyst_id,
        format('insert into public.feedback (alert_id, label, note) values (%s, %L, %L)',
               alert, 'confirmed_fraud', 'rls check'));
    perform pg_temp.expect(n = 1, 'analyst cannot insert feedback');
    perform pg_temp.expect(
        (select analyst_ok from (select bool_and(f.analyst = analyst_id) as analyst_ok
                                 from public.feedback f where f.alert_id = alert) s),
        'feedback.analyst not set from the login');
    perform pg_temp.expect_denied('authenticated', analyst_id, 'analyst insert feedback as someone else',
        format('insert into public.feedback (alert_id, label, analyst) values (%s, %L, %L)',
               alert, 'false_alarm', stranger_id));
    perform pg_temp.expect_denied('authenticated', analyst_id, 'analyst update feedback',
        format('update public.feedback set label = %L where alert_id = %s', 'false_alarm', alert));
    perform pg_temp.expect_denied('authenticated', analyst_id, 'analyst delete feedback',
        format('delete from public.feedback where alert_id = %s', alert));
end;
$$;

select 'ALL RLS CHECKS PASSED' as result;

rollback;
