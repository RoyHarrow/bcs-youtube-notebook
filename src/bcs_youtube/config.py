from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    api_key: str | None
    workspace_root: Path
    snapshot_csv: Path
    exports_dir: Path


def load_config() -> AppConfig:
    load_dotenv()

    raw_api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    api_key = raw_api_key or None

    workspace_root = Path(__file__).resolve().parents[2]
    snapshot_csv = workspace_root / "data" / "snapshots" / "video_snapshots.csv"
    exports_dir = workspace_root / "data" / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    snapshot_csv.parent.mkdir(parents=True, exist_ok=True)

    return AppConfig(
        api_key=api_key,
        workspace_root=workspace_root,
        snapshot_csv=snapshot_csv,
        exports_dir=exports_dir,
    )
