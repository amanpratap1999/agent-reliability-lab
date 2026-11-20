from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from pydantic import ValidationError

from app.core.adapters.base import AdapterError
from app.schemas.adapters import (
    AdapterCapabilities,
    AdapterConfig,
    AdapterErrorCode,
    AdapterErrorInfo,
    AdapterEvent,
    AdapterRuntimeContext,
    AgentExecutionResult,
    AgentTask,
    EventProvenance,
    HttpApiAdapterSettings,
    HttpApiAgentResponse,
    HttpApiErrorPayload,
    HttpApiEventRecord,
    HttpApiEventsResponse,
    HttpApiExecutionLimits,
    HttpApiExecutionRequest,
)


SecretResolver = Callable[[str], str | None]
HttpClientFactory = Callable[..., httpx.AsyncClient]


class HttpApiAdapter:
    """Transparent adapter for an external agent exposed through a JSON HTTP API.

    Remote result envelopes are agent-reported. Event records returned by the API
    are adapter-reported; this adapter never upgrades them to direct observation.
    """

    def __init__(
        self,
        secret_resolver: SecretResolver | None = None,
        client_factory: HttpClientFactory = httpx.AsyncClient,
    ):
        self._secret_resolver = secret_resolver
        self._client_factory = client_factory
        self._client: httpx.AsyncClient | None = None
        self._settings: HttpApiAdapterSettings | None = None
        self._timeout_seconds = 120
        self._max_actions = 100
        self._last_run_id: str | None = None
        self._secret_value: str | None = None
        self._events: dict[str, AdapterEvent] = {}
        self._capabilities = AdapterCapabilities(
            event_collection=True,
            cooperative_stop=False,
            observability_notes=[
                "HTTP task outputs are agent_reported.",
                "Events returned by the remote API are adapter_reported.",
                "This adapter does not independently observe environment state.",
            ],
        )

    @property
    def capabilities(self) -> AdapterCapabilities:
        return self._capabilities

    async def connect(self, config: AdapterConfig, context: AdapterRuntimeContext) -> None:
        if config.adapter_type != "http_api":
            raise AdapterError(AdapterErrorCode.CONFIGURATION_INVALID, "HTTP adapter requires adapter_type='http_api'")
        if self._client is not None:
            raise AdapterError(AdapterErrorCode.PROTOCOL_ERROR, "HTTP adapter is already connected")
        try:
            settings = HttpApiAdapterSettings.model_validate(config.settings)
        except ValidationError as exc:
            raise AdapterError(AdapterErrorCode.CONFIGURATION_INVALID, "HTTP API adapter settings are invalid") from exc

        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        headers.update(settings.headers)
        self._secret_value = None
        if settings.auth_ref_key is not None:
            reference = config.secret_refs.get(settings.auth_ref_key)
            if not reference or self._secret_resolver is None:
                raise AdapterError(AdapterErrorCode.CONFIGURATION_INVALID, "HTTP API authentication secret reference is missing or cannot be resolved")
            try:
                secret = self._secret_resolver(reference)
            except Exception as exc:
                raise AdapterError(AdapterErrorCode.CONFIGURATION_INVALID, "HTTP API authentication reference could not be resolved") from exc
            if not secret:
                raise AdapterError(AdapterErrorCode.CONFIGURATION_INVALID, "HTTP API authentication reference resolved to an empty value")
            self._secret_value = secret
            headers[settings.auth_header] = f"Bearer {secret}" if settings.auth_scheme == "bearer" else secret

        self._settings = settings
        self._timeout_seconds = config.timeout_seconds
        self._max_actions = config.max_actions
        self._events.clear()
        self._last_run_id = None
        try:
            self._client = self._client_factory(
                base_url=str(settings.base_url),
                timeout=httpx.Timeout(config.timeout_seconds),
                headers=headers,
                follow_redirects=False,
            )
        except Exception as exc:
            self._client = None
            raise AdapterError(AdapterErrorCode.CONNECTION_FAILED, "HTTP client initialization failed", retryable=True) from exc

        self._capabilities = AdapterCapabilities(
            event_collection=True,
            cooperative_stop=settings.stop_path is not None,
            structured_tool_calls=settings.structured_tool_calls,
            screenshots=settings.screenshots,
            max_concurrent_runs=1,
            observability_notes=[
                "HTTP task outputs are agent_reported.",
                "Events returned by the remote API are adapter_reported.",
                "This adapter does not independently observe environment state.",
            ],
        )

    def _require_connection(self) -> tuple[httpx.AsyncClient, HttpApiAdapterSettings]:
        if self._client is None or self._settings is None:
            raise AdapterError(AdapterErrorCode.CONNECTION_FAILED, "HTTP adapter is not connected")
        return self._client, self._settings

    def _raise_for_http_status(self, response: httpx.Response) -> None:
        status = response.status_code
        if 200 <= status < 300:
            return
        if status in {401, 403}:
            raise AdapterError(AdapterErrorCode.AUTHENTICATION_FAILED, "HTTP agent authentication failed", retryable=False)
        if status in {408, 504}:
            raise AdapterError(AdapterErrorCode.TIMEOUT, "HTTP agent request timed out", retryable=True)
        if status in {400, 422}:
            raise AdapterError(AdapterErrorCode.PROTOCOL_ERROR, "HTTP agent rejected the request contract", retryable=False)
        if status == 429 or status >= 500:
            raise AdapterError(AdapterErrorCode.EXECUTION_FAILED, f"HTTP agent returned status {status}", retryable=True)
        raise AdapterError(AdapterErrorCode.EXECUTION_FAILED, f"HTTP agent returned status {status}", retryable=False)

    def _redact(self, value):
        if isinstance(value, str):
            return value.replace(self._secret_value, "[REDACTED]") if self._secret_value else value
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        if isinstance(value, dict):
            return {key: self._redact(item) for key, item in value.items()}
        return value

    def _map_remote_error(self, error: HttpApiErrorPayload | None) -> AdapterErrorInfo | None:
        if error is None:
            return None
        try:
            code = AdapterErrorCode(error.code) if error.code else AdapterErrorCode.EXECUTION_FAILED
        except ValueError:
            code = AdapterErrorCode.EXECUTION_FAILED
        return AdapterErrorInfo(
            code=code,
            message=self._redact(error.message)[:500],
            retryable=error.retryable,
            details=self._redact(error.details),
        )

    def _map_event(self, record: HttpApiEventRecord) -> AdapterEvent:
        event_id = self._redact(record.event_id) if record.event_id else str(uuid4())
        event = AdapterEvent(
            event_id=event_id,
            event_type=self._redact(record.event_type),
            occurred_at=record.occurred_at or datetime.now(timezone.utc),
            provenance=EventProvenance.ADAPTER_REPORTED,
            actor=self._redact(record.actor),
            action=self._redact(record.action),
            status=self._redact(record.status),
            payload=self._redact(record.payload),
        )
        self._events[event.event_id] = event
        return event

    async def execute(self, task: AgentTask, context: AdapterRuntimeContext) -> AgentExecutionResult:
        client, settings = self._require_connection()
        self._last_run_id = context.run_id
        request_body = HttpApiExecutionRequest(
            task=task,
            context=context,
            limits=HttpApiExecutionLimits(timeout_seconds=self._timeout_seconds, max_actions=self._max_actions),
        )
        try:
            response = await client.post(settings.execute_path, json=request_body.model_dump(mode="json"))
        except httpx.TimeoutException as exc:
            raise AdapterError(AdapterErrorCode.TIMEOUT, "HTTP agent execution timed out", retryable=True) from exc
        except httpx.RequestError as exc:
            raise AdapterError(AdapterErrorCode.CONNECTION_FAILED, "HTTP agent request failed", retryable=True) from exc
        self._raise_for_http_status(response)
        try:
            remote = HttpApiAgentResponse.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise AdapterError(AdapterErrorCode.PROTOCOL_ERROR, "HTTP agent returned an invalid response payload") from exc

        for event in remote.events:
            self._map_event(event)
        return AgentExecutionResult(
            status=remote.status,
            output=self._redact(remote.output),
            provenance=EventProvenance.AGENT_REPORTED,
            error=self._map_remote_error(remote.error),
            started_at=remote.started_at,
            finished_at=remote.finished_at,
            metadata=self._redact(remote.metadata),
        )

    async def collect_events(self) -> list[AdapterEvent]:
        client, settings = self._require_connection()
        if settings.events_path is not None and self._last_run_id is not None:
            try:
                response = await client.get(settings.events_path, params={"run_id": self._last_run_id})
            except httpx.TimeoutException as exc:
                raise AdapterError(AdapterErrorCode.TIMEOUT, "HTTP event collection timed out", retryable=True) from exc
            except httpx.RequestError as exc:
                raise AdapterError(AdapterErrorCode.CONNECTION_FAILED, "HTTP event collection failed", retryable=True) from exc
            self._raise_for_http_status(response)
            try:
                payload = HttpApiEventsResponse.model_validate(response.json())
            except (ValueError, ValidationError) as exc:
                raise AdapterError(AdapterErrorCode.PROTOCOL_ERROR, "HTTP event endpoint returned an invalid payload") from exc
            for event in payload.events:
                self._map_event(event)
        return list(self._events.values())

    async def stop(self) -> None:
        client, settings = self._require_connection()
        if settings.stop_path is None:
            raise AdapterError(AdapterErrorCode.UNSUPPORTED_CAPABILITY, "HTTP agent does not expose a cooperative stop endpoint")
        if self._last_run_id is None:
            return
        try:
            response = await client.post(settings.stop_path, json={"run_id": self._last_run_id})
        except httpx.TimeoutException as exc:
            raise AdapterError(AdapterErrorCode.TIMEOUT, "HTTP stop request timed out", retryable=True) from exc
        except httpx.RequestError as exc:
            raise AdapterError(AdapterErrorCode.CONNECTION_FAILED, "HTTP stop request failed", retryable=True) from exc
        self._raise_for_http_status(response)

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.aclose()
        self._client = None
        self._settings = None
        self._last_run_id = None
        self._secret_value = None
        self._events.clear()
