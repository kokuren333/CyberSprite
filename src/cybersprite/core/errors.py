"""Actionable errors shared by all surfaces."""

from typing import Any


class CyberSpriteError(Exception):
    def __init__(
        self, code: str, message: str, hint: str, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.details = details or {}

    def as_dict(self) -> dict[str, Any]:
        return dict(code=self.code, message=self.message, details=self.details, hint=self.hint)

    @property
    def exit_code(self) -> int:
        if self.code == "E_VALIDATION_FAILED":
            return 1
        if self.code in {"E_INVALID_ARGS", "E_UNKNOWN_OP"}:
            return 2
        if self.code in {"E_IO", "E_LOCKED", "E_PATH_NOT_ALLOWED", "E_INVALID_PROJECT"}:
            return 4
        if self.code in {"E_INTERNAL", "E_INVARIANT"}:
            return 5
        if self.code in {
            "E_LIMIT_EXCEEDED",
            "E_UNSUPPORTED",
            "E_NEEDS_QUANTIZE",
            "E_NOT_PALETTE_CLOSED",
            "E_SCHEMA_TOO_NEW",
        }:
            return 6
        return 3


def invalid(message: str, **details: Any) -> CyberSpriteError:
    return CyberSpriteError(
        "E_INVALID_ARGS", message, "Correct the indicated argument and retry.", details
    )
