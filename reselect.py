import json
from pathlib import Path

from main import process_selected
from modules.db import DB
from modules.youtube import choose, search


def _load_config():
    return json.loads(Path("config.json").read_text(encoding="utf-8"))


def main():
    cfg = _load_config()
    db = DB(cfg["db_path"])

    try:
        raw = input("Enter final reel serial number: ").strip()
        if not raw.isdigit():
            raise SystemExit("Serial must be a number.")

        serial = int(raw)
        row = db.get(serial)
        if not row:
            raise SystemExit(f"Serial {serial} does not exist.")

        original = json.loads(row["original_json"])
        if not original.get("title"):
            raise SystemExit(f"Serial {serial} has no original playlist title.")

        print("\n" + "=" * 78)
        print(f"RESELECTING FINAL REEL [{serial:04d}]")
        print("=" * 78)
        print(f"Original playlist title: {original.get('title', '')}")
        print(f"Original playlist URL:   {original.get('url', '')}")
        print(f"Current chosen video:    {row['selected_video_title']}")
        print(f"Current chosen URL:      {row['selected_video_url']}")

        print("\nSearching YouTube ...", flush=True)
        results = search(
            original["title"],
            cfg.get("top_youtube_results", 10),
        )

        selected, _ = choose(
            results,
            original["title"],
            cfg,
            force_manual=True,
        )

        if isinstance(selected, str):
            if selected == "skip":
                return
            if selected == "quit":
                return

        duplicate_serial = db.selected_exists(
            selected["id"],
            exclude_serial=serial,
        )
        if duplicate_serial is not None:
            reason = (
                f"That YouTube video is already FINISHED under serial "
                f"{duplicate_serial:04d}. Choose another result."
            )
            db.set_status(serial, "ERROR", reason)
            db.event(serial, "ERROR", reason)
            raise SystemExit(reason)

        print(f"\nRESELECTED VIDEO FOR SERIAL [{serial:04d}]")
        print(f"Title: {selected['title']}")
        print(f"URL:   {selected['url']}", flush=True)

        # The permanent serial stays unchanged. The chosen video becomes the
        # new primary reference for this reel.
        process_selected(
            original,
            selected,
            serial,
            db,
            cfg,
            search_results=results,
            ranking=[],
            mode="manual_reselection",
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
