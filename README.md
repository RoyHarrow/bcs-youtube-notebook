# BCS YouTube Video Analyzer -  Jupiter NoteBook Version

Python toolkit for searching YouTube videos and analyzing:
- Total views
- Likes
- Estimated views per month
- Tracked views growth per month from local snapshots

## Why two monthly metrics?
YouTube public Data API does not expose full historical monthly view totals for all public videos.
This app therefore provides:
1. `estimated_views_per_month`: `total_views / months_since_publish`.
2. `tracked_views_growth_per_month`: calculated from snapshots collected over time by this app.

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Optional: create `.env` from `.env.example` and set:

```env
YOUTUBE_API_KEY=your_key_here
```

You can create a key in Google Cloud Console for YouTube Data API v3.

If you do not have an API key, the app automatically falls back to a public-data backend (yt-dlp) that uses only publicly available metadata.

## CLI usage

Windows cmd:

```cmd
set PYTHONPATH=src
python -m bcs_youtube.cli --query "DevSecOps" --publisher "BCS Member Groups" --max-results 50
```

Outputs:
- terminal summary table
- snapshot appended to `data/snapshots/video_snapshots.csv`
- CSV export in `data/exports/` (unless `--no-export` is used)

Backend mode:
- With `YOUTUBE_API_KEY`: uses YouTube Data API.
- Without `YOUTUBE_API_KEY`: uses public no-key metadata backend.

## Notebook usage

Open `notebooks/bcs_youtube_analysis.ipynb` and run cells top-to-bottom.

## Notes on filtering

The app applies a meeting-oriented keyword filter on title/description.
You can optionally filter by publisher/channel title using `--publisher`.
You can tune keywords in `src/bcs_youtube/analytics.py`.
