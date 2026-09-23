"""Audit tables (M3-07 first slice; baseline 4.2 `traces/trace_spans`, `escalations`, `feedback`, INV-OBS-01/02/03).

`traces` summarises every request (ask or task execution): principal pseudonym, department, outcome, reason
codes, the version set, tokens, cost and duration; `trace_spans` holds each node attempt (operation key,
outcome, duration); `escalations` keeps the minimum context a human needs to take over (question, evidence
chunk ids, verifier and safety results, policy version); `feedback` links user signals to a trace. Evidence
text is never stored here (INV-OBS-03: the restricted replayable payload is a separate, encrypted store, later).
All four are append-only for the application role; the admin role reads; the read-only role has no access.
An escalation may change status (open -> acknowledged -> closed) only through the admin role.

Revision ID: 0011
Revises: 0010
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

UP = """
create table traces (
    trace_id       text primary key check (trace_id ~ '^[0-9a-f]{32}$'),
    run_id         text not null check (run_id ~ '^[0-9a-f]{32}$'),
    kind           text not null check (kind in ('ask', 'task')),
    task_id        uuid,
    principal      text not null check (principal ~ '^[0-9a-f]{32,64}$'),
    dept           dept not null,
    query          text not null,
    outcome        text not null check (outcome in ('answered', 'refused', 'escalated', 'completed', 'insufficient_evidence', 'failed')),
    reason_codes   text[] not null default '{}',
    versions       jsonb not null,
    evidence_chunk_ids text[] not null default '{}',
    cited_chunk_ids    text[] not null default '{}',
    flagged_chunk_ids  text[] not null default '{}',
    model_calls    integer not null default 0 check (model_calls >= 0),
    tokens         integer not null default 0 check (tokens >= 0),
    cost_usd       numeric(12, 6) not null default 0 check (cost_usd >= 0),
    duration_ms    double precision not null check (duration_ms >= 0),
    created_at     timestamptz not null default now()
);
comment on table traces is 'M3-07 request trace summary (INV-OBS-01); no evidence text (INV-OBS-03).';
create index traces_principal_created on traces (principal, created_at desc);
create index traces_outcome_created on traces (outcome, created_at desc);

create table trace_spans (
    span_id        bigserial primary key,
    trace_id       text not null references traces (trace_id),
    node           text not null,
    attempt        integer not null check (attempt >= 1),
    operation_key  text not null check (operation_key ~ '^[0-9a-f]{64}$'),
    outcome        text not null check (outcome in ('ok', 'retry', 'failed', 'timeout')),
    error_code     text,
    started_at     timestamptz not null,
    duration_ms    double precision not null check (duration_ms >= 0),
    unique (trace_id, node, attempt)
);

create table escalations (
    escalation_id  text primary key check (escalation_id ~ '^[0-9a-f]{32}$'),
    trace_id       text not null unique references traces (trace_id),
    principal      text not null,
    dept           dept not null,
    reason_codes   text[] not null check (cardinality(reason_codes) >= 1),
    query          text not null,
    evidence_chunk_ids text[] not null default '{}',
    verify_result  jsonb,
    safety_result  jsonb,
    policy_version text not null,
    detail         text not null default '',
    status         text not null default 'open' check (status in ('open', 'acknowledged', 'closed')),
    handled_by     text,
    handled_at     timestamptz,
    created_at     timestamptz not null default now()
);
comment on table escalations is 'M2-10/M3-07: minimum context for a human to take over; status changes only via the admin role.';
create index escalations_open on escalations (created_at) where status = 'open';

create table feedback (
    feedback_id    uuid primary key,
    trace_id       text not null references traces (trace_id),
    principal      text not null,
    signal         text not null check (signal in ('up', 'down', 'correction')),
    correction_text text,
    created_at     timestamptz not null default now(),
    constraint feedback_correction_text check ((signal = 'correction') = (correction_text is not null))
);
create index feedback_trace on feedback (trace_id);

create function medops_escalation_status_guard() returns trigger language plpgsql as $$
begin
    if tg_op = 'DELETE' then
        raise exception 'escalations are never deleted' using errcode = 'restrict_violation';
    end if;
    if new.escalation_id is distinct from old.escalation_id or new.trace_id is distinct from old.trace_id
       or new.principal is distinct from old.principal or new.dept is distinct from old.dept
       or new.reason_codes is distinct from old.reason_codes or new.query is distinct from old.query
       or new.evidence_chunk_ids is distinct from old.evidence_chunk_ids or new.verify_result is distinct from old.verify_result
       or new.safety_result is distinct from old.safety_result or new.policy_version is distinct from old.policy_version
       or new.detail is distinct from old.detail or new.created_at is distinct from old.created_at then
        raise exception 'escalation content is immutable; only status/handled_* may change' using errcode = 'restrict_violation';
    end if;
    if old.status = 'closed' and new.status <> 'closed' then
        raise exception 'a closed escalation stays closed' using errcode = 'restrict_violation';
    end if;
    return new;
end $$;
create trigger escalations_guard before update or delete on escalations for each row execute function medops_escalation_status_guard();
create trigger traces_guard before update or delete on traces for each row execute function medops_append_only();
create trigger trace_spans_guard before update or delete on trace_spans for each row execute function medops_append_only();
create trigger feedback_guard before update or delete on feedback for each row execute function medops_append_only();

alter table traces enable row level security;
alter table traces force row level security;
alter table trace_spans enable row level security;
alter table trace_spans force row level security;
alter table escalations enable row level security;
alter table escalations force row level security;
alter table feedback enable row level security;
alter table feedback force row level security;
create policy traces_app on traces for all to medops_app using (true) with check (true);
create policy trace_spans_app on trace_spans for all to medops_app using (true) with check (true);
create policy escalations_app on escalations for all to medops_app using (true) with check (true);
create policy feedback_app on feedback for all to medops_app using (true) with check (true);
create policy traces_admin on traces for select to medops_admin_role using (true);
create policy trace_spans_admin on trace_spans for select to medops_admin_role using (true);
create policy escalations_admin on escalations for all to medops_admin_role using (true) with check (true);
create policy feedback_admin on feedback for select to medops_admin_role using (true);
grant select, insert on traces, trace_spans, escalations, feedback to medops_app;
grant usage, select on sequence trace_spans_span_id_seq to medops_app;
grant select on traces, trace_spans, feedback to medops_admin_role;
grant select, update on escalations to medops_admin_role;
"""

DOWN = """
drop table if exists feedback;
drop table if exists escalations;
drop table if exists trace_spans;
drop table if exists traces;
drop function if exists medops_escalation_status_guard();
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
