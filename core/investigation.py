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

        # ── Correlate (first pass — tags confirmed hits) ─────────────────────
        correlate(investigation)

        # ── Socid enrichment on confirmed profile URLs only ──────────────────
        await _enrich_with_socid(investigation, store)

        # ── Nametrace enrichment on hits that expose a full name ─────────────
        await _enrich_with_nametrace(investigation, store)

        # ── Build graph ──────────────────────────────────────────────────────
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


async def _enrich_with_socid(investigation: Investigation, store) -> None:
    try:
        from socid_extractor import extract as socid_extract
        import httpx
    except ImportError:
        return

    # Collect unique URLs from confirmed profile hits only
    url_to_hits: dict[str, list] = {}
    for result in investigation.results:
        for hit in result.profile_hits:
            if hit.url and hit.metadata.get("confirmed_by_multiple"):
                url_to_hits.setdefault(hit.url, []).append(hit)

    if not url_to_hits:
        return

    store.emit(investigation.id, SSEEvent(event="collector_started", data={"collector": "socid_enrichment"}))

    async def _fetch_and_enrich(client: httpx.AsyncClient, url: str, hits: list) -> None:
        try:
            resp = await client.get(url, timeout=10)
            if resp.status_code != 200:
                return
            extracted = socid_extract(resp.text)
            if extracted:
                for hit in hits:
                    hit.metadata["socid"] = extracted
        except Exception:
            pass

    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0"},
        follow_redirects=True,
    ) as client:
        await asyncio.gather(*[
            _fetch_and_enrich(client, url, hits)
            for url, hits in url_to_hits.items()
        ], return_exceptions=True)

    store.save(investigation)
    store.emit(investigation.id, SSEEvent(event="collector_done", data={"collector": "socid_enrichment"}))


def _extract_fullname(hit) -> str | None:
    m = hit.metadata
    ids = m.get("ids") if isinstance(m.get("ids"), dict) else {}
    socid = m.get("socid") if isinstance(m.get("socid"), dict) else {}
    return (
        m.get("full_name") or m.get("fullname") or m.get("global_name") or m.get("name")
        or ids.get("fullname") or ids.get("full_name") or ids.get("name")
        or socid.get("name")
    ) or None


async def _enrich_with_nametrace(investigation: Investigation, store) -> None:
    from collectors.nametrace_collector import fetch_nametrace

    name_to_hits: dict[str, list] = {}
    for result in investigation.results:
        for hit in result.profile_hits:
            fullname = _extract_fullname(hit)
            if not fullname:
                continue
            first_name = fullname.split()[0][:50].lower()
            name_to_hits.setdefault(first_name, []).append(hit)

    if not name_to_hits:
        return

    store.emit(investigation.id, SSEEvent(event="collector_started", data={"collector": "nametrace_enrichment"}))

    async def _run(first_name: str, hits: list) -> None:
        try:
            data = await fetch_nametrace(first_name)
            for hit in hits:
                hit.metadata["nametrace"] = data
        except Exception:
            pass

    await asyncio.gather(*[
        _run(first_name, hits)
        for first_name, hits in name_to_hits.items()
    ], return_exceptions=True)

    store.save(investigation)
    store.emit(investigation.id, SSEEvent(event="collector_done", data={"collector": "nametrace_enrichment"}))


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
