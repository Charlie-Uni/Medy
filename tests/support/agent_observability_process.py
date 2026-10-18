"""PUBLIC independent-process recovery observer. Credentials stay in the environment."""

import json
import os
import sys

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from medops.core import telemetry
from medops.domain.agent_execution import PVAgentRun
from medops.infrastructure.db.agent_facts import FactDatabaseBinding
from medops.infrastructure.llm.fake import FakeModelGateway
from tests.support.agent_runtime import reopen_case


def main():
    data = json.load(sys.stdin)
    run = PVAgentRun.model_validate(data["run"])
    binding = FactDatabaseBinding.model_validate(data["binding"])
    fake = FakeModelGateway({})
    case = reopen_case({"users": {"app": os.environ["MEDOPS_TEST_AGENT_APP_URL"]}}, run, binding, data["chunk"], fake)
    exporter = InMemorySpanExporter()
    provider = telemetry.install_exporter(exporter, batch=False)
    try:
        with case["runtime"].recover(run.context) as recovered:
            result = recovered.run()
        (root,) = [s for s in exporter.get_finished_spans() if s.name == "agent.execution"]
        print(
            json.dumps(
                dict(
                    trace_id=format(root.context.trace_id, "032x"),
                    span_id=format(root.context.span_id, "016x"),
                    attributes=dict(root.attributes),
                    calls=len(fake.calls),
                    started_at=result.run.started_at.isoformat(),
                )
            )
        )
    finally:
        telemetry.set_tracer_provider(None)
        provider.shutdown()


if __name__ == "__main__":
    main()
