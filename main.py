import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from modules.db import DB
from modules.hooks import detect
from modules.video import probe, render
from modules.youtube import download, info, playlist, search, choose


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def print_header(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78, flush=True)


def _load_config():
    config_path = Path("config.json")
    if not config_path.is_file():
        raise SystemExit("config.json was not found in the project directory.")
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"config.json is invalid: {exc}") from exc


def _ensure_directories(cfg):
    Path(cfg["temp_dir"]).mkdir(parents=True, exist_ok=True)
    Path(cfg["reels_finished_dir"]).mkdir(parents=True, exist_ok=True)
    Path(cfg["db_path"]).parent.mkdir(parents=True, exist_ok=True)


def _clean_temp(temp):
    """Remove all temporary pipeline artifacts after a successful run.

    Windows can briefly keep media files locked after a subprocess exits, so
    cleanup retries before giving up. A cleanup failure never invalidates an
    otherwise successful render, but it is reported to the caller.
    """
    import gc
    import time

    temp = Path(temp)
    if not temp.exists():
        return []

    gc.collect()
    failures = []

    for child in list(temp.iterdir()):
        removed = False
        last_error = None

        for attempt in range(10):
            try:
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child)
                else:
                    child.unlink()
                removed = True
                break
            except OSError as exc:
                last_error = exc
                gc.collect()
                time.sleep(0.25 * (attempt + 1))

        if not removed:
            failures.append((child, last_error))

    return failures


def _write_json_atomic(path, data):
    path = Path(path)
    temporary = path.with_name(path.stem + ".writing.json")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    temporary.replace(path)




def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _output_duration(probe_data, fallback):
    try:
        return round(float(probe_data["format"]["duration"]), 3)
    except (KeyError, TypeError, ValueError):
        return round(float(fallback), 3)


def _build_final_metadata(
    *,
    serial,
    original,
    selected,
    selected_info,
    search_results,
    ranking,
    reference_info,
    hook,
    render_result,
    source_file,
    source_probe,
    final_path,
    final_probe,
    cfg,
    mode,
):
    source_file = Path(source_file)
    final_path = Path(final_path)

    return {
        "schema_version": "3.0",
        "generated_at_utc": utc_now(),
        "serial": int(serial),
        "status": "FINISHED",

        "source_identity": {
            "identity_type": "chosen_youtube_video",
            "selected_video_id": selected["id"],
            "selected_video_url": selected["url"],
            "selected_video_title": selected["title"],
            "serial_is_stable_for_selected_video": True,
        },

        "original_playlist_song": original,
        "original_playlist_source_metadata": reference_info or {},

        "chosen_video": {
            "search_result": selected,
            "complete_ytdlp_metadata": selected_info,
        },

        "youtube_search": {
            "query": original["title"],
            "selection_mode": mode,
            "result_count": len(search_results),
            "results": search_results,
            "ranking": ranking,
            "ranking_policy": {
                "channel_reputation_used": False,
                "title_similarity_weight": 0.58,
                "video_wording_weight": 0.22,
                "view_count_weight": 0.10,
                "source_duration_weight": 0.10,
                "view_count_normalization": "log10 relative to largest returned result",
                "strong_video_wording_bonus": 0.06,
                "title_matching": (
                    "exact normalized core-song match is strongest; "
                    "fuzzy matching tolerates spacing/spelling variants"
                ),
                "quality_penalties": (
                    "lyrics/audio/alternate versions/covers/BTS/promos/"
                    "collections are penalized so they do not beat a real "
                    "video-song result merely because of views"
                ),
                "reference_metadata": (
                    "original playlist video metadata is read silently for "
                    "duration-based disambiguation; the original video is "
                    "never downloaded or assigned a serial"
                ),
            },
        },

        "downloaded_source": {
            "filename": source_file.name,
            "temporary_path": str(source_file.resolve()),
            "size_bytes": source_file.stat().st_size,
            "sha256": _sha256(source_file),
            "ffprobe": source_probe,
            "deleted_after_success": True,
            "cookies_file_used": (
                str((Path.home() / "cookies.txt").resolve())
                if (Path.home() / "cookies.txt").is_file()
                else None
            ),
        },

        "hook": hook,

        "render": render_result,

        "final_reel": {
            "filename": final_path.name,
            "path": str(final_path.resolve()),
            "json_path": str(final_path.with_suffix(".json").resolve()),
            "size_bytes": final_path.stat().st_size,
            "sha256": _sha256(final_path),
            "width": render_result["canvas"]["width"],
            "height": render_result["canvas"]["height"],
            "aspect_ratio": render_result["canvas"]["aspect_ratio"],
            "fps": render_result["canvas"]["fps"],
            "duration_seconds": _output_duration(
                final_probe,
                hook["duration"],
            ),
            "ffprobe": final_probe,
        },

        "pipeline": {
            "single_final_hook": True,
            "browser_cookie_extraction": False,
            "youtube_channel_reputation_used": False,
            "youtube_view_count_used": True,
            "working_files_directly_in_temp": True,
            "temp_cleanup_after_success_only": True,
            "gpu_encoder_mode": cfg.get("video_encoder", "auto"),
        },

        "config_snapshot": cfg,
    }


def process_selected(
    original,
    selected,
    serial,
    db,
    cfg,
    *,
    search_results=None,
    ranking=None,
    reference_info=None,
    mode="automatic",
):
    temp = Path(cfg["temp_dir"])
    final_dir = Path(cfg["reels_finished_dir"])
    final_dir.mkdir(parents=True, exist_ok=True)
    temp.mkdir(parents=True, exist_ok=True)

    previous_row = db.get(serial)
    previous_final = (
        Path(previous_row["final_path"])
        if previous_row and previous_row["final_path"]
        else None
    )
    previous_json = (
        Path(previous_row["final_json_path"])
        if previous_row and previous_row["final_json_path"]
        else None
    )

    db.set_selected(serial, original, selected)
    db.set_status(serial, "PROCESSING", None)
    db.event(serial, "PROCESSING", f"Selected video: {selected['id']}")

    try:
        print("\nDownloading selected YouTube video to temp/ ...", flush=True)
        source_file = download(selected["url"], temp, selected["id"])

        print("Reading complete YouTube metadata ...", flush=True)
        selected_info = info(selected["url"])
        source_probe = probe(source_file)

        print("Analysing audio and selecting the single final hook ...", flush=True)
        hook = detect(source_file, temp, cfg)

        final = final_dir / f"{serial:04d}_{selected['id']}_reel.mp4"
        json_path = final.with_suffix(".json")

        print(
            f"Rendering final {cfg['video_width']}x{cfg['video_height']} reel ...",
            flush=True,
        )
        render_result = render(
            source_file,
            hook["start"],
            hook["end"],
            final,
            cfg,
        )
        final_probe = probe(final)

        metadata = _build_final_metadata(
            serial=serial,
            original=original,
            selected=selected,
            selected_info=selected_info,
            search_results=search_results or [],
            ranking=ranking or [],
            reference_info=reference_info or {},
            hook=hook,
            render_result=render_result,
            source_file=source_file,
            source_probe=source_probe,
            final_path=final,
            final_probe=final_probe,
            cfg=cfg,
            mode=mode,
        )

        _write_json_atomic(json_path, metadata)
        db.finish(serial, metadata, final, json_path)
        db.event(serial, "FINISHED", str(final))

        # A reselection can change the YouTube video ID and therefore the
        # permanent filename. Remove the superseded pair only after the new
        # reel and JSON have been safely committed.
        old_paths = (previous_final, previous_json)
        new_paths = {final.resolve(), json_path.resolve()}
        for old_path in old_paths:
            if old_path and old_path.exists() and old_path.resolve() not in new_paths:
                try:
                    old_path.unlink()
                except OSError as cleanup_error:
                    db.event(
                        serial,
                        "CLEANUP_WARNING",
                        f"Could not remove superseded file {old_path}: {cleanup_error}",
                    )

        cleanup_failures = _clean_temp(temp)
        if cleanup_failures:
            for leftover, cleanup_error in cleanup_failures:
                db.event(
                    serial,
                    "CLEANUP_WARNING",
                    f"Could not remove temporary file {leftover}: {cleanup_error}",
                )
            print(
                "WARNING: some temporary files could not be deleted; " 
                "the reel itself was completed successfully.",
                flush=True,
            )
            for leftover, _ in cleanup_failures:
                print(f"Temporary file retained: {leftover}", flush=True)
        else:
            print("Temporary files cleaned successfully.", flush=True)

        print("\nPROCESSED WITHOUT ERRORS.")
        print(f"Final reel: {final}")
        print(f"Final reel JSON: {json_path}", flush=True)
        return "done"

    except Exception as exc:
        db.set_status(serial, "ERROR", str(exc))
        db.event(serial, "ERROR", str(exc))
        print(f"\nERROR while processing serial {serial:04d}: {exc}", flush=True)
        print("Temporary files were retained in temp/ for debugging.", flush=True)
        return "error"


def process_playlist_entry(entry, db, cfg):
    original = {
        "playlist_id": entry.get("id"),
        "title": entry.get("title", ""),
        "url": entry.get("url", ""),
        "playlist_index": entry.get("playlist_index"),
    }

    print_header(f"CURRENT PLAYLIST ENTRY: {original['title']}")
    print(f"Original playlist URL: {original['url']}", flush=True)

    try:
        print("\nSearching YouTube ...", flush=True)
        results = search(
            original["title"],
            cfg.get("top_youtube_results", 10),
        )
        reference_info = None
        if cfg.get("automation", {}).get("auto_youtube_selection", True):
            # Read the original playlist video's metadata only as a silent
            # reference for disambiguating search results. The original video
            # is never downloaded and is not assigned a serial.
            try:
                reference_info = info(original["url"])
            except Exception:
                reference_info = None

        selected, ranking = choose(
            results,
            original["title"],
            cfg,
            reference_info=reference_info,
        )

        if selected == "skip":
            db.record_skip(original, "User skipped YouTube selection")
            print("SKIPPED WITHOUT ERRORS.", flush=True)
            return "skip"

        if selected == "quit":
            print("Quit requested.", flush=True)
            return "quit"

        serial = db.get_or_create_serial(selected)
        row = db.get(serial)

        print(f"\nCHOSEN YOUTUBE VIDEO [{serial:04d}]")
        print(f"Title: {selected['title']}")
        print(f"URL:   {selected['url']}", flush=True)

        if row["status"] in {"FINISHED", "DONE"}:
            print(
                "Already FINISHED in database; skipping duplicate processing.",
                flush=True,
            )
            return "done"

        duplicate_serial = db.selected_exists(
            selected["id"],
            exclude_serial=serial,
        )
        if duplicate_serial is not None:
            reason = (
                f"Chosen YouTube video is already FINISHED under serial "
                f"{duplicate_serial:04d}."
            )
            db.set_status(serial, "SKIPPED", reason)
            db.record_skip(original, reason, serial)
            print(f"SKIPPED: {reason}", flush=True)
            return "skip"

        return process_selected(
            original,
            selected,
            serial,
            db,
            cfg,
            search_results=results,
            ranking=ranking,
            reference_info=reference_info,
            mode="automatic" if cfg.get("automation", {}).get(
                "auto_youtube_selection", True
            ) else "manual",
        )

    except Exception as exc:
        db.event(None, "ERROR", str(exc))
        print(f"\nERROR before processing could begin: {exc}", flush=True)
        return "error"


def retry_serial(serial, db, cfg):
    row = db.get(serial)
    if not row:
        raise SystemExit(f"Serial {serial} was not found.")

    original = json.loads(row["original_json"])
    selected = json.loads(row["selected_json"])
    if not selected.get("id"):
        raise SystemExit(f"Serial {serial} does not contain a valid chosen video.")

    print_header(f"RETRY CHOSEN VIDEO [{serial:04d}]")
    print(f"Title: {selected['title']}")
    print(f"URL:   {selected['url']}", flush=True)

    reference_info = None
    try:
        reference_info = info(original["url"])
    except Exception:
        reference_info = None

    return process_selected(
        original,
        selected,
        serial,
        db,
        cfg,
        search_results=[],
        ranking=[],
        reference_info=reference_info,
        mode="retry",
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate one final hook reel per selected YouTube video."
    )
    parser.add_argument(
        "--retry",
        type=int,
        help="reprocess the stored chosen video for a serial",
    )
    parser.add_argument(
        "--reset",
        type=int,
        help="reset a serial to PENDING before normal/retry processing",
    )
    args = parser.parse_args()

    cfg = _load_config()
    _ensure_directories(cfg)

    with DB(cfg["db_path"]) as db:
        if args.reset is not None:
            db.reset(args.reset)

        if args.retry is not None:
            retry_serial(args.retry, db, cfg)
            return

        entries = playlist(cfg["playlist_url"])
        if not entries:
            print("No playlist entries were found.")
            return

        for entry in entries:
            result = process_playlist_entry(entry, db, cfg)
            if result == "quit":
                break


if __name__ == "__main__":
    main()
