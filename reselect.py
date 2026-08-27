import json
from pathlib import Path

from main import reselect_serial
from modules.db import PlaylistDB, ReelDB


def _load_config():
    path = Path("config.json")
    if not path.is_file():
        raise SystemExit("config.json was not found in the project directory.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"config.json is invalid: {exc}") from exc


def main():
    cfg = _load_config()
    raw = input("Enter final reel serial number: ").strip()
    if not raw.isdigit():
        raise SystemExit("Serial must be a number.")

    serial = int(raw)
    with PlaylistDB(cfg["playlist_db_path"]) as playlist_db, ReelDB(cfg["reels_db_path"]) as reel_db:
        result = reselect_serial(serial, reel_db, playlist_db, cfg)
        if result == "skip":
            print("Reselection skipped.")
        elif result == "quit":
            print("Reselection cancelled.")


if __name__ == "__main__":
    main()
