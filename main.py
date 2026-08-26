import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from modules.db import DB
from modules.youtube import playlist, search, choose, download, info
from modules.hooks import detect
from modules.video import render


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def print_header(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78, flush=True)


def process(playlist_entry, db, cfg):
    """Process one playlist entry. The playlist itself never owns the permanent serial."""
    original = {
        "playlist_id": playlist_entry.get("id"),
        "title": playlist_entry.get("title", ""),
        "url": playlist_entry.get("url", ""),
        "playlist_index": playlist_entry.get("playlist_index"),
    }

    print_header(f"CURRENT PLAYLIST ENTRY: {original['title']}")
    print(f"Original playlist URL: {original['url']}", flush=True)

    try:
        results = search(original["title"], cfg.get("top_youtube_results", 10))
        selected = choose(results, original["title"], cfg)

        if selected == "skip":
            db.record_skip(original, "User skipped YouTube selection")
            print("SKIPPED without errors.", flush=True)
            return "skip"

        if selected == "quit":
            print("Quit requested.", flush=True)
            return "quit"

        # A permanent serial belongs to the chosen YouTube video, not to the
        # playlist position. Re-selecting the same video therefore keeps the
        # same serial.
        serial = db.get_or_create_serial(selected)
        row = db.get(serial)

        print(f"\nCHOSEN YOUTUBE VIDEO [{serial:04d}]")
        print(f"Title: {selected['title']}")
        print(f"URL:   {selected['url']}", flush=True)

        if row["status"] == "FINISHED":
            print("Already FINISHED in database; skipping duplicate processing.", flush=True)
            return "done"

        if db.selected_exists(selected["id"], exclude_serial=serial):
            print("Chosen YouTube video already belongs to a finished serial; skipping.", flush=True)
            db.set_status(serial, "SKIPPED", "Chosen YouTube video already finished under another serial.")
            return "skip"

        db.set_selected(serial, original, selected)
        db.set_status(serial, "PROCESSING", None)

        temp = Path(cfg["temp_dir"])
        temp.mkdir(parents=True, exist_ok=True)

        # All working files are directly inside temp/. No per-song temp folders.
        # yt-dlp progress is intentionally suppressed; only meaningful pipeline
        # stages are printed to the terminal.
        print("\nDownloading selected YouTube video to temp/ ...", flush=True)
        yfile = download(selected["url"], temp)

        print("Reading complete YouTube metadata ...", flush=True)
        selected_info = info(selected["url"])

        print("Analysing audio and selecting the single final hook ...", flush=True)
        hook = detect(yfile, temp, cfg)

        final_dir = Path(cfg["reels_finished_dir"])
        final_dir.mkdir(parents=True, exist_ok=True)
        final = final_dir / f"{serial:04d}_{selected['id']}_reel.mp4"
        json_path = final_dir / f"{serial:04d}_{selected['id']}_reel.json"

        print("Rendering final 9:16 reel ...", flush=True)
        render_result = render(
            yfile,
            hook["start"],
            hook["end"],
            final,
            cfg,
        )

        # Capture file information before temp is deleted. This JSON is the
        # permanent handoff document for later editing/8D/upload workflows.
        video_stat = final.stat()
        metadata = {
            "schema_version": "2.0",
            "generated_at_utc": utc_now(),
            "serial": serial,
            "status": "FINISHED",
            "original_playlist_song": original,
            "chosen_video": selected,
            "chosen_video_ytdlp_metadata": selected_info,
            "youtube_search": {
                "query": original["title"],
                "result_count": len(results),
                "results": results,
                "ranking": db.last_ranking,
            },
            "hook": hook,
            "render": render_result,
            "final_reel": {
                "path": str(final.resolve()),
                "json_path": str(json_path.resolve()),
                "filename": final.name,
                "size_bytes": video_stat.st_size,
                "extension": final.suffix.lower(),
                "width": int(cfg["video_width"]),
                "height": int(cfg["video_height"]),
                "fps": cfg.get("video_fps", 30),
                "duration_seconds": round(float(hook["duration"]), 3),
            },
            "pipeline": {
                "youtube_channel_reputation_used_for_ranking": False,
                "youtube_view_count_used_for_ranking": True,
                "cookies_source": str(Path.home() / "cookies.txt") if (Path.home() / "cookies.txt").is_file() else None,
                "temporary_directory": str(temp.resolve()),
                "temporary_files_deleted_after_success": True,
                "gpu_encoder_mode": cfg.get("video_encoder", "auto"),
            },
            "config_snapshot": cfg,
        }

        json_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

        db.finish(serial, metadata, final)
        db.event(serial, "FINISHED", str(final))

        # Only now is temp cleaned. If anything above fails, temp remains.
        for child in temp.iterdir():
            try:
                if child.is_file() or child.is_symlink():
                    child.unlink()
                elif child.is_dir():
                    shutil.rmtree(child)
            except OSError:
                pass

        print("\nPROCESSED WITHOUT ERRORS.")
        print(f"Final reel: {final}")
        print(f"Final reel JSON: {json_path}", flush=True)
        return "done"

    except Exception as exc:
        # If a serial exists for the selected video, preserve it as ERROR.
        # Selection/search errors have no chosen serial and are logged in skips.
        if 'serial' in locals():
            db.set_status(serial, "ERROR", str(exc))
            db.event(serial, "ERROR", str(exc))
        print(f"\nERROR while processing: {exc}", flush=True)
        return "error"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--retry", type=int, help="retry one chosen-video serial")
    parser.add_argument("--reset", type=int, help="reset one chosen-video serial to PENDING")
    args = parser.parse_args()

    cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))
    Path(cfg["temp_dir"]).mkdir(parents=True, exist_ok=True)
    Path(cfg["reels_finished_dir"]).mkdir(parents=True, exist_ok=True)

    db = DB(cfg["db_path"])
    if args.reset:
        db.reset(args.reset)

    if args.retry:
        row = db.get(args.retry)
        if not row:
            raise SystemExit(f"Serial {args.retry} was not found.")
        original = json.loads(row["original_json"])
        selected = json.loads(row["selected_json"])
        # Retry is deliberately the same processing pipeline, with no new
        # automatic selection.
        print_header(f"RETRY CHOSEN VIDEO [{args.retry:04d}]")
        print(f"Title: {selected['title']}")
        print(f"URL:   {selected['url']}", flush=True)
        # Build a playlist-like entry and force processing through the helper.
        # It will resolve the same selected video and retain the serial.
        cfg2 = dict(cfg)
        cfg2["_forced_selection"] = selected
        process_retry(original, selected, args.retry, db, cfg2)
        return

    entries = playlist(cfg["playlist_url"])
    for entry in entries:
        result = process(entry, db, cfg)
        if result == "quit":
            break


def process_retry(original, selected, serial, db, cfg):
    try:
        row = db.get(serial)
        if row and row["status"] == "FINISHED":
            print("Already FINISHED; nothing to retry.", flush=True)
            return
        previous_final = Path(row["final_path"]) if row and row["final_path"] else None
        db.set_selected(serial, original, selected)
        db.set_status(serial, "PROCESSING", None)
        temp = Path(cfg["temp_dir"])
        temp.mkdir(parents=True, exist_ok=True)

        print("\nDownloading selected YouTube video to temp/ ...", flush=True)
        yfile = download(selected["url"], temp)
        print("Reading complete YouTube metadata ...", flush=True)
        selected_info = info(selected["url"])
        print("Analysing audio and selecting the single final hook ...", flush=True)
        hook = detect(yfile, temp, cfg)

        final_dir = Path(cfg["reels_finished_dir"])
        final_dir.mkdir(parents=True, exist_ok=True)
        final = final_dir / f"{serial:04d}_{selected['id']}_reel.mp4"
        json_path = final_dir / f"{serial:04d}_{selected['id']}_reel.json"

        print("Rendering final 9:16 reel ...", flush=True)
        render_result = __import__("modules.video", fromlist=["render"]).render(
            yfile, hook["start"], hook["end"], final, cfg
        )
        st = final.stat()
        metadata = {
            "schema_version": "2.0",
            "generated_at_utc": utc_now(),
            "serial": serial,
            "status": "FINISHED",
            "original_playlist_song": original,
            "chosen_video": selected,
            "chosen_video_ytdlp_metadata": selected_info,
            "hook": hook,
            "render": render_result,
            "final_reel": {
                "path": str(final.resolve()),
                "json_path": str(json_path.resolve()),
                "filename": final.name,
                "size_bytes": st.st_size,
                "width": int(cfg["video_width"]),
                "height": int(cfg["video_height"]),
                "fps": cfg.get("video_fps", 30),
                "duration_seconds": round(float(hook["duration"]), 3),
            },
            "pipeline": {
                "youtube_channel_reputation_used_for_ranking": False,
                "youtube_view_count_used_for_ranking": True,
                "cookies_source": str(Path.home() / "cookies.txt") if (Path.home() / "cookies.txt").is_file() else None,
            },
            "config_snapshot": cfg,
            "retry": True,
        }
        json_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        db.finish(serial, metadata, final)
        db.event(serial, "FINISHED", str(final))
        if previous_final and previous_final.resolve() != final.resolve():
            previous_json = previous_final.with_suffix(".json")
            try:
                if previous_final.exists():
                    previous_final.unlink()
                if previous_json.exists():
                    previous_json.unlink()
            except OSError:
                pass
        for child in temp.iterdir():
            try:
                if child.is_file() or child.is_symlink(): child.unlink()
                elif child.is_dir(): shutil.rmtree(child)
            except OSError:
                pass
        print("\nPROCESSED WITHOUT ERRORS.")
        print(f"Final reel: {final}")
        print(f"Final reel JSON: {json_path}", flush=True)
    except Exception as exc:
        db.set_status(serial, "ERROR", str(exc))
        db.event(serial, "ERROR", str(exc))
        print(f"\nERROR while processing: {exc}", flush=True)


if __name__ == "__main__":
    main()
