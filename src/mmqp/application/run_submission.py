from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from mmqp.domain.errors import DomainError, ProblemV1

type VersionValue = str


@dataclass(frozen=True, slots=True)
class ResearchRunRequest:
    snapshot_id: str
    start_date: date
    end_date: date
    base_currency: str
    factor_definition_version: str
    universe_version: str
    portfolio_definition_version: str
    strategy_version: str
    transaction_cost_model_version: str
    risk_model_version: str


@dataclass(frozen=True, slots=True)
class RunSubmissionReceipt:
    snapshot_id: str
    request: Mapping[str, Any]
    result_kind: str
    disclaimer: str
    run_created: bool = False


@dataclass(frozen=True, slots=True)
class ResearchRunRef:
    run_id: str
    manifest_id: str


class ExperimentRunner(Protocol):
    def submit(self, request: ResearchRunRequest) -> ResearchRunRef: ...


class NotImplementedRunError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            ProblemV1(
                kind="interface/runner-unavailable",
                title="Experiment runner is unavailable",
                status=501,
                detail="Experiment runner is not attached to this research interface",
            )
        )


class RunSubmissionValidationError(DomainError):
    def __init__(self, fields: list[str], error_codes: list[str] | None = None):
        super().__init__(
            ProblemV1(
                kind="interface/run-request-invalid",
                title="Research run request is invalid",
                status=422,
                detail=", ".join(error_codes or fields),
                fields={field: [] for field in sorted(set(fields))} if fields else None,
            )
        )
        self.fields = list(dict.fromkeys(fields))
        self.error_codes = sorted(set(error_codes or fields))


class RunSubmissionService:
    def __init__(
        self,
        available_snapshots: Sequence[str],
        experiment_runner: ExperimentRunner | None = None,
    ) -> None:
        self._available_snapshots = frozenset(available_snapshots)
        self._experiment_runner = experiment_runner

    def submit(self, request: ResearchRunRequest) -> RunSubmissionReceipt:
        fields, error_codes = self._validation_errors(request)
        if fields or error_codes:
            raise RunSubmissionValidationError(fields, error_codes)
        if self._experiment_runner is None:
            return self._receipt(request, {}, False)
        run_ref = self._experiment_runner.submit(request)
        return self._receipt(request, {"run_id": run_ref.run_id, "manifest_id": run_ref.manifest_id}, True)

    def _validation_errors(self, request: ResearchRunRequest) -> tuple[list[str], list[str]]:
        fields: list[str] = []
        error_codes: list[str] = []
        identifier_fields = (
            "snapshot_id",
            "factor_definition_version",
            "universe_version",
            "portfolio_definition_version",
            "strategy_version",
            "transaction_cost_model_version",
            "risk_model_version",
        )
        for field_name in identifier_fields:
            value = getattr(request, field_name)
            if not isinstance(value, str) or not value.strip():
                fields.append(field_name)
                error_codes.append("version.missing")
        if request.snapshot_id and request.snapshot_id not in self._available_snapshots:
            fields.append("snapshot_id")
            error_codes.append("snapshot.unavailable")
        if request.start_date > request.end_date:
            fields.append("date_range.invalid")
            error_codes.append("date_range.invalid")
        if (
            not isinstance(request.base_currency, str)
            or len(request.base_currency) != 3
            or not request.base_currency.isalpha()
        ):
            fields.append("base_currency")
            error_codes.append("base_currency.invalid")
        return fields, error_codes

    @staticmethod
    def _receipt(
        request: ResearchRunRequest,
        outcome: Mapping[str, Any],
        run_created: bool,
    ) -> RunSubmissionReceipt:
        identifier_fields = (
            "factor_definition_version",
            "universe_version",
            "portfolio_definition_version",
            "strategy_version",
            "transaction_cost_model_version",
            "risk_model_version",
        )
        return RunSubmissionReceipt(
            snapshot_id=request.snapshot_id,
            request={
                "start_date": request.start_date,
                "end_date": request.end_date,
                "base_currency": request.base_currency,
                **{field: getattr(request, field) for field in identifier_fields},
                **outcome,
            },
            result_kind="research_simulation",
            disclaimer="Simulation only; not investment advice; no brokerage order sent.",
            run_created=run_created,
        )
