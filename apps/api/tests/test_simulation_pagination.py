"""Bound SQL pagination and request-scoped validation work without fake engine claims."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from earthmind_api.geospatial_models import NetworkVersion, Scenario
from earthmind_api.settings import Settings
from earthmind_api.simulation_networks import network_catalog
from earthmind_api.simulation_routes import scenarios
from earthmind_api.simulation_service import scenario_response
from earthmind_contracts.simulation import DemandConfig, ScenarioValidation
from sqlalchemy.dialects import postgresql


async def test_network_catalog_applies_database_bounds_before_loading(monkeypatch) -> None:
    region_id = uuid4()
    networks = [
        NetworkVersion(
            id=uuid4(),
            region_id=region_id,
            version_label=f"page-{index}",
            source_format="osm_sumo_georeferenced",
        )
        for index in range(2)
    ]
    session = AsyncMock()
    session.scalar.return_value = 4321

    async def bounded_result(query):
        statement = str(
            query.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        )
        normalized = " ".join(statement.split())
        assert "LIMIT 2" in normalized and "OFFSET 7" in normalized
        return SimpleNamespace(all=lambda: networks)

    session.scalars.side_effect = bounded_result
    session.get.return_value = SimpleNamespace(name="Contract test study region")
    validation = AsyncMock(
        return_value=(
            None,
            ScenarioValidation(valid=False, errors=["Controlled readiness unit case"]),
            None,
        )
    )
    monkeypatch.setattr("earthmind_api.simulation_networks.validate_network_input", validation)
    page = await network_catalog(session, Settings(), 2, 7)
    assert page["total"] == 4321 and page["limit"] == 2 and page["offset"] == 7
    assert len(page["items"]) == 2
    assert validation.await_count == 2
    assert session.scalar.await_count == 1


async def test_scenario_page_reuses_validation_only_inside_one_request(monkeypatch) -> None:
    network_id = uuid4()
    network = NetworkVersion(id=network_id, version_label="contract-version")
    values = [
        Scenario(
            id=uuid4(),
            network_version_id=network_id,
            name=f"Contract scenario {index}",
            config={"demand": DemandConfig().model_dump(mode="json")},
            configuration_checksum="a" * 64,
            created_at=datetime.now(UTC),
        )
        for index in range(2)
    ]
    session = AsyncMock()
    session.scalar.return_value = 2
    session.scalars.return_value = SimpleNamespace(all=lambda: values)
    check = AsyncMock(return_value=(network, ScenarioValidation(valid=True), None))
    monkeypatch.setattr("earthmind_api.simulation_service.validate_network_input", check)
    first = await scenarios(session, Settings(), 2, 0)
    assert len(first["items"]) == 2 and check.await_count == 1
    second = await scenarios(session, Settings(), 2, 0)
    assert len(second["items"]) == 2 and check.await_count == 2
    # Detail/create callers that omit the cache still perform a fresh validation.
    await scenario_response(session, Settings(), values[0])
    await scenario_response(session, Settings(), values[0])
    assert check.await_count == 4
