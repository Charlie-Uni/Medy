"""Shared inference and budget assembly for live evaluation commands.

Constructing a gateway does not call a provider. The caller still owns dataset
preflight, fact planes, released policies, execution limits and the run lifetime.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from medops.core.config import Settings
from medops.infrastructure.llm.budget import BudgetedGateway
from medops.infrastructure.llm.factory import build_budgeted_gateway
from medops.infrastructure.llm.meter import MeteredGateway
from medops.retrieval.inference_process import InferenceProcess, ProcessEmbedding, ProcessReranker


@dataclass
class EvaluationRuntime:
    gpu: InferenceProcess
    provider: ProcessEmbedding
    budgeted_gateway: BudgetedGateway
    gateway: MeteredGateway
    _rerankers: dict[int, ProcessReranker] = field(default_factory=dict)

    def reranker(self, output: int) -> ProcessReranker:
        if output not in self._rerankers:
            self._rerankers[output] = ProcessReranker(self.gpu, output=output)
        return self._rerankers[output]


def bootstrap_execution(
    settings: Settings,
    *,
    device: str,
    rerank_output: int,
    gpu_timeout_s: float,
    run_cap_usd: float | None,
) -> EvaluationRuntime:
    gpu = InferenceProcess(device=device, output=rerank_output, timeout_s=gpu_timeout_s)
    try:
        provider = ProcessEmbedding(gpu)
        budgeted = build_budgeted_gateway(settings, run_cap_usd=run_cap_usd, require_execution_budget=True)
        return EvaluationRuntime(gpu, provider, budgeted, MeteredGateway(budgeted))
    except BaseException:
        gpu.close(graceful=False)
        raise
