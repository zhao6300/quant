from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ProblemV1:
    kind: str
    title: str
    status: int
    detail: str | None = None
    operation_id: str | None = None
    fields: Mapping[str, list[str]] | None = None
    retry: str = "never"

    def to_dict(self) -> dict[str, Any]:
        response: dict[str, Any] = {
            "kind": self.kind,
            "title": self.title,
            "status": self.status,
            "retry": self.retry,
        }
        if self.detail is not None:
            response["detail"] = self.detail
        if self.operation_id is not None:
            response["operation_id"] = self.operation_id
        if self.fields is not None:
            response["fields"] = {key: list(values) for key, values in self.fields.items()}
        return response


class DomainError(Exception):
    def __init__(self, problem: ProblemV1):
        super().__init__(problem.detail or problem.title)
        self.problem = problem
