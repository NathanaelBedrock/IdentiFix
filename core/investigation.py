from __future__ import annotations
import asyncio
from datetime import datetime
from core.models import (
    Investigation,
    InvestigationStatus,
    CollectorStatus,
    SSEEvent,
)
from collectors import get_collector_instances
from api.discord_client import DiscordClient
from api.twitter_client import TwitterClient
from api.reddit_client import RedditClient
from correlators.identity import correlate
from graph.builder import build_graph
from enrichers.ai import generate_ai_report


async def run_investigation(investigation: Investigation, store) -> None:
    """Full investigation pipeline executed as a background task."""
    investigation.status = InvestigationStatus.RUNNING
    investigation.started_at = datetime.utcnow()
    store.save(investigation)
    store.emit(investigation.id, SSEEvent(event="started", data={"id": investigation.id}))

    try:
        # ── Platform API collection ──────────────────────────────────────────
        await _collect_platform_apis(investigation, store)

        # ── Tool collectors (run in parallel) ───────────────────────────────
        await _run_collectors(investigation, store)

        # ── Correlate & build graph ──────────────────────────────────────────
        correlate(investigation)
        investigation.graph = build_graph(investigation)
        store.save(investigation)
        store.emit(investigation.id, SSEEvent(event="graph_ready", data={}))

        # ── AI report ───────────────────────────────────────────────────────
        investigation.ai_report = await generate_ai_report(investigation)

        investigation.status = InvestigationStatus.COMPLETED
        investigation.completed_at = datetime.utcnow()
        store.save(investigation)
        store.emit(investigation.id, SSEEvent(
            event="completed",
            data={"summary": investigation.summary()},
        ))

    except asyncio.CancelledError:
        investigation.status = InvestigationStatus.CANCELLED
        investigation.completed_at = datetime.utcnow()
        store.save(investigation)
        store.emit(investigation.id, SSEEvent(event="cancelled", data={}))

    except Exception as exc:
        investigation.status = InvestigationStatus.FAILED
        investigation.error = str(exc)
        investigation.completed_at = datetime.utcnow()
        store.save(investigation)
        store.emit(investigation.id, SSEEvent(event="failed", data={"error": str(exc)}))


async def _collect_platform_apis(investigation: Investigation, store) -> None:
    target = investigation.target

    async def _discord():
        if not target.discord_id:
            return
        try:
            client = DiscordClient()
            data = await client.get_user(target.discord_id)
            investigation.raw_data = getattr(investigation, "raw_data", {})
            investigation.results.append(
                _api_result("discord_api", raw=data, hits=[{
                    "platform": "Discord",
                    "url": f"https://discord.com/users/{target.discord_id}",
                    "username": data.get("username", target.discord_id),
                    "metadata": data,
                }])
            )
            store.save(investigation)
            store.emit(investigation.id, SSEEvent(event="collector_done", data={
                "collector": "discord_api", "hits": 1,
            }))
        except Exception as exc:
            _emit_collector_error(investigation, store, "discord_api", exc)

    async def _twitter():
        if not target.twitter_handle:
            return
        try:
            client = TwitterClient()
            data = await client.get_user_by_username(target.twitter_handle)
            user = data.get("data", {})
            investigation.results.append(
                _api_result("twitter_api", raw=data, hits=[{
                    "platform": "Twitter/X",
                    "url": f"https://twitter.com/{target.twitter_handle}",
                    "username": user.get("username", target.twitter_handle),
                    "metadata": user,
                }])
            )
            store.save(investigation)
            store.emit(investigation.id, SSEEvent(event="collector_done", data={
                "collector": "twitter_api", "hits": 1,
            }))
        except Exception as exc:
            _emit_collector_error(investigation, store, "twitter_api", exc)

    async def _reddit():
        if not target.reddit_username:
            return
        try:
            client = RedditClient()
            data = await client.get_user(target.reddit_username)
            reddit_data = data.get("data", {})
            investigation.results.append(
                _api_result("reddit_api", raw=data, hits=[{
                    "platform": "Reddit",
                    "url": f"https://reddit.com/u/{target.reddit_username}",
                    "username": reddit_data.get("name", target.reddit_username),
                    "metadata": reddit_data,
                }])
            )
            store.save(investigation)
            store.emit(investigation.id, SSEEvent(event="collector_done", data={
                "collector": "reddit_api", "hits": 1,
            }))
        except Exception as exc:
            _emit_collector_error(investigation, store, "reddit_api", exc)

    await asyncio.gather(_discord(), _twitter(), _reddit())


async def _run_collectors(investigation: Investigation, store) -> None:
    collectors = get_collector_instances()
    target = investigation.target

    for c in collectors:
        investigation.collectors[c.name] = CollectorStatus.PENDING
    store.save(investigation)

    async def _run_one(collector):
        investigation.collectors[collector.name] = CollectorStatus.RUNNING
        store.emit(investigation.id, SSEEvent(event="collector_started", data={"collector": collector.name}))

        result = await collector.run(target)
        investigation.results.append(result)
        investigation.collectors[collector.name] = result.status
        store.save(investigation)
        store.emit(investigation.id, SSEEvent(event="collector_done", data={
            "collector": collector.name,
            "status": result.status.value,
            "hits": len(result.profile_hits) + len(result.email_registrations) + len(result.email_breaches),
        }))

    await asyncio.gather(*[_run_one(c) for c in collectors])


# ── Helpers ─────────────────────────────────────────────────────────────────

def _api_result(name: str, raw: dict, hits: list[dict]):
    from core.models import CollectorResult, CollectorStatus, ProfileHit
    return CollectorResult(
        collector=name,
        status=CollectorStatus.SUCCESS,
        profile_hits=[ProfileHit(**h) for h in hits],
        raw_data={name: raw},
    )


def _emit_collector_error(investigation, store, name: str, exc: Exception) -> None:
    from core.models import CollectorResult, CollectorStatus
    investigation.results.append(CollectorResult(
        collector=name,
        status=CollectorStatus.FAILED,
        error=str(exc),
    ))
    store.save(investigation)
    store.emit(investigation.id, SSEEvent(event="collector_done", data={
        "collector": name, "status": "failed", "error": str(exc),
    }))
