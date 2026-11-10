from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """Base interface for all external AI and data providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider service."""
        pass

    @property
    @abstractmethod
    def is_mock(self) -> bool:
        """Returns True if the provider is currently operating in mock development mode."""
        pass
