from __future__ import annotations
from core.models import Investigation, IdentityGraph, GraphNode, GraphEdge

PLATFORM_CATEGORY: dict[str, str] = {
    # Social
    "twitter": "Social", "x": "Social", "instagram": "Social", "reddit": "Social",
    "bluesky": "Social", "mastodon": "Social", "mstdn.social": "Social",
    "tumblr": "Social", "flipboard": "Social", "telegram": "Social",
    "discord": "Social", "disqus": "Social", "substack": "Social",
    "medium": "Social", "wattpad": "Social", "wikipedia": "Social",
    # Developer
    "github": "Developer", "gitlab": "Developer", "docker hub": "Developer",
    "launchpad": "Developer", "crowdin": "Developer", "slides": "Developer",
    # Gaming
    "minecraft": "Gaming", "star citizen": "Gaming", "jeuxvideo": "Gaming",
    "jeuxvideo.com": "Gaming",
    # Creative
    "soundcloud": "Creative", "freesound": "Creative", "audiojungle": "Creative",
    "themforest": "Creative", "themeforest": "Creative", "imgur": "Creative",
    # Other
    "duolingo": "Other",
}

CATEGORY_ORDER = ["Social", "Developer", "Gaming", "Creative", "Other"]


def _category(platform: str) -> str:
    return PLATFORM_CATEGORY.get(platform.lower(), "Other")


def build_graph(investigation: Investigation) -> IdentityGraph:
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    def add_node(node_id: str, label: str, node_type: str, metadata: dict | None = None) -> str:
        if node_id not in nodes:
            nodes[node_id] = GraphNode(id=node_id, label=label, type=node_type, metadata=metadata or {})
        return node_id

    def add_edge(src: str, dst: str, label: str, weight: float = 1.0) -> None:
        edges.append(GraphEdge(source=src, target=dst, label=label, weight=weight))

    root_id = f"identity:{investigation.id}"
    add_node(root_id, investigation.target.label(), "person")

    target = investigation.target

    if target.username:
        uid = f"username:{target.username}"
        add_node(uid, f"@{target.username}", "username")
        add_edge(root_id, uid, "uses_username")

    if target.email:
        eid = f"email:{target.email}"
        add_node(eid, target.email, "email")
        add_edge(root_id, eid, "has_email")

    if target.discord_id:
        did = f"discord:{target.discord_id}"
        add_node(did, f"Discord:{target.discord_id}", "platform_profile",
                 {"platform": "Discord", "url": f"https://discord.com/users/{target.discord_id}"})
        add_edge(root_id, did, "profile_on")

    if target.twitter_handle:
        tid = f"twitter:{target.twitter_handle}"
        add_node(tid, f"@{target.twitter_handle}", "platform_profile",
                 {"platform": "Twitter/X", "url": f"https://twitter.com/{target.twitter_handle}"})
        add_edge(root_id, tid, "profile_on")

    if target.reddit_username:
        rid = f"reddit:{target.reddit_username}"
        add_node(rid, f"u/{target.reddit_username}", "platform_profile",
                 {"platform": "Reddit", "url": f"https://reddit.com/u/{target.reddit_username}"})
        add_edge(root_id, rid, "profile_on")

    # ── Confirmed profile hits grouped by category ───────────────────────────
    anchor = f"username:{target.username}" if target.username else root_id

    seen_profiles: dict[str, str] = {}  # platform_key -> node_id
    category_hits: dict[str, list[tuple[str, dict]]] = {}  # category -> [(platform_key, hit)]

    for result in investigation.results:
        for hit in result.profile_hits:
            if not hit.metadata.get("confirmed_by_multiple"):
                continue
            platform_key = f"profile:{hit.platform.lower()}:{hit.username.lower()}"
            if platform_key in seen_profiles:
                continue
            seen_profiles[platform_key] = hit.platform
            cat = _category(hit.platform)
            category_hits.setdefault(cat, []).append((platform_key, hit))

    for cat in CATEGORY_ORDER:
        hits = category_hits.get(cat, [])
        if not hits:
            continue

        cat_id = f"category:{cat.lower()}"
        add_node(cat_id, cat, "category")
        add_edge(anchor, cat_id, "has_profiles", weight=1.0)

        for platform_key, hit in hits:
            confirmation_count = hit.metadata.get("confirmation_count", 1)
            nid = add_node(
                platform_key,
                hit.platform,
                "platform_profile",
                {"url": hit.url, "platform": hit.platform,
                 "confirmation_count": confirmation_count, **hit.metadata},
            )
            add_edge(cat_id, nid, "found_on", weight=float(confirmation_count))

    # ── Email registrations ──────────────────────────────────────────────────
    for result in investigation.results:
        for reg in result.email_registrations:
            if not reg.registered:
                continue
            reg_id = f"reg:{reg.site}"
            add_node(reg_id, reg.site, "platform_profile",
                     {"url": reg.url or "", "platform": reg.site})
            email_anchor = f"email:{target.email}" if target.email else root_id
            add_edge(email_anchor, reg_id, "registered_on")

        for breach in result.email_breaches:
            breach_id = f"breach:{breach.source}"
            add_node(breach_id, breach.source, "breach",
                     {"date": breach.date or "", "records": breach.records or 0})
            email_anchor = f"email:{target.email}" if target.email else root_id
            add_edge(email_anchor, breach_id, "exposed_in", weight=1.5)

    return IdentityGraph(nodes=list(nodes.values()), edges=edges)
