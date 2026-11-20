from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator


class EventProvenance(str, Enum):
    DIRECTLY_OBSERVED = "directly_observed"
    ADAPTER_REPORTED = "adapter_reported"
    AGENT_REPORTED = "agent_reported"
    INFERRED = "inferred"


class AdapterErrorCode(str, Enum):
    CONFIGURATION_INVALID = "configuration_invalid"
    CONNECTION_FAILED = "connection_failed"
    EXECUTION_FAILED = "execution_failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    PROTOCOL_ERROR = "protocol_error"
    UNKNOWN = "unknown"
    AUTHENTICATION_FAILED = "authentication_failed"


class ExecutionStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    INCONCLUSIVE = "inconclusive"


class AdapterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    adapter_type: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    config_version: str = "1"
    timeout_seconds: int = Field(default=120, ge=1, le=3600)
    max_actions: int = Field(default=100, ge=1, le=10000)
    settings: dict[str, Any] = Field(default_factory=dict)
    # Values are secret-manager references only, never credential values.
    secret_refs: dict[str, str] = Field(default_factory=dict)

    @field_validator("settings")
    @classmethod
    def reject_secret_bearing_setting_names(cls, value: dict[str, Any]) -> dict[str, Any]:
        forbidden = ("api_key", "access_token", "refresh_token", "password", "secret", "credential", "private_key", "authorization")
        def inspect(node: Any) -> None:
            if isinstance(node, dict):
                for key, nested in node.items():
                    normalized = str(key).lower().replace("-", "_")
                    if any(part in normalized for part in forbidden):
                        raise ValueError("Secret values must be supplied through secret_refs, not settings")
                    inspect(nested)
            elif isinstance(node, list):
                for nested in node:
                    inspect(nested)
        inspect(value)
        return value

    @field_validator("secret_refs")
    @classmethod
    def require_secret_reference_uri(cls, value: dict[str, str]) -> dict[str, str]:
        allowed_schemes = ("vault://", "env://", "secret://", "op://")
        if any(not reference.startswith(allowed_schemes) for reference in value.values()):
            raise ValueError("secret_refs values must be references using vault://, env://, secret:// or op://")
        return value


class AdapterRuntimeContext(BaseModel):
    run_id: str
    environment_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentTask(BaseModel):
    task_id: str
    scenario_id: str
    instruction: str = Field(min_length=1, max_length=10000)
    context: dict[str, Any] = Field(default_factory=dict)


class AdapterCapabilities(BaseModel):
    event_collection: bool = True
    cooperative_stop: bool = True
    structured_tool_calls: bool = False
    screenshots: bool = False
    max_concurrent_runs: int = Field(default=1, ge=1, le=1000)
    observability_notes: list[str] = Field(default_factory=list)


class AdapterMetadata(BaseModel):
    adapter_type: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    display_name: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=40)
    description: str = Field(default="", max_length=500)
    capabilities: AdapterCapabilities = Field(default_factory=AdapterCapabilities)


class AdapterErrorInfo(BaseModel):
    code: AdapterErrorCode
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class AdapterEvent(BaseModel):
    event_id: str
    event_type: str = Field(min_length=1, max_length=100)
    occurred_at: datetime
    provenance: EventProvenance
    actor: str | None = None
    action: str | None = None
    status: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentExecutionResult(BaseModel):
    status: ExecutionStatus
    output: str | dict[str, Any] | None = None
    provenance: EventProvenance = EventProvenance.AGENT_REPORTED
    error: AdapterErrorInfo | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HttpApiAdapterSettings(BaseModel):
    """Provider-neutral HTTP endpoint and auth-reference settings."""
    model_config = ConfigDict(extra="forbid")
    base_url: AnyHttpUrl
    execute_path: str = "/v1/execute"
    events_path: str | None = None
    stop_path: str | None = None
    auth_ref_key: str | None = "http_auth"
    auth_header: str = "Authorization"
    auth_scheme: Literal["bearer", "raw"] = "bearer"
    headers: dict[str, str] = Field(default_factory=dict)
    structured_tool_calls: bool = False
    screenshots: bool = False

    @field_validator("base_url")
    @classmethod
    def require_https_except_loopback(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.username or value.password or value.query or value.fragment:
            raise ValueError("base_url cannot embed credentials, query parameters or fragments")
        if value.scheme != "https" and value.host not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("HTTPS is required except for loopback mock/test endpoints")
        return value

    @field_validator("execute_path", "events_path", "stop_path")
    @classmethod
    def validate_relative_api_path(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.startswith("/") or "://" in value or "?" in value or "#" in value:
            raise ValueError("HTTP adapter paths must be absolute paths on the configured base URL")
        if any(segment == ".." for segment in value.split("/")):
            raise ValueError("HTTP adapter paths cannot traverse parent directories")
        return value

    @field_validator("auth_header")
    @classmethod
    def validate_auth_header(cls, value: str) -> str:
        import re
        if not re.fullmatch(r"[A-Za-z0-9-]{1,80}", value):
            raise ValueError("auth_header must be a valid HTTP header name")
        if value.lower() in {"host", "content-length", "connection", "transfer-encoding", "cookie", "set-cookie", "proxy-authorization"}:
            raise ValueError("auth_header cannot target a transport-controlled or cookie header")
        return value

    @field_validator("headers")
    @classmethod
    def reject_sensitive_custom_headers(cls, value: dict[str, str]) -> dict[str, str]:
        forbidden = {"authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key", "host", "content-length", "connection", "transfer-encoding"}
        for name, header_value in value.items():
            if name.lower() in forbidden:
                raise ValueError("Authentication headers must use secret_refs, not custom headers")
            if "\r" in header_value or "\n" in header_value:
                raise ValueError("HTTP header values cannot contain line breaks")
        return value


class HttpApiErrorPayload(BaseModel):
    code: str | None = None
    message: str = "Remote agent execution failed"
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class HttpApiEventRecord(BaseModel):
    event_id: str | None = None
    event_type: str = Field(min_length=1, max_length=100)
    occurred_at: datetime | None = None
    actor: str | None = None
    action: str | None = None
    status: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class HttpApiAgentResponse(BaseModel):
    status: ExecutionStatus
    output: str | dict[str, Any] | None = None
    error: HttpApiErrorPayload | None = None
    events: list[HttpApiEventRecord] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HttpApiEventsResponse(BaseModel):
    events: list[HttpApiEventRecord] = Field(default_factory=list)


class HttpApiExecutionLimits(BaseModel):
    timeout_seconds: int = Field(ge=1, le=3600)
    max_actions: int = Field(ge=1, le=10000)


class HttpApiExecutionRequest(BaseModel):
    task: AgentTask
    context: AdapterRuntimeContext
    limits: HttpApiExecutionLimits
