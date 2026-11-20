import asyncio

import httpx
import pytest
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from app.core.adapters import AdapterError, AdapterRegistry, HttpApiAdapter
from app.schemas.adapters import (
    AdapterConfig,
    AdapterErrorCode,
    AdapterMetadata,
    AdapterRuntimeContext,
    AgentTask,
    EventProvenance,
    HttpApiAdapterSettings,
)


captured: dict = {}
mock_app = FastAPI()


@mock_app.post("/v1/execute")
async def execute_endpoint(request: Request, authorization: str | None = Header(default=None)):
    captured["authorization"] = authorization
    captured["request"] = await request.json()
    return {
        "status": "completed",
        "output": {"answer": "done", "echo": "test-token"},
        "events": [{
            "event_id": "evt-response",
            "event_type": "tool.call",
            "occurred_at": "2026-11-20T05:00:00Z",
            "provenance": "directly_observed",
            "actor": "mock-agent",
            "action": "get_incident",
            "status": "completed",
            "payload": {"token": "test-token"},
        }],
        "metadata": {"endpoint": "mock", "echo": "test-token"},
    }


@mock_app.get("/v1/events")
async def events_endpoint(run_id: str):
    captured["events_run_id"] = run_id
    return {
        "events": [{
            "event_id": "evt-events",
            "event_type": "tool.result",
            "occurred_at": "2026-11-20T05:00:01Z",
            "provenance": "agent_reported",
            "actor": "mock-agent",
            "action": "get_incident",
            "status": "completed",
            "payload": {"token": "test-token"},
        }]
    }


@mock_app.post("/v1/stop")
async def stop_endpoint(request: Request):
    captured["stop"] = await request.json()
    return {"accepted": True}


def _config(**settings_overrides) -> AdapterConfig:
    settings = {
        "base_url": "http://127.0.0.1",
        "execute_path": "/v1/execute",
        "events_path": "/v1/events",
        "stop_path": "/v1/stop",
        "auth_ref_key": "http_auth",
    }
    settings.update(settings_overrides)
    return AdapterConfig(
        adapter_type="http_api",
        timeout_seconds=8,
        max_actions=12,
        settings=settings,
        secret_refs={"http_auth": "vault://agent-reliability-lab/mock-http-token"},
    )


def _factory(app: FastAPI):
    def create_client(**kwargs):
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), **kwargs)
    return create_client


def test_http_api_adapter_executes_collects_events_and_stops_with_truthful_provenance():
    captured.clear()
    registry = AdapterRegistry()
    registry.register(
        AdapterMetadata(adapter_type="http_api", display_name="HTTP API", version="1.0"),
        lambda: HttpApiAdapter(
            secret_resolver=lambda reference: "test-token" if reference.startswith("vault://") else None,
            client_factory=_factory(mock_app),
        ),
    )
    adapter = registry.create(_config())
    context = AdapterRuntimeContext(run_id="run-http-1", environment_id="servicedesk_v1")
    task = AgentTask(task_id="task-http-1", scenario_id="SD-001", instruction="Find and assign INC1001")

    async def exercise():
        await adapter.connect(_config(), context)
        result = await adapter.execute(task, context)
        events = await adapter.collect_events()
        await adapter.stop()
        await adapter.disconnect()
        return result, events

    result, events = asyncio.run(exercise())
    assert captured["authorization"] == "Bearer test-token"
    assert captured["request"]["task"]["task_id"] == "task-http-1"
    assert captured["request"]["context"]["run_id"] == "run-http-1"
    assert captured["request"]["limits"] == {"timeout_seconds": 8, "max_actions": 12}
    assert captured["events_run_id"] == "run-http-1"
    assert captured["stop"] == {"run_id": "run-http-1"}

    assert result.status.value == "completed"
    assert result.provenance == EventProvenance.AGENT_REPORTED
    assert result.output == {"answer": "done", "echo": "[REDACTED]"}
    assert result.metadata["echo"] == "[REDACTED]"
    assert len(events) == 2
    assert {event.provenance for event in events} == {EventProvenance.ADAPTER_REPORTED}
    assert all(event.payload["token"] == "[REDACTED]" for event in events)
    assert adapter._client is None


def test_http_api_adapter_normalizes_authentication_and_invalid_response_errors():
    auth_app = FastAPI()

    @auth_app.post("/v1/execute")
    async def unauthorized():
        return JSONResponse(status_code=401, content={"detail": "not authorized"})

    malformed_app = FastAPI()

    @malformed_app.post("/v1/execute")
    async def malformed():
        return {"output": "missing required status"}

    async def run_auth_failure():
        adapter = HttpApiAdapter(secret_resolver=lambda _: "test-token", client_factory=_factory(auth_app))
        config = _config(events_path=None, stop_path=None)
        await adapter.connect(config, AdapterRuntimeContext(run_id="r1", environment_id="servicedesk_v1"))
        with pytest.raises(AdapterError) as exc:
            await adapter.execute(AgentTask(task_id="t1", scenario_id="SD-001", instruction="Do task"), AdapterRuntimeContext(run_id="r1", environment_id="servicedesk_v1"))
        await adapter.disconnect()
        return exc.value

    async def run_protocol_failure():
        adapter = HttpApiAdapter(secret_resolver=lambda _: "test-token", client_factory=_factory(malformed_app))
        config = _config(events_path=None, stop_path=None)
        await adapter.connect(config, AdapterRuntimeContext(run_id="r2", environment_id="servicedesk_v1"))
        with pytest.raises(AdapterError) as exc:
            await adapter.execute(AgentTask(task_id="t2", scenario_id="SD-001", instruction="Do task"), AdapterRuntimeContext(run_id="r2", environment_id="servicedesk_v1"))
        await adapter.disconnect()
        return exc.value

    auth_error = asyncio.run(run_auth_failure())
    protocol_error = asyncio.run(run_protocol_failure())
    assert auth_error.info.code == AdapterErrorCode.AUTHENTICATION_FAILED
    assert protocol_error.info.code == AdapterErrorCode.PROTOCOL_ERROR


def test_http_api_adapter_normalizes_timeout_and_rejects_missing_auth_reference():
    def timeout_handler(request: httpx.Request):
        raise httpx.ReadTimeout("sensitive endpoint detail", request=request)

    async def run_timeout():
        adapter = HttpApiAdapter(
            secret_resolver=lambda _: "test-token",
            client_factory=lambda **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler), **kwargs),
        )
        config = _config(events_path=None, stop_path=None)
        context = AdapterRuntimeContext(run_id="r-timeout", environment_id="servicedesk_v1")
        await adapter.connect(config, context)
        with pytest.raises(AdapterError) as exc:
            await adapter.execute(AgentTask(task_id="t3", scenario_id="SD-001", instruction="Do task"), context)
        await adapter.disconnect()
        return exc.value

    timeout_error = asyncio.run(run_timeout())
    assert timeout_error.info.code == AdapterErrorCode.TIMEOUT
    assert "sensitive endpoint" not in timeout_error.info.message

    async def run_missing_secret():
        adapter = HttpApiAdapter(secret_resolver=lambda _: None, client_factory=_factory(mock_app))
        with pytest.raises(AdapterError) as exc:
            await adapter.connect(_config(), AdapterRuntimeContext(run_id="r-missing", environment_id="servicedesk_v1"))
        return exc.value

    missing_secret_error = asyncio.run(run_missing_secret())
    assert missing_secret_error.info.code == AdapterErrorCode.CONFIGURATION_INVALID


def test_http_adapter_settings_enforce_transport_and_path_safety():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        HttpApiAdapterSettings(base_url="http://api.example.com")
    with pytest.raises(ValidationError):
        HttpApiAdapterSettings(base_url="https://user:pass@api.example.com")
    with pytest.raises(ValidationError):
        HttpApiAdapterSettings(base_url="https://api.example.com", execute_path="/../admin")
    with pytest.raises(ValidationError):
        HttpApiAdapterSettings(base_url="https://api.example.com", headers={"Authorization": "Bearer raw-token"})
    valid = HttpApiAdapterSettings(base_url="https://api.example.com")
    assert valid.base_url.host == "api.example.com"


def test_http_api_adapter_normalizes_server_and_connection_failures():
    async def run_server_failure():
        adapter = HttpApiAdapter(
            secret_resolver=lambda _: "test-token",
            client_factory=lambda **kwargs: httpx.AsyncClient(
                transport=httpx.MockTransport(lambda request: httpx.Response(503, json={"detail": "unavailable"})),
                **kwargs,
            ),
        )
        context = AdapterRuntimeContext(run_id="r-server", environment_id="servicedesk_v1")
        await adapter.connect(_config(events_path=None, stop_path=None), context)
        with pytest.raises(AdapterError) as exc:
            await adapter.execute(AgentTask(task_id="t-server", scenario_id="SD-001", instruction="Do task"), context)
        await adapter.disconnect()
        return exc.value

    async def run_connection_failure():
        def fail_request(request: httpx.Request):
            raise httpx.ConnectError("private host information", request=request)
        adapter = HttpApiAdapter(
            secret_resolver=lambda _: "test-token",
            client_factory=lambda **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(fail_request), **kwargs),
        )
        context = AdapterRuntimeContext(run_id="r-connect", environment_id="servicedesk_v1")
        await adapter.connect(_config(events_path=None, stop_path=None), context)
        with pytest.raises(AdapterError) as exc:
            await adapter.execute(AgentTask(task_id="t-connect", scenario_id="SD-001", instruction="Do task"), context)
        await adapter.disconnect()
        return exc.value

    server_error = asyncio.run(run_server_failure())
    connection_error = asyncio.run(run_connection_failure())
    assert server_error.info.code == AdapterErrorCode.EXECUTION_FAILED
    assert server_error.info.retryable is True
    assert connection_error.info.code == AdapterErrorCode.CONNECTION_FAILED
    assert "private host" not in connection_error.info.message


def test_http_api_adapter_exposes_unsupported_cooperative_stop_explicitly():
    async def exercise():
        adapter = HttpApiAdapter(secret_resolver=lambda _: "test-token", client_factory=_factory(mock_app))
        await adapter.connect(_config(events_path=None, stop_path=None), AdapterRuntimeContext(run_id="r-no-stop", environment_id="servicedesk_v1"))
        assert adapter.capabilities.cooperative_stop is False
        with pytest.raises(AdapterError) as exc:
            await adapter.stop()
        await adapter.disconnect()
        return exc.value
    error = asyncio.run(exercise())
    assert error.info.code == AdapterErrorCode.UNSUPPORTED_CAPABILITY
