import asyncio
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.core.adapters import (
    AdapterContractError,
    AdapterError,
    AdapterRegistry,
    AdapterRegistrationError,
    AgentAdapter,
    normalize_adapter_error,
)
from app.schemas.adapters import (
    AdapterCapabilities,
    AdapterConfig,
    AdapterErrorCode,
    AdapterEvent,
    AdapterMetadata,
    AdapterRuntimeContext,
    AgentExecutionResult,
    AgentTask,
    EventProvenance,
    ExecutionStatus,
)


class FakeAdapter:
    def __init__(self):
        self.connected = False
        self.stopped = False
        self.disconnected = False
        self.capabilities = AdapterCapabilities(
            event_collection=True,
            cooperative_stop=True,
            structured_tool_calls=True,
            screenshots=False,
            max_concurrent_runs=2,
        )

    async def connect(self, config: AdapterConfig, context: AdapterRuntimeContext) -> None:
        assert config.adapter_type == "fake"
        assert context.run_id
        self.connected = True

    async def execute(self, task: AgentTask, context: AdapterRuntimeContext) -> AgentExecutionResult:
        assert self.connected is True
        return AgentExecutionResult(
            status=ExecutionStatus.COMPLETED,
            output={"task_id": task.task_id, "scenario_id": task.scenario_id},
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )

    async def collect_events(self) -> list[AdapterEvent]:
        return [AdapterEvent(
            event_id="evt-1",
            event_type="action.completed",
            occurred_at=datetime.now(timezone.utc),
            provenance=EventProvenance.ADAPTER_REPORTED,
            actor="fake-agent",
            action="lookup",
            status="completed",
        )]

    async def stop(self) -> None:
        self.stopped = True

    async def disconnect(self) -> None:
        self.disconnected = True


def _metadata(adapter_type: str = "fake") -> AdapterMetadata:
    return AdapterMetadata(
        adapter_type=adapter_type,
        display_name=f"{adapter_type.title()} adapter",
        version="0.1.0",
        description="Test-only adapter used for protocol contract verification",
        capabilities=AdapterCapabilities(event_collection=True, cooperative_stop=True),
    )


def test_fake_adapter_satisfies_async_lifecycle_protocol_and_registry():
    registry = AdapterRegistry()
    registry.register(_metadata(), FakeAdapter)
    adapter = registry.create(AdapterConfig(adapter_type="fake"))
    assert isinstance(adapter, AgentAdapter)
    assert registry.contains("fake")
    assert registry.get_metadata("fake").version == "0.1.0"
    assert [item.adapter_type for item in registry.list_metadata()] == ["fake"]

    async def exercise_lifecycle():
        context = AdapterRuntimeContext(run_id="run-1", environment_id="servicedesk_v1")
        await adapter.connect(AdapterConfig(adapter_type="fake"), context)
        result = await adapter.execute(AgentTask(task_id="task-1", scenario_id="SD-001", instruction="Find INC1001"), context)
        events = await adapter.collect_events()
        await adapter.stop()
        await adapter.disconnect()
        return result, events

    result, events = asyncio.run(exercise_lifecycle())
    assert result.status == ExecutionStatus.COMPLETED
    assert result.output["task_id"] == "task-1"
    assert events[0].provenance == EventProvenance.ADAPTER_REPORTED
    assert adapter.stopped is True
    assert adapter.disconnected is True


def test_registry_rejects_duplicate_unknown_and_invalid_adapters():
    registry = AdapterRegistry()
    metadata = _metadata()
    registry.register(metadata, FakeAdapter)
    with pytest.raises(AdapterRegistrationError):
        registry.register(metadata, FakeAdapter)
    with pytest.raises(AdapterRegistrationError):
        registry.create(AdapterConfig(adapter_type="missing"))

    invalid_registry = AdapterRegistry()
    invalid_registry.register(metadata, lambda: object())
    with pytest.raises(AdapterContractError):
        invalid_registry.create(AdapterConfig(adapter_type="fake"))


def test_adapter_configuration_rejects_invalid_values_and_raw_secret_fields():
    with pytest.raises(ValidationError):
        AdapterConfig(adapter_type="fake", timeout_seconds=0)
    with pytest.raises(ValidationError):
        AdapterConfig(adapter_type="fake", api_key="raw-secret")
    with pytest.raises(ValidationError):
        AdapterConfig(adapter_type="fake", settings={"nested": {"api_key": "raw-secret"}})
    with pytest.raises(ValidationError):
        AdapterConfig(adapter_type="fake", secret_refs={"api_key": "plain-token"})
    config = AdapterConfig(adapter_type="fake", secret_refs={"api_key": "vault://project/adapter-token"})
    assert config.secret_refs["api_key"].startswith("vault://")


def test_error_normalization_covers_timeout_cancel_connection_and_protocol_failures():
    timeout = normalize_adapter_error(TimeoutError("provider detail should not leak"))
    assert timeout.code == AdapterErrorCode.TIMEOUT
    assert timeout.retryable is True
    assert "provider detail" not in timeout.message

    cancelled = normalize_adapter_error(asyncio.CancelledError())
    assert cancelled.code == AdapterErrorCode.CANCELLED
    assert cancelled.retryable is False

    connection = normalize_adapter_error(ConnectionError("private endpoint"))
    assert connection.code == AdapterErrorCode.CONNECTION_FAILED
    assert connection.retryable is True
    assert "private endpoint" not in connection.message

    unsupported = normalize_adapter_error(NotImplementedError())
    assert unsupported.code == AdapterErrorCode.UNSUPPORTED_CAPABILITY

    custom = normalize_adapter_error(AdapterError(AdapterErrorCode.PROTOCOL_ERROR, "Invalid adapter response"))
    assert custom.code == AdapterErrorCode.PROTOCOL_ERROR
    unknown = normalize_adapter_error(RuntimeError("secret-bearing runtime message"))
    assert unknown.code == AdapterErrorCode.UNKNOWN
    assert "secret-bearing" not in unknown.message


def test_provenance_is_explicit_and_not_collapsed():
    assert {item.value for item in EventProvenance} == {
        "directly_observed", "adapter_reported", "agent_reported", "inferred"
    }
    event = AdapterEvent(
        event_id="evt-2",
        event_type="agent.claim",
        occurred_at=datetime.now(timezone.utc),
        provenance=EventProvenance.AGENT_REPORTED,
    )
    assert event.provenance == EventProvenance.AGENT_REPORTED
