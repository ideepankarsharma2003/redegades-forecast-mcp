from __future__ import annotations

from datetime import date, datetime
from typing import Any

from mcp_service.query_registry import QueryDefinition

DANGEROUS_SQL_TOKENS = (
    ";",
    "--",
    "/*",
    "*/",
    " xp_",
    " drop ",
    " alter ",
    " truncate ",
    " delete ",
    " update ",
    " insert ",
    " merge ",
    " grant ",
    " revoke ",
    " execute ",
    " exec ",
)


def validate_and_normalize_params(
    definition: QueryDefinition,
    raw_params: dict[str, Any] | None,
) -> dict[str, Any]:
    params = raw_params or {}
    allowed = set(definition.allowed_params)
    unknown = sorted(set(params) - allowed)
    if unknown:
        raise ValueError(f"Unexpected query params: {', '.join(unknown)}")

    normalized: dict[str, Any] = dict(definition.defaults)
    normalized.update(params)

    missing = [
        param
        for param in definition.required_params
        if normalized.get(param) in (None, "")
    ]
    if missing:
        raise ValueError(f"Missing required params: {', '.join(missing)}")

    for key, value in normalized.items():
        normalized[key] = _normalize_value(key, value)

    return normalized


def _normalize_value(key: str, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float, bool, date, datetime)):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        upper_scan = f" {stripped.upper()} "
        for token in DANGEROUS_SQL_TOKENS:
            if token.upper() in upper_scan:
                raise ValueError(f"Unsafe value blocked for '{key}'")
        return stripped
    raise ValueError(f"Unsupported value type for '{key}': {type(value).__name__}")
