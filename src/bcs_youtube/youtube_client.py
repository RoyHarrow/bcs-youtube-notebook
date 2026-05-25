from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urlparse

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


@dataclass(frozen=True)
class YouTubeVideo:
    video_id: str
    title: str
    description: str
    channel_title: str
    channel_id: str
    channel_handle: str
    published_at: datetime
    thumbnail_url: str
    view_count: int
    like_count: int


class BaseYouTubeClient(ABC):
    @abstractmethod
    def search_video_ids(self, query: str, max_results: int = 50) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def fetch_videos(self, video_ids: Iterable[str]) -> list[YouTubeVideo]:
        raise NotImplementedError


class ApiYouTubeClient(BaseYouTubeClient):
    def __init__(self, api_key: str) -> None:
        self._service = build("youtube", "v3", developerKey=api_key)

    def search_video_ids(self, query: str, max_results: int = 50) -> list[str]:
        video_ids: list[str] = []
        next_page_token = None

        while len(video_ids) < max_results:
            batch_size = min(50, max_results - len(video_ids))
            request = self._service.search().list(
                part="snippet",
                q=query,
                type="video",
                maxResults=batch_size,
                order="relevance",
                pageToken=next_page_token,
            )
            response = self._safe_execute(request)
            items = response.get("items", [])

            for item in items:
                video_id = item.get("id", {}).get("videoId")
                if video_id:
                    video_ids.append(video_id)

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        return video_ids

    def fetch_videos(self, video_ids: Iterable[str]) -> list[YouTubeVideo]:
        ids = [v for v in video_ids if v]
        if not ids:
            return []

        results: list[YouTubeVideo] = []
        for i in range(0, len(ids), 50):
            chunk = ids[i : i + 50]
            request = self._service.videos().list(
                part="snippet,statistics",
                id=",".join(chunk),
                maxResults=50,
            )
            response = self._safe_execute(request)

            for item in response.get("items", []):
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})

                published_raw = snippet.get("publishedAt", "")
                published_at = datetime.fromisoformat(
                    published_raw.replace("Z", "+00:00")
                ).astimezone(timezone.utc)

                thumbs = snippet.get("thumbnails", {})
                thumb_url = (
                    thumbs.get("high", {}).get("url")
                    or thumbs.get("medium", {}).get("url")
                    or thumbs.get("default", {}).get("url")
                    or ""
                )

                results.append(
                    YouTubeVideo(
                        video_id=item.get("id", ""),
                        title=snippet.get("title", ""),
                        description=snippet.get("description", ""),
                        channel_title=snippet.get("channelTitle", ""),
                        channel_id=snippet.get("channelId", ""),
                        channel_handle="",
                        published_at=published_at,
                        thumbnail_url=thumb_url,
                        view_count=int(stats.get("viewCount", 0)),
                        like_count=int(stats.get("likeCount", 0)),
                    )
                )

        return results

    @staticmethod
    def _safe_execute(request: object) -> dict:
        try:
            return request.execute()
        except HttpError as exc:
            raise RuntimeError(f"YouTube API request failed: {exc}") from exc


class PublicYouTubeClient(BaseYouTubeClient):
    """Public-data client using yt-dlp search and metadata extraction (no API key)."""

    def __init__(self) -> None:
        self._ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
            "noplaylist": True,
        }

    def search_video_ids(self, query: str, max_results: int = 50) -> list[str]:
        search_term = f"ytsearch{max_results}:{query}"
        with YoutubeDL(self._ydl_opts) as ydl:
            info = ydl.extract_info(search_term, download=False) or {}

        ids: list[str] = []
        for entry in info.get("entries", []) or []:
            video_id = (entry or {}).get("id")
            if video_id:
                ids.append(str(video_id))
        return ids

    def fetch_videos(self, video_ids: Iterable[str]) -> list[YouTubeVideo]:
        ids = [v for v in video_ids if v]
        if not ids:
            return []

        results: list[YouTubeVideo] = []
        with YoutubeDL({**self._ydl_opts, "extract_flat": False}) as ydl:
            for video_id in ids:
                try:
                    info = ydl.extract_info(
                        f"https://www.youtube.com/watch?v={video_id}", download=False
                    ) or {}
                except DownloadError:
                    # Some search results can point to unavailable videos; skip them.
                    continue

                upload_date = str(info.get("upload_date") or "")
                published_at = self._parse_upload_date(upload_date)
                if not published_at:
                    # Keep invalid dates from crashing a batch; skip malformed records.
                    continue

                results.append(
                    YouTubeVideo(
                        video_id=str(info.get("id") or video_id),
                        title=str(info.get("title") or ""),
                        description=str(info.get("description") or ""),
                        channel_title=str(info.get("channel") or ""),
                        channel_id=str(info.get("channel_id") or ""),
                        channel_handle=str(info.get("uploader_id") or info.get("channel_handle") or ""),
                        published_at=published_at,
                        thumbnail_url=str(info.get("thumbnail") or ""),
                        view_count=int(info.get("view_count") or 0),
                        like_count=int(info.get("like_count") or 0),
                    )
                )

        return results

    @staticmethod
    def _parse_upload_date(upload_date: str) -> datetime | None:
        if len(upload_date) != 8 or not upload_date.isdigit():
            return None
        try:
            dt = datetime.strptime(upload_date, "%Y%m%d")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def create_youtube_client(api_key: str | None) -> BaseYouTubeClient:
    if api_key:
        return ApiYouTubeClient(api_key=api_key)
    return PublicYouTubeClient()


def _extract_publisher_handle(publisher: str) -> str | None:
    raw = publisher.strip()
    if not raw:
        return None

    if raw.startswith("@"):
        return raw[1:]

    if "youtube.com" not in raw.lower():
        return None

    url = raw if "://" in raw else f"https://{raw}"
    parsed = urlparse(url)
    path = (parsed.path or "").strip("/")
    if path.startswith("@") and len(path) > 1:
        return path[1:]
    return None


def search_video_ids_for_publisher(publisher: str, max_results: int = 50) -> list[str]:
    """Return recent video IDs for a YouTube @handle URL or @handle string."""
    handle = _extract_publisher_handle(publisher)
    if not handle:
        return []

    channel_url = f"https://www.youtube.com/@{handle}/videos"
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "noplaylist": False,
    }

    with YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(channel_url, download=False) or {}
        except DownloadError:
            return []

    ids: list[str] = []
    for entry in info.get("entries", []) or []:
        video_id = (entry or {}).get("id")
        if video_id:
            ids.append(str(video_id))
        if len(ids) >= max_results:
            break
    return ids
