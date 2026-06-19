from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProvisionResult:
    name: str
    provider: str
    endpoint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Provider(ABC):
    name: str = ""

    @abstractmethod
    def provision(self, plan: dict) -> ProvisionResult:
        ...

    @abstractmethod
    def verify(self, result: ProvisionResult) -> bool:
        ...

    @abstractmethod
    def destroy(self, result: ProvisionResult) -> None:
        ...
