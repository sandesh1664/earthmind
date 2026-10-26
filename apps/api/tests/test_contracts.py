"""Make wire-schema changes visible to TypeScript and other consumers."""

import json
from pathlib import Path

import pytest
from earthmind_contracts import (
    ApiHealth,
    DiagnosticJob,
    DiagnosticRequest,
    LiveHealth,
    ReadyHealth,
    SumoRuntimeRecord,
    SystemCapabilities,
)
from pydantic import BaseModel


@pytest.mark.parametrize(
    "model",
    [
        LiveHealth,
        ReadyHealth,
        ApiHealth,
        DiagnosticRequest,
        DiagnosticJob,
        SumoRuntimeRecord,
        SystemCapabilities,
    ],
)
def test_committed_schema_matches_python_contract(model: type[BaseModel]) -> None:
    root = Path(__file__).resolve().parents[3]
    schema = json.loads(
        (root / "packages" / "contracts" / "schema" / f"{model.__name__}.json").read_text()
    )
    assert schema == model.model_json_schema()
