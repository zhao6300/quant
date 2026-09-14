from __future__ import annotations

from builtins import list as list_type
from typing import Protocol

from mmqp.domain.factors import FactorDefinition, FactorEvaluationRequest, FactorEvaluationResult, FactorValue


class FactorResearchRepository(Protocol):
    def create(self, definition: FactorDefinition) -> FactorDefinition: ...
    def list(self) -> list_type[FactorDefinition]: ...
    def find(self, definition_id: str) -> FactorDefinition | None: ...
    def create_result(
        self,
        request: FactorEvaluationRequest,
        result: FactorEvaluationResult,
    ) -> list_type[FactorValue]: ...
    def list_results(self, definition_id: str) -> list_type[FactorValue]: ...
