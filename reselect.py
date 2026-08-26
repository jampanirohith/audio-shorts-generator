import json
from pathlib import Path

from modules.db import DB
from modules.youtube import search, choose
from main import process_retry


def main():
    cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))
    db = DB(cfg["db_path"])

    raw = input("Enter final reel serial number: ").strip()
    if not raw.isdigit():
        raise SystemExit("Serial must be a number.")
    serial = int(raw)

    row = db.get(serial)
    if not row:
        raise SystemExit(f"Serial {serial} does not exist.")

    original = json.loads(row["original_json"])
    print("\n" + "=" * 78)
    print(f"RESELECTING FINAL REEL [{serial:04d}]")
    print("=" * 78)
    print(f"Original playlist title: {original.get('title','')}")
    print(f"Original playlist URL:   {original.get('url','')}")
    print(f"Current chosen video:    {row['selected_video_title']}")
    print(f"Current chosen URL:      {row['selected_video_url']}")

    results = search(original.get("title", ""), cfg.get("top_youtube_results", 10))

    manual_cfg = dict(cfg)
    manual_cfg["automation"] = dict(cfg.get("automation", {}))
    manual_cfg["automation"]["auto_youtube_selection"] = False
    selected = choose(results, original.get("title", ""), manual_cfg)

    if selected in ("skip", "quit"):
        print("Reselection cancelled.")
        return

    existing = db.cx.execute(
        "SELECT serial,status FROM queue WHERE selected_video_id=? AND serial<>?",
        (selected["id"], serial),
    ).fetchone()
    if existing and existing["status"] == "FINISHED":
        raise SystemExit(
            f"That YouTube video is already the finished reference for serial "
            f"{existing['serial']:04d}. Choose a different result."
        )

    db.set_selected(serial, original, selected)
    db.set_status(serial, "PENDING", None)
    print(f"\nRESELECTED VIDEO FOR SERIAL [{serial:04d}]")
    print(f"Title: {selected['title']}")
    print(f"URL:   {selected['url']}", flush=True)

    process_retry(original, selected, serial, db, cfg)


if __name__ == "__main__":
    main()
