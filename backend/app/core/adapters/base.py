import asyncio
from typing import Protocol, runtime_checkable

from app.schemas.adapters import (
    AdapterConfig,
    AdapterCapabilities,
    AdapterErrorCode,
    AdapterErrorInfo,
    AdapterEvent,
    AdapterRuntimeContext,
    AgentExecutionResult,
    AgentTask,
)


class AdapterError(RuntimeError):
    """Provider-neutral adapter failure with stable machine-readable semantics."""

    def __init__(
        self,
        code: AdapterErrorCode,
        message: str,
        *,
        retryable: bool = False,
        details: dict | None = None,
    ):
        super().__init__(message)
        self.info = AdapterErrorInfo(
            code=code,
            message=message[:500],
            retryable=retryable,
            details=details or {},
        )


class AdapterContractError(TypeError):
    """Raised when an adapter does not satisfy the common lifecycle contract."""


class AdapterRegistrationError(ValueError):
    """Raised when an adapter type cannot be registered or resolved."""


def normalize_adapter_error(error: BaseException) -> AdapterErrorInfo:
    """Map runtime failures to safe, provider-neutral error codes."""
    if isinstance(error, AdapterError):
        return error.info
    if isinstance(error, asyncio.CancelledError):
        return AdapterErrorInfo(code=AdapterErrorCode.CANCELLED, message="Adapter execution was cancelled", retryable=False)
    if isinstance(error, TimeoutError):
        return AdapterErrorInfo(code=AdapterErrorCode.TIMEOUT, message="Adapter operation exceeded its timeout", retryable=True)
    if isinstance(error, ConnectionError):
        return AdapterErrorInfo(code=AdapterErrorCode.CONNECTION_FAILED, message="Adapter connection failed", retryable=True)
    if isinstance(error, NotImplementedError):
        return AdapterErrorInfo(code=AdapterErrorCode.UNSUPPORTED_CAPABILITY, message="Adapter does not support the requested capability", retryable=False)
    if isinstance(error, ValueError):
        return AdapterErrorInfo(code=AdapterErrorCode.CONFIGURATION_INVALID, message="Adapter configuration or input was rejected", retryable=False)
    return AdapterErrorInfo(
        code=AdapterErrorCode.UNKNOWN,
        message=f"Unexpected adapter failure ({type(error).__name__})",
        retryable=False,
    )


@runtime_checkable
class AgentAdapter(Protocol):
    """Provider-neutral asynchronous lifecycle expected from every agent adapter."""

    @property
    def capabilities(self) -> AdapterCapabilities:
        ...

    async def connect(self, config: AdapterConfig, context: AdapterRuntimeContext) -> None:
        """Validate configuration and establish an adapter session."""

    async def execute(self, task: AgentTask, context: AdapterRuntimeContext) -> AgentExecutionResult:
        """Execute one task and return the agent-reported result envelope."""

    async def collect_events(self) -> list[AdapterEvent]:
        """Return currently available normalized adapter events."""

    async def stop(self) -> None:
        """Request cooperative cancellation; completion is confirmed by execute/result state."""

    async def disconnect(self) -> None:
        """Release adapter resources; safe to call after stop or failure."""
