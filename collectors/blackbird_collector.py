"""
Blackbird: Email & username search on 600+ sites.
Invoked as a subprocess since it lacks a stable importable Python API.
"""
from __future__ import annotations
import asyncio
import json
import shutil
from collectors.base import BaseCollector
from core.models import CollectorResult, InvestigationTarget, ProfileHit, EmailRegistration


class BlackbirdCollector(BaseCollector):
    name = "blackbird"
    requires_username = True

    @classmethod
    def available(cls) -> bool:
        return shutil.which("blackbird") is not None

    async def _collect(self, target: InvestigationTarget, result: CollectorResult) -> None:
        username = target.username
        cmd = ["blackbird", "-u", username, "--json"]
        if target.email:
            cmd += ["-e", target.email]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return

        for site in data.get("found", []):
            result.profile_hits.append(ProfileHit(
                platform=site.get("site", "unknown"),
                url=site.get("url", ""),
                username=username,
                exists=True,
                metadata=site,
            ))
