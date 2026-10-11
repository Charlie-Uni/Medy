"""Final Skill judgment checks; user observations are premises, never document evidence."""

from medops.domain.common import DomainModel, NonEmptyStr, Sha256
from medops.domain.verification import Verdict


class JudgmentCheck(DomainModel):
    key: NonEmptyStr
    clause_indices: tuple[int, ...]
    conclusion: Verdict
    rationale: Verdict
    clause_relevance: Verdict
    observation_grounding: Verdict
    rule_failures: tuple[str, ...] = ()

    @property
    def supported(self) -> bool:
        return not self.rule_failures and all(
            value is Verdict.supported
            for value in (self.conclusion, self.rationale, self.clause_relevance, self.observation_grounding)
        )


class JudgmentVerification(DomainModel):
    verifier_version: NonEmptyStr
    input_sha256: Sha256
    judge_model_id: str | None
    checks: tuple[JudgmentCheck, ...]

    @property
    def supported(self) -> bool:
        return bool(self.checks) and all(check.supported for check in self.checks)

    @property
    def contradicted(self) -> bool:
        return any(
            value is Verdict.contradicted
            for check in self.checks
            for value in (check.conclusion, check.rationale, check.clause_relevance, check.observation_grounding)
        )
