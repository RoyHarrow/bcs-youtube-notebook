from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from urllib.parse import urlparse

import pandas as pd

from .youtube_client import YouTubeVideo

MEETING_KEYWORDS = (
    "meeting",
    "session",
    "webinar",
    "talk",
    "group",
    "bcs",
    "devsecops",
)

GENERIC_TOKENS = {
    "a",
    "an",
    "and",
    "for",
    "from",
    "group",
    "groups",
    "in",
    "member",
    "members",
    "of",
    "on",
    "or",
    "session",
    "talk",
    "the",
    "to",
    "webinar",
}

PUBLISHER_GENERIC_TOKENS = {
    "a",
    "an",
    "and",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
}


def _tokenize(text: str) -> list[str]:
    parts = [p.strip().lower() for p in text.replace("-", " ").split()]
    tokens: list[str] = []
    for token in parts:
        normalized = "".join(ch for ch in token if ch.isalnum())
        if not normalized:
            continue
        if normalized.endswith("s") and len(normalized) > 4:
            normalized = normalized[:-1]
        tokens.append(normalized)
    return tokens


def _slug(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def _extract_youtube_handle(publisher: str) -> str | None:
    raw = publisher.strip()
    if not raw:
        return None

    if raw.startswith("@"):
        return _slug(raw[1:]) or None

    if "youtube.com" not in raw.lower():
        return None

    url = raw if "://" in raw else f"https://{raw}"
    parsed = urlparse(url)
    path = (parsed.path or "").strip("/")
    if path.startswith("@") and len(path) > 1:
        return _slug(path[1:]) or None
    return None


def videos_to_dataframe(videos: list[YouTubeVideo]) -> pd.DataFrame:
    rows: list[dict] = []
    for video in videos:
        row = asdict(video)
        row["published_at"] = video.published_at
        rows.append(row)

    if not rows:
        return pd.DataFrame(
            columns=[
                "video_id",
                "title",
                "description",
                "channel_title",
                "channel_id",
                "channel_handle",
                "published_at",
                "thumbnail_url",
                "view_count",
                "like_count",
            ]
        )

    df = pd.DataFrame(rows)
    df["published_at"] = pd.to_datetime(df["published_at"], utc=True)
    df["view_count"] = pd.to_numeric(df["view_count"], errors="coerce").fillna(0).astype(int)
    df["like_count"] = pd.to_numeric(df["like_count"], errors="coerce").fillna(0).astype(int)
    return df


def filter_meeting_videos(df: pd.DataFrame, keywords: tuple[str, ...] = MEETING_KEYWORDS) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    pattern = "|".join(keywords)
    title_match = df["title"].str.contains(pattern, case=False, na=False, regex=True)
    desc_match = df["description"].str.contains(pattern, case=False, na=False, regex=True)
    return df[title_match | desc_match].copy()


def filter_by_publisher(df: pd.DataFrame, publisher: str | None) -> pd.DataFrame:
    """Filter videos by publisher text, handle, or YouTube channel URL."""
    if df.empty or not publisher:
        return df.copy()

    handle = _extract_youtube_handle(publisher)
    if handle:
        by_title_slug = df["channel_title"].fillna("").map(_slug).eq(handle)
        if "channel_handle" in df.columns:
            by_handle = (
                df["channel_handle"].fillna("").map(lambda v: _slug(str(v).lstrip("@"))).eq(handle)
            )
            return df[by_title_slug | by_handle].copy()
        return df[by_title_slug].copy()

    publisher_tokens = [t for t in _tokenize(publisher) if t not in PUBLISHER_GENERIC_TOKENS]
    if not publisher_tokens:
        return df.copy()

    channel_text = df["channel_title"].fillna("").str.lower().str.replace(r"[^a-z0-9 ]+", " ", regex=True)
    match = pd.Series(True, index=df.index)
    for token in publisher_tokens:
        match = match & channel_text.str.contains(rf"\b{token}\b", case=False, na=False, regex=True)
    return df[match].copy()


def filter_by_query_terms(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Keep rows that contain meaningful query tokens in title/description/channel."""
    if df.empty:
        return df.copy()

    query_tokens = [t for t in _tokenize(query) if t not in GENERIC_TOKENS]
    if not query_tokens:
        return df.copy()

    searchable = (
        df["title"].fillna("")
        + " "
        + df["description"].fillna("")
        + " "
        + df["channel_title"].fillna("")
    ).str.lower()

    pattern = "|".join(pd.Series(query_tokens).map(lambda t: rf"\b{t}\b").tolist())
    match = searchable.str.contains(pattern, case=False, na=False, regex=True)
    return df[match].copy()


def add_estimated_views_per_month(df: pd.DataFrame, now: datetime | None = None) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        out["months_since_publish"] = []
        out["estimated_views_per_month"] = []
        return out

    now_utc = now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)
    days_since_publish = (now_utc - out["published_at"]).dt.days.clip(lower=1)
    months_since_publish = (days_since_publish / 30.4375).clip(lower=0.1)
    out["months_since_publish"] = months_since_publish
    out["estimated_views_per_month"] = (out["view_count"] / months_since_publish).round(2)
    return out


def sort_for_display(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    return df.sort_values(by=["view_count", "like_count"], ascending=[False, False]).reset_index(drop=True)
