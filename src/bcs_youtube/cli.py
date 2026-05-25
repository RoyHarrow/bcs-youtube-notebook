from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from tabulate import tabulate

from .analytics import (
    add_estimated_views_per_month,
    filter_by_publisher,
    filter_by_query_terms,
    filter_meeting_videos,
    sort_for_display,
    videos_to_dataframe,
)
from .config import load_config
from .storage import add_monthly_growth_from_snapshots, append_snapshot, load_snapshots
from .youtube_client import create_youtube_client, search_video_ids_for_publisher


def run(query: str, max_results: int, export_csv: bool, publisher: str | None = None) -> None:
    config = load_config()
    client = create_youtube_client(config.api_key)

    if config.api_key:
        print("Using YouTube Data API backend.")
    else:
        print("Using public no-key backend (yt-dlp).")

    if publisher and not config.api_key:
        video_ids = search_video_ids_for_publisher(publisher=publisher, max_results=max_results)
        if not video_ids:
            video_ids = client.search_video_ids(query=query, max_results=max_results)
    else:
        video_ids = client.search_video_ids(query=query, max_results=max_results)
    videos = client.fetch_videos(video_ids)

    df = videos_to_dataframe(videos)
    df = filter_by_query_terms(df, query=query)
    df = filter_by_publisher(df, publisher=publisher)
    if not publisher:
        df = filter_meeting_videos(df)
    df = add_estimated_views_per_month(df)

    snapshots = load_snapshots(config.snapshot_csv)
    df = add_monthly_growth_from_snapshots(df, snapshots)
    df = sort_for_display(df)

    append_snapshot(config.snapshot_csv, query=query, df=df)

    display_cols = [
        "video_id",
        "title",
        "published_at",
        "view_count",
        "like_count",
        "estimated_views_per_month",
        "tracked_views_growth_per_month",
    ]
    show = df[display_cols].copy() if not df.empty else df

    print("\nVideo summary\n")
    if show.empty:
        print("No matching meeting videos found.")
    else:
        print(tabulate(show, headers="keys", tablefmt="github", showindex=False))

    if export_csv and not df.empty:
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        out_file = Path(config.exports_dir) / f"youtube_analysis_{stamp}.csv"
        df.to_csv(out_file, index=False)
        print(f"\nExported: {out_file}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BCS YouTube video analytics")
    parser.add_argument("--query", required=True, help="YouTube search query")
    parser.add_argument(
        "--publisher",
        default=None,
        help="Optional publisher filter by channel title, @handle, or URL",
    )
    parser.add_argument("--max-results", type=int, default=50, help="Maximum videos to search")
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Disable CSV export",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    run(
        query=args.query,
        max_results=args.max_results,
        export_csv=not args.no_export,
        publisher=args.publisher,
    )


if __name__ == "__main__":
    main()
