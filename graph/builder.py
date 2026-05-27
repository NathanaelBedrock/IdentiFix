from __future__ import annotations
from core.models import Investigation, IdentityGraph, GraphNode, GraphEdge


def build_graph(investigation: Investigation) -> IdentityGraph:
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    def add_node(node_id: str, label: str, node_type: str, metadata: dict | None = None) -> str:
        if node_id not in nodes:
            nodes[node_id] = GraphNode(
                id=node_id,
                label=label,
                type=node_type,
                metadata=metadata or {},
            )
        return node_id

    def add_edge(src: str, dst: str, label: str, weight: float = 1.0) -> None:
        edges.append(GraphEdge(source=src, target=dst, label=label, weight=weight))

    # Root identity node
    root_id = f"identity:{investigation.id}"
    add_node(root_id, investigation.target.label(), "person")

    target = investigation.target

    # Username node
    if target.username:
        uid = f"username:{target.username}"
        add_node(uid, f"@{target.username}", "username")
        add_edge(root_id, uid, "uses_username")

    # Email node
    if target.email:
        eid = f"email:{target.email}"
        add_node(eid, target.email, "email")
        add_edge(root_id, eid, "has_email")

    # Social handle nodes
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

    # Profile hits from collectors
    seen_platforms: dict[str, str] = {}
    for result in investigation.results:
        for hit in result.profile_hits:
            platform_key = f"profile:{hit.platform.lower()}:{hit.username.lower()}"
            if platform_key not in seen_platforms:
                nid = add_node(platform_key, f"{hit.platform}", "platform_profile",
                               {"url": hit.url, "platform": hit.platform, **hit.metadata})
                seen_platforms[platform_key] = nid
                anchor = f"username:{hit.username}" if hit.username in (target.username or "") else root_id
                add_edge(anchor, platform_key, "found_on",
                         weight=2.0 if hit.metadata.get("confirmed_by_multiple") else 1.0)

        # Email registrations
        for reg in result.email_registrations:
            if not reg.registered:
                continue
            reg_id = f"reg:{reg.site}"
            add_node(reg_id, reg.site, "platform_profile",
                     {"url": reg.url or "", "platform": reg.site})
            email_anchor = f"email:{target.email}" if target.email else root_id
            add_edge(email_anchor, reg_id, "registered_on")

        # Breaches
        for breach in result.email_breaches:
            breach_id = f"breach:{breach.source}"
            add_node(breach_id, breach.source, "breach",
                     {"date": breach.date or "", "records": breach.records or 0})
            email_anchor = f"email:{target.email}" if target.email else root_id
            add_edge(email_anchor, breach_id, "exposed_in", weight=1.5)

    return IdentityGraph(nodes=list(nodes.values()), edges=edges)
