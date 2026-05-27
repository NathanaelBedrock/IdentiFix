from __future__ import annotations
import asyncio
from collectors.base import BaseCollector
from core.models import CollectorResult, InvestigationTarget, EmailRegistration

try:
    import httpx as _httpx
    import holehe.modules as _holehe_modules
    from holehe.core import get_functions, import_submodules
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


class HolehCollector(BaseCollector):
    name = "holehe"
    requires_email = True

    @classmethod
    def available(cls) -> bool:
        return _AVAILABLE

    async def _collect(self, target: InvestigationTarget, result: CollectorResult) -> None:
        email = target.email
        modules = get_functions(import_submodules(_holehe_modules))
        out: list[dict] = []

        async with _httpx.AsyncClient(timeout=15) as client:
            tasks = [mod(email, client, out) for mod in modules]
            await asyncio.gather(*tasks, return_exceptions=True)

        for entry in out:
            if not isinstance(entry, dict):
                continue
            result.email_registrations.append(EmailRegistration(
                site=entry.get("name", "unknown"),
                registered=bool(entry.get("exists", False)),
                url=entry.get("domain"),
                metadata={
                    k: v for k, v in entry.items()
                    if k not in ("name", "domain", "exists") and v is not None
                },
            ))
