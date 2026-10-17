"""Subprocess-only PUBLIC crash harness. Credentials are environment-only."""

import json
import os
import sys

from medops.bootstrap.agent_driver import PgAgentDriver
from medops.domain.agent_execution import PVAgentRun
from medops.infrastructure.db.agent_facts import FactDatabaseBinding
from medops.infrastructure.llm.fake import FakeModelGateway
from tests.support.agent_runtime import reopen_case
from tests.support.pv_agent import proposal
from tests.support.pv_loop import terminal


def main():
    data = json.load(sys.stdin)
    run = PVAgentRun.model_validate(data["run"])
    binding = FactDatabaseBinding.model_validate(data["binding"])
    fake = FakeModelGateway({"agent_plan": [proposal(), terminal()]})
    case = reopen_case(
        {"users": {"app": os.environ["MEDOPS_TEST_AGENT_APP_URL"]}}, run, binding, data["chunk"], fake, lease_s=3
    )
    mode = data["mode"]
    checkpoint = PgAgentDriver.checkpoint
    settled = PgAgentDriver.settled
    complete = fake.complete

    def save(self, event):
        if mode == "tool_commit" and event.phase == "tool_committed":
            os._exit(83)
        checkpoint(self, event)
        if mode == "decision" and event.phase == "decision_started":
            os._exit(83)

    def receipt(self, *args):
        settled(self, *args)
        if mode == "planning_receipt" and args[0].purpose == "agent_plan":
            os._exit(83)

    def provider(request):
        if mode == "inflight":
            os._exit(83)
        return complete(request)

    PgAgentDriver.checkpoint = save
    PgAgentDriver.settled = receipt
    fake.complete = provider
    with case["runtime"].start(run) as execution:
        execution.run()
    raise RuntimeError("PUBLIC-crash-point-not-reached")


if __name__ == "__main__":
    main()
