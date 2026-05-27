"""ShareTrace: resolves social media tracking links — subprocess wrapper."""
from __future__ import annotations
import asyncio
import json
import shutil
from collectors.base import BaseCollector
from core.models import CollectorResult, InvestigationTarget


class ShareTraceCollector(BaseCollector):
    name = "sharetrace"
    requires_username = True

    @classmethod
    def available(cls) -> bool:
        return shutil.which("sharetrace") is not None

    async def _collect(self, target: InvestigationTarget, result: CollectorResult) -> None:
        username = target.username
        proc = await asyncio.create_subprocess_exec(
            "sharetrace", username, "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return
        result.raw_data["sharetrace"] = data
