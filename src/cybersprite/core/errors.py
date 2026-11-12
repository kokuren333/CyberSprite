"""Actionable errors shared by all surfaces."""

from typing import Any

# SPEC §9.2 and Appendix C. Keep every public code explicit; unknown bugs exit 5.
EXIT_CODES = {
    "E_VALIDATION_FAILED": 1,
    "E_INVALID_ARGS": 2,
    "E_UNKNOWN_OP": 2,
    "E_PROJECT_NOT_FOUND": 3,
    "E_EXISTS": 3,
    "E_LAYER_NOT_FOUND": 3,
    "E_CEL_NOT_FOUND": 3,
    "E_TAG_NOT_FOUND": 3,
    "E_SLICE_NOT_FOUND": 3,
    "E_TILESET_NOT_FOUND": 3,
    "E_SOURCE_NOT_FOUND": 3,
    "E_FRAME_OUT_OF_RANGE": 3,
    "E_AMBIGUOUS_REF": 3,
    "E_WRONG_LAYER_TYPE": 3,
    "E_LAYER_LOCKED": 3,
    "E_PALETTE_FROZEN": 3,
    "E_INDEX_OUT_OF_RANGE": 3,
    "E_COLOR_NOT_IN_PALETTE": 3,
    "E_OUT_OF_CANVAS": 3,
    "E_REVISION_CONFLICT": 3,
    "E_NOTHING_TO_UNDO": 3,
    "E_NOTHING_TO_REDO": 3,
    "E_HISTORY_UNAVAILABLE": 3,
    "E_PLUGIN": 3,
    "E_BACKEND_UNAVAILABLE": 3,
    "E_LICENSE_NOT_ACCEPTED": 3,
    "E_GENERATION_FAILED": 3,
    "E_TIMEOUT": 4,
    "E_IO": 4,
    "E_LOCKED": 4,
    "E_PATH_NOT_ALLOWED": 4,
    "E_INVALID_PROJECT": 4,
    "E_INTERNAL": 5,
    "E_INVARIANT": 5,
    "E_LIMIT_EXCEEDED": 6,
    "E_UNSUPPORTED": 6,
    "E_NEEDS_QUANTIZE": 6,
    "E_NOT_PALETTE_CLOSED": 6,
    "E_SCHEMA_TOO_NEW": 6,
}


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
        return EXIT_CODES.get(self.code, 5)


def invalid(message: str, **details: Any) -> CyberSpriteError:
    return CyberSpriteError(
        "E_INVALID_ARGS", message, "Correct the indicated argument and retry.", details
    )
