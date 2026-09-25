"""M5-06 (record 87): a controlled retention purge path for the audit tables and a rewrap-only update path for
encrypted payloads (key rotation).

- Append-only stays the default. A DELETE on traces / trace_spans / feedback / replays / bad_cases, or on a *closed*
  escalation, is accepted only inside a transaction that set `medops.retention_purge = on` and only for rows older
  than `medops.retention_days` (never fewer than 90 days). Only the admin role holds DELETE; the retention CLI sets
  the two GUCs per transaction, so no other code path can delete audit rows by accident.
- `trace_payloads` rows may be UPDATEd only by a KEK rewrap: `dek_wrapped` and `kek_version` change, everything else
  (ciphertext, nonce, identity, timestamps) must be identical. The restricted role gets a column-level UPDATE grant
  for exactly those two columns. `payload_access_log` and `document_requests` stay permanent.

Revision ID: 0019
Revises: 0018
"""

from __future__ import annotations

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

_ESCALATION_IMMUTABLE = """new.escalation_id is distinct from old.escalation_id or new.trace_id is distinct from old.trace_id
       or new.principal is distinct from old.principal or new.dept is distinct from old.dept
       or new.reason_codes is distinct from old.reason_codes or new.query is distinct from old.query
       or new.evidence_chunk_ids is distinct from old.evidence_chunk_ids or new.verify_result is distinct from old.verify_result
       or new.safety_result is distinct from old.safety_result or new.policy_version is distinct from old.policy_version
       or new.detail is distinct from old.detail or new.created_at is distinct from old.created_at"""

_BAD_CASE_IMMUTABLE = """new.case_id is distinct from old.case_id or new.trace_id is distinct from old.trace_id
       or new.dept is distinct from old.dept or new.opened_at is distinct from old.opened_at
       or new.signals is distinct from old.signals or new.label is distinct from old.label
       or new.reasons is distinct from old.reasons"""

UP = rf"""
create function medops_retention_purge_allowed(stamp timestamptz) returns boolean language plpgsql stable as $$
declare
    days integer;
begin
    if coalesce(current_setting('medops.retention_purge', true), '') <> 'on' then
        return false;
    end if;
    days := greatest(coalesce(nullif(current_setting('medops.retention_days', true), '')::integer, 365), 90);
    return stamp < now() - make_interval(days => days);
end $$;
comment on function medops_retention_purge_allowed(timestamptz) is 'M5-06: true only inside a retention purge transaction (medops.retention_purge=on) for rows older than medops.retention_days (floor 90).';

create function medops_append_only_with_retention() returns trigger language plpgsql as $$
begin
    if tg_op = 'DELETE' and medops_retention_purge_allowed(old.created_at) then
        return old;
    end if;
    raise exception 'append-only table' using errcode = 'restrict_violation';
end $$;

create function medops_spans_append_only_with_retention() returns trigger language plpgsql as $$
begin
    if tg_op = 'DELETE' and medops_retention_purge_allowed(old.started_at) then
        return old;
    end if;
    raise exception 'append-only table' using errcode = 'restrict_violation';
end $$;

drop trigger traces_guard on traces;
create trigger traces_guard before update or delete on traces for each row execute function medops_append_only_with_retention();
drop trigger trace_spans_guard on trace_spans;
create trigger trace_spans_guard before update or delete on trace_spans for each row execute function medops_spans_append_only_with_retention();
drop trigger feedback_guard on feedback;
create trigger feedback_guard before update or delete on feedback for each row execute function medops_append_only_with_retention();
drop trigger replays_guard on replays;
create trigger replays_guard before update or delete on replays for each row execute function medops_append_only_with_retention();

create or replace function medops_escalation_status_guard() returns trigger language plpgsql as $$
begin
    if tg_op = 'DELETE' then
        if old.status = 'closed' and medops_retention_purge_allowed(old.created_at) then
            return old;
        end if;
        raise exception 'escalations are never deleted' using errcode = 'restrict_violation';
    end if;
    if {_ESCALATION_IMMUTABLE} then
        raise exception 'escalation content is immutable; only status/handled_* may change' using errcode = 'restrict_violation';
    end if;
    if old.status = 'closed' and new.status <> 'closed' then
        raise exception 'a closed escalation stays closed' using errcode = 'restrict_violation';
    end if;
    return new;
end $$;

create or replace function medops_bad_case_guard() returns trigger language plpgsql as $$
begin
    if tg_op = 'DELETE' then
        if medops_retention_purge_allowed(old.opened_at) then
            return old;
        end if;
        raise exception 'bad cases are never deleted' using errcode = 'restrict_violation';
    end if;
    if {_BAD_CASE_IMMUTABLE} then
        raise exception 'bad case identity, signals and label are immutable' using errcode = 'restrict_violation';
    end if;
    if new.human_override is distinct from old.human_override
       and not pg_has_role(current_user, 'medops_admin_role', 'member') then
        raise exception 'human_override is written by the admin role only' using errcode = 'insufficient_privilege';
    end if;
    new.updated_at = now();
    return new;
end $$;

create function medops_payload_rewrap_guard() returns trigger language plpgsql as $$
begin
    if new.payload_id = old.payload_id and new.trace_id = old.trace_id and new.node = old.node and new.kind = old.kind
       and new.ciphertext = old.ciphertext and new.nonce = old.nonce and new.created_at = old.created_at
       and new.expires_at is not distinct from old.expires_at and new.kek_version is not null then
        return new;
    end if;
    raise exception 'payload rows change only by a KEK rewrap (dek_wrapped, kek_version)' using errcode = 'restrict_violation';
end $$;
drop trigger trace_payloads_guard on trace_payloads;
create trigger trace_payloads_guard before update on trace_payloads for each row execute function medops_payload_rewrap_guard();

create policy traces_admin_delete on traces for delete to medops_admin_role using (true);
create policy trace_spans_admin_delete on trace_spans for delete to medops_admin_role using (true);
create policy feedback_admin_delete on feedback for delete to medops_admin_role using (true);
create policy replays_admin_delete on replays for delete to medops_admin_role using (true);
create policy trace_payloads_admin_delete on trace_payloads for delete to medops_admin_role using (true);
grant delete on traces, trace_spans, feedback, replays, escalations, bad_cases, trace_payloads to medops_admin_role;
-- the purge's WHERE clause needs the key columns; the admin role still cannot read ciphertext, nonce or wrapped keys
grant select (payload_id, trace_id, node, kind, kek_version, created_at, expires_at) on trace_payloads to medops_admin_role;
grant update (dek_wrapped, kek_version) on trace_payloads to medops_restricted_role;
"""

DOWN = rf"""
revoke update (dek_wrapped, kek_version) on trace_payloads from medops_restricted_role;
revoke select (payload_id, trace_id, node, kind, kek_version, created_at, expires_at) on trace_payloads from medops_admin_role;
revoke delete on traces, trace_spans, feedback, replays, escalations, bad_cases, trace_payloads from medops_admin_role;
drop policy if exists trace_payloads_admin_delete on trace_payloads;
drop policy if exists replays_admin_delete on replays;
drop policy if exists feedback_admin_delete on feedback;
drop policy if exists trace_spans_admin_delete on trace_spans;
drop policy if exists traces_admin_delete on traces;
drop trigger trace_payloads_guard on trace_payloads;
create trigger trace_payloads_guard before update on trace_payloads for each row execute function medops_append_only();
drop function medops_payload_rewrap_guard();

create or replace function medops_bad_case_guard() returns trigger language plpgsql as $$
begin
    if tg_op = 'DELETE' then
        raise exception 'bad cases are never deleted' using errcode = 'restrict_violation';
    end if;
    if {_BAD_CASE_IMMUTABLE} then
        raise exception 'bad case identity, signals and label are immutable' using errcode = 'restrict_violation';
    end if;
    if new.human_override is distinct from old.human_override
       and not pg_has_role(current_user, 'medops_admin_role', 'member') then
        raise exception 'human_override is written by the admin role only' using errcode = 'insufficient_privilege';
    end if;
    new.updated_at = now();
    return new;
end $$;

create or replace function medops_escalation_status_guard() returns trigger language plpgsql as $$
begin
    if tg_op = 'DELETE' then
        raise exception 'escalations are never deleted' using errcode = 'restrict_violation';
    end if;
    if {_ESCALATION_IMMUTABLE} then
        raise exception 'escalation content is immutable; only status/handled_* may change' using errcode = 'restrict_violation';
    end if;
    if old.status = 'closed' and new.status <> 'closed' then
        raise exception 'a closed escalation stays closed' using errcode = 'restrict_violation';
    end if;
    return new;
end $$;

drop trigger replays_guard on replays;
create trigger replays_guard before update or delete on replays for each row execute function medops_append_only();
drop trigger feedback_guard on feedback;
create trigger feedback_guard before update or delete on feedback for each row execute function medops_append_only();
drop trigger trace_spans_guard on trace_spans;
create trigger trace_spans_guard before update or delete on trace_spans for each row execute function medops_append_only();
drop trigger traces_guard on traces;
create trigger traces_guard before update or delete on traces for each row execute function medops_append_only();
drop function medops_spans_append_only_with_retention();
drop function medops_append_only_with_retention();
drop function medops_retention_purge_allowed(timestamptz);
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
