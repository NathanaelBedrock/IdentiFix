from __future__ import annotations
from collectors.base import BaseCollector
from core.models import CollectorResult, InvestigationTarget, ProfileHit

try:
    from socialscan.util import execute_queries, Platforms
    from socialscan.platforms import QueryError
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


class SocialscanCollector(BaseCollector):
    name = "socialscan"
    requires_username = True

    @classmethod
    def available(cls) -> bool:
        return _AVAILABLE

    async def _collect(self, target: InvestigationTarget, result: CollectorResult) -> None:
        username = target.username
        queries = [username]
        if target.email:
            queries.append(target.email)

        responses = await execute_queries(queries, list(Platforms))
        for resp in responses:
            if resp.available is False:
                result.profile_hits.append(ProfileHit(
                    platform=resp.platform.name,
                    url=(
                        f"https://reddit.com/u/{username}" if resp.platform.name == "REDDIT"
                        else f"https://x.com/{username}" if resp.platform.name == "TWITTER"
                        else f"https://{resp.platform.name.lower()}.com/{username}"
                    ),
                    username=username,
                    exists=True,
                    metadata={"message": resp.message},
                ))
