from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SNAPSHOT_COLUMNS = [
    "snapshot_at",
    "query",
    "video_id",
    "title",
    "channel_title",
    "published_at",
    "view_count",
    "like_count",
]


def append_snapshot(snapshot_csv: Path, query: str, df: pd.DataFrame) -> None:
    snapshot_at = datetime.now(timezone.utc)
    to_store = df.copy()
    to_store["snapshot_at"] = snapshot_at
    to_store["query"] = query

    available_cols = [col for col in SNAPSHOT_COLUMNS if col in to_store.columns]
    to_store = to_store[available_cols]

    exists = snapshot_csv.exists()
    to_store.to_csv(snapshot_csv, mode="a", header=not exists, index=False)


def load_snapshots(snapshot_csv: Path) -> pd.DataFrame:
    if not snapshot_csv.exists():
        return pd.DataFrame(columns=SNAPSHOT_COLUMNS)

    df = pd.read_csv(snapshot_csv)
    if df.empty:
        return pd.DataFrame(columns=SNAPSHOT_COLUMNS)

    df["snapshot_at"] = pd.to_datetime(df["snapshot_at"], utc=True, errors="coerce")
    df["published_at"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    df["view_count"] = pd.to_numeric(df["view_count"], errors="coerce").fillna(0).astype(int)
    df["like_count"] = pd.to_numeric(df["like_count"], errors="coerce").fillna(0).astype(int)
    return df


def add_monthly_growth_from_snapshots(df_current: pd.DataFrame, snapshots: pd.DataFrame) -> pd.DataFrame:
    out = df_current.copy()
    if out.empty:
        out["tracked_views_growth_per_month"] = []
        return out

    if snapshots.empty:
        out["tracked_views_growth_per_month"] = pd.NA
        return out

    agg = snapshots.sort_values("snapshot_at").groupby("video_id").agg(
        first_view=("view_count", "first"),
        first_seen=("snapshot_at", "first"),
        last_view=("view_count", "last"),
        last_seen=("snapshot_at", "last"),
    )

    days = (agg["last_seen"] - agg["first_seen"]).dt.days.clip(lower=1)
    months = (days / 30.4375).clip(lower=0.1)
    agg["tracked_views_growth_per_month"] = ((agg["last_view"] - agg["first_view"]) / months).round(2)

    merged = out.merge(
        agg[["tracked_views_growth_per_month"]],
        how="left",
        left_on="video_id",
        right_index=True,
    )
    return merged
