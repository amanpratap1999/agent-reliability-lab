from collections.abc import Callable

from app.core.adapters.base import AgentAdapter, AdapterContractError, AdapterRegistrationError
from app.schemas.adapters import AdapterConfig, AdapterMetadata


AdapterFactory = Callable[[], AgentAdapter]


class AdapterRegistry:
    """In-memory registry keyed by neutral adapter type identifiers."""

    def __init__(self):
        self._factories: dict[str, AdapterFactory] = {}
        self._metadata: dict[str, AdapterMetadata] = {}

    def register(self, metadata: AdapterMetadata, factory: AdapterFactory, *, replace: bool = False) -> None:
        adapter_type = metadata.adapter_type
        if not callable(factory):
            raise AdapterRegistrationError("Adapter factory must be callable")
        if adapter_type in self._factories and not replace:
            raise AdapterRegistrationError(f"Adapter type '{adapter_type}' is already registered")
        self._factories[adapter_type] = factory
        self._metadata[adapter_type] = metadata

    def unregister(self, adapter_type: str) -> None:
        if adapter_type not in self._factories:
            raise AdapterRegistrationError(f"Adapter type '{adapter_type}' is not registered")
        del self._factories[adapter_type]
        del self._metadata[adapter_type]

    def create(self, config: AdapterConfig) -> AgentAdapter:
        factory = self._factories.get(config.adapter_type)
        if factory is None:
            raise AdapterRegistrationError(f"Adapter type '{config.adapter_type}' is not registered")
        adapter = factory()
        if not isinstance(adapter, AgentAdapter):
            raise AdapterContractError(f"Factory for '{config.adapter_type}' returned an object that does not implement AgentAdapter")
        return adapter

    def get_metadata(self, adapter_type: str) -> AdapterMetadata:
        metadata = self._metadata.get(adapter_type)
        if metadata is None:
            raise AdapterRegistrationError(f"Adapter type '{adapter_type}' is not registered")
        return metadata

    def list_metadata(self) -> list[AdapterMetadata]:
        return [self._metadata[key] for key in sorted(self._metadata)]

    def contains(self, adapter_type: str) -> bool:
        return adapter_type in self._factories
