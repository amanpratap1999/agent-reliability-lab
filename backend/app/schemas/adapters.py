from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    error: AdapterErrorInfo | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
