from __future__ import annotations
import time
from abc import ABC, abstractmethod
from core.models import CollectorResult, CollectorStatus, InvestigationTarget


class BaseCollector(ABC):
    name: str = "base"
    requires_username: bool = False
    requires_email: bool = False
    requires_image: bool = False

    @classmethod
    def available(cls) -> bool:
        """Return False if required library is not installed."""
        return True

    def can_run(self, target: InvestigationTarget) -> bool:
        if self.requires_username and not target.username:
            return False
        if self.requires_email and not target.email:
            return False
        if self.requires_image and not target.image_path:
            return False
        return True

    async def run(self, target: InvestigationTarget) -> CollectorResult:
        result = CollectorResult(collector=self.name)

        if not self.available():
            result.status = CollectorStatus.SKIPPED
            result.error = f"Library for {self.name} is not installed"
            return result

        if not self.can_run(target):
            result.status = CollectorStatus.SKIPPED
            result.error = "Target does not have required fields"
            return result

        result.status = CollectorStatus.RUNNING
        start = time.monotonic()
        try:
            await self._collect(target, result)
            result.status = CollectorStatus.SUCCESS
        except Exception as exc:
            result.status = CollectorStatus.FAILED
            result.error = str(exc)
        finally:
            result.duration_seconds = round(time.monotonic() - start, 2)

        return result

    @abstractmethod
    async def _collect(self, target: InvestigationTarget, result: CollectorResult) -> None:
        """Fill `result` in-place with collected data."""
