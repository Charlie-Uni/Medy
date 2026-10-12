"""Shared paid task test support; no collected test cases."""

from dataclasses import replace

from medops.infrastructure.llm.meter import MeteredGateway
from tests.support.tasks import FakeEnv


class PaidFakeEnv(FakeEnv):
    def __init__(self, store, reg, principals, gateway):
        super().__init__(store, reg, principals)
        self.gateway = gateway
        self.meters = {}

    def skill_context(self, conn, user, trace_id, historical):
        ctx = super().skill_context(conn, user, trace_id, historical)
        meter = MeteredGateway(self.gateway)
        self.meters[trace_id] = meter
        return replace(ctx, deps=replace(ctx.deps, gateway=meter))
