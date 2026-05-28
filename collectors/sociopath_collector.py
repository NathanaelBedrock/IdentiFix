"""Sociopath: profile spider & identity enrichment — subprocess wrapper."""
from __future__ import annotations
import asyncio
import json
import shutil
from collectors.base import BaseCollector
from core.models import CollectorResult, InvestigationTarget, ProfileHit


class SociopathCollector(BaseCollector):
    name = "sociopath"
    requires_email = True

    @classmethod
    def available(cls) -> bool:
        return shutil.which("sociopath") is not None

    async def _collect(self, target: InvestigationTarget, result: CollectorResult) -> None:
        identity = target.email
        cmd = ["sociopath", "--email", target.email, "--json"]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        try:
            data = json.loads(stdout)
        except (json.JSONDecodeError, TypeError):
            return

        if not data:
            return

        profiles = data if isinstance(data, list) else data.get("profiles", [])
        result.raw_data["sociopath"] = profiles
        for entry in profiles:
            result.profile_hits.append(ProfileHit(
                platform=entry.get("Platform", "unknown"),
                url=entry.get("URL", ""),
                username=entry.get("Username") or identity,
                exists=True,
                metadata=entry,
            ))
