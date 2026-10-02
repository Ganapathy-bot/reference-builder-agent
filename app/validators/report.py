"""Shared validation issue types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Issue:
    code: str
    message: str
    style: str | None = None
    severity: str = "error"

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "style": self.style,
            "severity": self.severity,
        }


@dataclass
class ValidationReport:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    attempts: int = 1
    corrections: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors

    def status(self) -> str:
        if self.errors:
            return "failed"
        if self.warnings:
            return "warning"
        return "passed"

    def as_dict(self) -> dict:
        return {
            "status": self.status(),
            "errors": [issue.as_dict() for issue in self.errors],
            "warnings": [issue.as_dict() for issue in self.warnings],
            "attempts": self.attempts,
            "corrections": self.corrections,
        }
