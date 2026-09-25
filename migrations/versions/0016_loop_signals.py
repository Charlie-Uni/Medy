"""M4-01 (record 79): signals correlated to traces for Observe, the Loop's case table, and the Loop role's read path.

- `trace_signals`: one row per trace joining feedback (up / down / corrections), the escalation (status, reason codes,
  resolution), verifier failure, safety flags and replay drift — the single source Execute writes and Observe reads
  (baseline 5.8). A `security_invoker` view: row security of the base tables applies to whoever queries it.
- `escalations.resolution`: the human outcome of an escalation (`confirmed_issue` / `false_alarm` / `resolved_manually`),
  set by the admin role; the 0011 guard already restricts every other column.
- `bad_cases`: the Loop's working table — one case per trace, the signal snapshot that opened it, the label, and the
  attribution columns M4-02 fills (class, confidence, who attributed, the human override). Identity, signals and label
  are immutable; `human_override` can only be written by the admin role (a human), never by the Loop role.
- `medops_loop_role` may read the signal sources and read / open / attribute cases; it still cannot write anything
  released (INV-AUTH-05, proven by M4-04).

Revision ID: 0016
Revises: 0015
"""

from __future__ import annotations

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

UP = r"""
alter table escalations add column resolution text
    check (resolution in ('confirmed_issue', 'false_alarm', 'resolved_manually'));
comment on column escalations.resolution is 'M4-01: human outcome of the escalation; admin role only (the 0011 guard keeps every other column immutable).';

create table bad_cases (
    case_id uuid primary key default gen_random_uuid(),
    trace_id text not null unique references traces (trace_id),
    dept dept not null,
    opened_at timestamptz not null default now(),
    signals jsonb not null,
    label text not null check (label in ('bad', 'good')),
    reasons text[] not null default '{}',
    attribution text check (attribution in ('retrieval', 'intent', 'generation', 'knowledge_gap', 'safety')),
    confidence numeric(4, 3) check (confidence >= 0 and confidence <= 1),
    attributed_by text check (attributed_by in ('model', 'human')),
    attribution_note text,
    human_override jsonb,
    status text not null default 'open' check (status in ('open', 'attributed', 'corrected', 'closed')),
    updated_at timestamptz not null default now()
);
comment on table bad_cases is 'M4-01/02: Loop cases opened from trace signals; identity, signals and label are immutable; human_override is written by humans (admin role) only.';
create index bad_cases_status_idx on bad_cases (status, opened_at);

create function medops_bad_case_guard() returns trigger language plpgsql as $$
begin
    if tg_op = 'DELETE' then
        raise exception 'bad cases are never deleted' using errcode = 'restrict_violation';
    end if;
    if new.case_id is distinct from old.case_id or new.trace_id is distinct from old.trace_id
       or new.dept is distinct from old.dept or new.opened_at is distinct from old.opened_at
       or new.signals is distinct from old.signals or new.label is distinct from old.label
       or new.reasons is distinct from old.reasons then
        raise exception 'bad case identity, signals and label are immutable' using errcode = 'restrict_violation';
    end if;
    if new.human_override is distinct from old.human_override
       and not pg_has_role(current_user, 'medops_admin_role', 'member') then
        raise exception 'human_override is written by the admin role only' using errcode = 'insufficient_privilege';
    end if;
    new.updated_at = now();
    return new;
end $$;
create trigger bad_cases_guard before update or delete on bad_cases for each row execute function medops_bad_case_guard();

alter table bad_cases enable row level security;
alter table bad_cases force row level security;
create policy bad_cases_loop on bad_cases for all to medops_loop_role using (true) with check (true);
create policy bad_cases_admin on bad_cases for all to medops_admin_role using (true) with check (true);
grant select, insert, update on bad_cases to medops_loop_role;
grant select, update on bad_cases to medops_admin_role;

create policy traces_loop_read on traces for select to medops_loop_role using (true);
create policy escalations_loop_read on escalations for select to medops_loop_role using (true);
create policy feedback_loop_read on feedback for select to medops_loop_role using (true);
create policy replays_loop_read on replays for select to medops_loop_role using (true);
grant select on traces, escalations, feedback, replays to medops_loop_role;

create view trace_signals with (security_invoker = true, security_barrier = true) as
select t.trace_id, t.kind, t.task_id, t.principal, t.dept, t.query, t.outcome, t.reason_codes, t.versions,
       t.evidence_chunk_ids, t.cited_chunk_ids, t.flagged_chunk_ids, t.model_calls, t.tokens, t.cost_usd,
       t.duration_ms, t.created_at,
       coalesce(f.up, 0)::int as feedback_up,
       coalesce(f.down, 0)::int as feedback_down,
       coalesce(f.corrections, 0)::int as feedback_corrections,
       f.last_feedback_at,
       e.escalation_id,
       e.status as escalation_status,
       e.reason_codes as escalation_reason_codes,
       e.resolution as escalation_resolution,
       e.handled_at as escalation_handled_at,
       (('unsupported_conclusion' = any (t.reason_codes))
        or coalesce((e.verify_result ->> 'structural_ok')::boolean, true) = false) as verifier_failed,
       (cardinality(t.flagged_chunk_ids) > 0
        or t.reason_codes && array['prompt_injection', 'acl_denied']::text[]) as safety_flagged,
       coalesce(r.n, 0)::int as replay_count,
       coalesce(r.changed_any, false) as replay_changed
  from traces t
  left join lateral (
        select count(*) filter (where signal = 'up') as up,
               count(*) filter (where signal = 'down') as down,
               count(*) filter (where signal = 'correction') as corrections,
               max(created_at) as last_feedback_at
          from feedback where feedback.trace_id = t.trace_id) f on true
  left join lateral (
        select escalation_id, status, reason_codes, resolution, handled_at, verify_result
          from escalations where escalations.trace_id = t.trace_id
         order by created_at desc limit 1) e on true
  left join lateral (
        select count(*) as n, bool_or(cardinality(changed) > 0) as changed_any
          from replays where replays.source_trace_id = t.trace_id) r on true;
comment on view trace_signals is 'M4-01: feedback, verifier, safety, escalation and replay signals joined to their trace; security_invoker so base-table RLS applies to the caller.';
grant select on trace_signals to medops_loop_role, medops_admin_role;
"""

DOWN = r"""
drop view if exists trace_signals;
revoke select on traces, escalations, feedback, replays from medops_loop_role;
drop policy if exists replays_loop_read on replays;
drop policy if exists feedback_loop_read on feedback;
drop policy if exists escalations_loop_read on escalations;
drop policy if exists traces_loop_read on traces;
drop trigger if exists bad_cases_guard on bad_cases;
drop function if exists medops_bad_case_guard();
drop table if exists bad_cases;
alter table escalations drop column if exists resolution;
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
