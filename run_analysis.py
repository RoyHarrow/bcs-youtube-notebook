import sys
from pathlib import Path

workspace_root = Path(__file__).resolve().parent
src_path = workspace_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from bcs_youtube.cli import main


if __name__ == "__main__":
    main()
