"""Harness (baseline 5.3, M2-01/02): the fixed LangGraph state machine
Intent -> Retrieve -> Verify -> Safety -> Answer | Escalate, with typed node contracts, timeouts, bounded
retries and degradation rules. Domain rules live in `medops.verification` / `medops.safety`; the graph only
moves `AgentState` forward and can be inspected for bypass edges."""
