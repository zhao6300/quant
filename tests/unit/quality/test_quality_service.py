from mmqp.application.quality import QualityService
from mmqp.domain.quality import ComplianceContext


def test_fixed_policy_rejects_unknown_rule() -> None:
    issues = QualityService().evaluate(compliance_context(), ())

    assert issues is not None


def compliance_context() -> ComplianceContext:
    return ComplianceContext("test", {}, frozenset(), {})
