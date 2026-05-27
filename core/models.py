from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
import uuid


class InvestigationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CollectorStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class InvestigationTarget(BaseModel):
    username: str | None = None
    email: str | None = None
    discord_id: str | None = None
    twitter_handle: str | None = None
    reddit_username: str | None = None
    image_path: str | None = None

    def has_username(self) -> bool:
        return bool(self.username)

    def has_email(self) -> bool:
        return bool(self.email)

    def label(self) -> str:
        parts = filter(None, [
            self.username,
            self.email,
            self.twitter_handle,
            f"discord:{self.discord_id}" if self.discord_id else None,
            f"reddit:{self.reddit_username}" if self.reddit_username else None,
        ])
        return " | ".join(parts) or "unknown"


class ProfileHit(BaseModel):
    platform: str
    url: str
    username: str
    exists: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmailRegistration(BaseModel):
    site: str
    registered: bool
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmailBreach(BaseModel):
    source: str
    date: str | None = None
    records: int | None = None
    fields: list[str] = Field(default_factory=list)
    description: str | None = None


class ExifData(BaseModel):
    file_path: str
    tags: dict[str, str] = Field(default_factory=dict)
    gps_lat: float | None = None
    gps_lon: float | None = None
    camera_make: str | None = None
    camera_model: str | None = None
    datetime_original: str | None = None


class ReverseImageMatch(BaseModel):
    similarity: float
    thumbnail_url: str | None = None
    source_url: str | None = None
    title: str | None = None
    author: str | None = None
    site: str | None = None


class CollectorResult(BaseModel):
    collector: str
    status: CollectorStatus = CollectorStatus.PENDING
    profile_hits: list[ProfileHit] = Field(default_factory=list)
    email_registrations: list[EmailRegistration] = Field(default_factory=list)
    email_breaches: list[EmailBreach] = Field(default_factory=list)
    exif_data: ExifData | None = None
    image_matches: list[ReverseImageMatch] = Field(default_factory=list)
    raw_data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    duration_seconds: float | None = None


class GraphNode(BaseModel):
    id: str
    label: str
    type: str  # "person", "username", "email", "platform_profile", "breach", "image"
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str
    weight: float = 1.0


class IdentityGraph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class Investigation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    target: InvestigationTarget
    status: InvestigationStatus = InvestigationStatus.PENDING
    collectors: dict[str, CollectorStatus] = Field(default_factory=dict)
    results: list[CollectorResult] = Field(default_factory=list)
    graph: IdentityGraph | None = None
    ai_report: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None

    def summary(self) -> dict[str, Any]:
        total_hits = sum(len(r.profile_hits) for r in self.results)
        total_sites = sum(
            len([e for e in r.email_registrations if e.registered])
            for r in self.results
        )
        total_breaches = sum(len(r.email_breaches) for r in self.results)
        return {
            "profile_hits": total_hits,
            "email_registrations": total_sites,
            "email_breaches": total_breaches,
            "collectors_run": len([s for s in self.collectors.values() if s == CollectorStatus.SUCCESS]),
            "collectors_total": len(self.collectors),
        }


class InvestigationCreateRequest(BaseModel):
    username: str | None = None
    email: str | None = None
    discord_id: str | None = None
    twitter_handle: str | None = None
    reddit_username: str | None = None


class SSEEvent(BaseModel):
    event: str
    data: Any
