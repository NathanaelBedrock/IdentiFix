"""Sociopath: profile spider & identity enrichment — subprocess wrapper."""
from __future__ import annotations
import asyncio
import json
import shutil
from collectors.base import BaseCollector
from core.models import CollectorResult, InvestigationTarget, ProfileHit


class SociopathCollector(BaseCollector):
    name = "sociopath"
    requires_username = True

    @classmethod
    def available(cls) -> bool:
        return shutil.which("sociopath") is not None

    async def _collect(self, target: InvestigationTarget, result: CollectorResult) -> None:
        username = target.username
        proc = await asyncio.create_subprocess_exec(
            "sociopath", "-u", username, "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return

        result.raw_data["sociopath"] = data
        for entry in data.get("profiles", []):
            result.profile_hits.append(ProfileHit(
                platform=entry.get("platform", "unknown"),
                url=entry.get("url", ""),
                username=username,
                exists=True,
                metadata=entry,
            ))
