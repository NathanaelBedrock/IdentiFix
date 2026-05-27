from __future__ import annotations
import asyncio
from collectors.base import BaseCollector
from core.models import CollectorResult, InvestigationTarget, ProfileHit

try:
    from sherlock_project.sherlock import sherlock
    from sherlock_project.sites import SitesInformation
    from sherlock_project.result import QueryStatus
    from sherlock_project.notify import QueryNotify
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


class SherlockCollector(BaseCollector):
    name = "sherlock"
    requires_username = True

    @classmethod
    def available(cls) -> bool:
        return _AVAILABLE

    async def _collect(self, target: InvestigationTarget, result: CollectorResult) -> None:
        username = target.username
        loop = asyncio.get_event_loop()

        def _run():
            sites = SitesInformation()
            site_data = {name: site.information for name, site in sites.sites.items()}
            return sherlock(username, site_data, QueryNotify())

        raw = await loop.run_in_executor(None, _run)

        for site_name, query_result in raw.items():
            if query_result.get("status") and query_result["status"].status == QueryStatus.CLAIMED:
                result.profile_hits.append(ProfileHit(
                    platform=site_name,
                    url=query_result.get("url_user") or "",
                    username=username,
                    exists=True,
                    metadata={"query_time": query_result["status"].query_time},
                ))
