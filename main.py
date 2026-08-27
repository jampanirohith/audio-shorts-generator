import argparse
import hashlib
import json
import platform
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from modules.db import PlaylistDB, ReelDB
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
    Path(cfg["playlist_db_path"]).parent.mkdir(parents=True, exist_ok=True)
    Path(cfg["reels_db_path"]).parent.mkdir(parents=True, exist_ok=True)


def _clean_temp(temp):
    import gc
    temp = Path(temp)
    if not temp.exists():
        return []
    gc.collect()
    failures = []
    for child in list(temp.iterdir()):
        removed = False
        last_error = None
        for attempt in range(12):
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
                time.sleep(0.20 * (attempt + 1))
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
    *, serial, original, selected, selected_info, search_results,
    ranking, reference_info, hook, render_result, source_file,
    source_probe, final_path, final_probe, cfg, mode, started_at,
):
    source_file = Path(source_file)
    final_path = Path(final_path)
    source_size = source_file.stat().st_size

    return {
        "schema_version": "4.0",
        "generated_at_utc": utc_now(),
        "processing_started_at_utc": started_at,
        "processing_finished_at_utc": utc_now(),
        "serial": int(serial),
        "status": "FINISHED",

        "source_identity": {
            "identity_type": "chosen_youtube_video",
            "primary_reference": "selected_video_id",
            "selected_video_id": selected["id"],
            "selected_video_url": selected["url"],
            "selected_video_title": selected["title"],
            "serial_is_stable_for_selected_video": True,
        },

        "original_playlist_song": original,
        "original_playlist_source_metadata": reference_info or {},

        "chosen_video": {
            "search_result_at_selection": selected,
            "complete_ytdlp_metadata": selected_info,
        },

        "youtube_search": {
            "query": original.get("title", ""),
            "selection_mode": mode,
            "result_count": len(search_results or []),
            "results": search_results or [],
            "ranking": ranking or [],
            "ranking_policy": {
                "channel_reputation_used": False,
                "title_similarity_weight": 0.54,
                "video_wording_weight": 0.22,
                "view_count_weight": 0.08,
                "source_duration_weight": 0.16,
                "view_count_normalization": "log10 relative to largest returned result",
                "strong_video_wording_bonus": 0.06,
                "metadata_title_disambiguation": True,
                },
        },

        "downloaded_source": {
            "filename": source_file.name,
            "temporary_path": str(source_file.resolve()),
            "size_bytes": source_size,
            "sha256": _sha256(source_file),
            "ffprobe": source_probe,
            "complete_source_metadata_captured_before_cleanup": True,
            "deleted_after_success": True,
            "cookies_file_used": (
                str((Path.home() / "cookies.txt").resolve())
                if (Path.home() / "cookies.txt").is_file() else None
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
            "duration_seconds": _output_duration(final_probe, hook["duration"]),
            "ffprobe": final_probe,
        },

        "pipeline": {
            "single_final_hook": True,
            "browser_cookie_extraction": False,
            "youtube_channel_reputation_used": False,
            "youtube_view_count_used": True,
            "playlist_order_persisted": True,
            "two_database_architecture": True,
            "selected_video_is_primary_reel_reference": True,
            "working_files_directly_in_temp": True,
            "temp_cleanup_after_success_only": True,
            "atomic_finalization": True,
            "atomic_json_write": True,
            "gpu_encoder_mode": cfg.get("video_encoder", "auto"),
        },

        "runtime": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },

        "config_snapshot": cfg,
    }


def process_selected(
    original, selected, serial, reel_db, playlist_db, cfg, *,
    search_results=None, ranking=None, reference_info=None,
    mode="automatic", playlist_id=None,
):
    temp = Path(cfg["temp_dir"])
    final_dir = Path(cfg["reels_finished_dir"])
    final_dir.mkdir(parents=True, exist_ok=True)
    temp.mkdir(parents=True, exist_ok=True)

    previous_row = reel_db.get(serial)
    previous_final = (
        Path(previous_row["final_path"])
        if previous_row and previous_row["final_path"] else None
    )
    previous_json = (
        Path(previous_row["final_json_path"])
        if previous_row and previous_row["final_json_path"] else None
    )

    started_at = utc_now()
    reel_db.set_selected(serial, original, selected, search_results, mode)
    reel_db.set_status(serial, "PROCESSING", None)
    reel_db.event(serial, "PROCESSING", f"Selected video: {selected['id']}")
    if playlist_id:
        playlist_db.set_status(
            playlist_id, original["id"], "PROCESSING", serial=serial
        )

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
            source_file, hook["start"], hook["end"], final, cfg
        )
        final_probe = probe(final)

        metadata = _build_final_metadata(
            serial=serial, original=original, selected=selected,
            selected_info=selected_info, search_results=search_results or [],
            ranking=ranking or [], reference_info=reference_info,
            hook=hook, render_result=render_result,
            source_file=source_file, source_probe=source_probe,
            final_path=final, final_probe=final_probe, cfg=cfg,
            mode=mode, started_at=started_at,
        )

        # Both permanent artifacts must exist before the DB can say FINISHED.
        _write_json_atomic(json_path, metadata)
        if not final.is_file() or not json_path.is_file():
            raise RuntimeError("Final reel or final JSON was not created.")

        reel_db.finish(serial, metadata, final, json_path)
        reel_db.event(serial, "FINISHED", str(final))
        if playlist_id:
            playlist_db.set_status(
                playlist_id, original["id"], "FINISHED", serial=serial
            )

        # Replace old reel only after the new pair and database record are safe.
        for old_path in (previous_final, previous_json):
            if old_path and old_path.exists():
                try:
                    if old_path.resolve() not in {final.resolve(), json_path.resolve()}:
                        old_path.unlink()
                except OSError as exc:
                    reel_db.event(
                        serial, "CLEANUP_WARNING",
                        f"Could not remove superseded file {old_path}: {exc}"
                    )

        cleanup_failures = _clean_temp(temp)
        if cleanup_failures:
            for leftover, cleanup_error in cleanup_failures:
                reel_db.event(
                    serial, "CLEANUP_WARNING",
                    f"Could not remove temporary file {leftover}: {cleanup_error}"
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
        reel_db.set_status(serial, "ERROR", str(exc))
        reel_db.event(serial, "ERROR", str(exc))
        if playlist_id:
            playlist_db.set_status(
                playlist_id, original["id"], "ERROR", serial=serial, error=str(exc)
            )
        print(f"\nERROR while processing serial {serial:04d}: {exc}", flush=True)
        print("Temporary files were retained in temp/ for debugging.", flush=True)
        return "error"


def process_playlist_entry(entry, playlist_id, playlist_db, reel_db, cfg):
    # `sync()` returns SQLite rows, not the raw yt-dlp playlist dictionaries.
    # Normalize both shapes here so the persisted playlist remains the
    # source-of-truth and fields such as title/URL/index are never lost.
    metadata = {}
    raw_metadata = entry.get("metadata_json")
    if raw_metadata:
        try:
            metadata = json.loads(raw_metadata) if isinstance(raw_metadata, str) else dict(raw_metadata)
        except (TypeError, ValueError):
            metadata = {}

    original = {
        "playlist_id": playlist_id,
        "playlist_title": (
            entry.get("playlist_title")
            or metadata.get("playlist_title")
            or ""
        ),
        "title": (
            entry.get("title")
            or entry.get("original_title")
            or ""
        ),
        "url": (
            entry.get("url")
            or entry.get("original_url")
            or ""
        ),
        "id": (
            entry.get("id")
            or entry.get("original_video_id")
        ),
        "playlist_index": (
            entry.get("playlist_index")
            or entry.get("current_position")
        ),
    }

    row = playlist_db.get(playlist_id, original["id"])
    if row and row["processing_status"] in {"FINISHED", "SKIPPED", "ERROR"}:
        print_header(
            f"CURRENT PLAYLIST ENTRY [{original['playlist_index']}]: {original['title']}"
        )
        print(f"Status remembered in playlist database: {row['processing_status']}")
        if row["final_serial"]:
            print(f"Final reel serial: {int(row['final_serial']):04d}")
        if row["last_error"]:
            print(f"Last error: {row['last_error']}")
        print("No repeated processing performed.", flush=True)
        return "skip"

    print_header(
        f"CURRENT PLAYLIST ENTRY [{original['playlist_index']}]: {original['title']}"
    )
    print(f"Original playlist URL: {original['url']}", flush=True)

    try:
        print("\nSearching YouTube ...", flush=True)
        results = search(original["title"], cfg.get("top_youtube_results", 10))

        reference_info = None
        if cfg.get("automation", {}).get("auto_youtube_selection", True):
            try:
                reference_info = info(original["url"])
            except Exception:
                reference_info = None

        selected, ranking = choose(
            results, original["title"], cfg,
            reference_info=reference_info,
        )

        if isinstance(selected, str) and selected == "skip":
            reel_db.record_skip(original, "User skipped YouTube selection")
            playlist_db.set_status(
                playlist_id, original["id"], "SKIPPED",
                error="User skipped YouTube selection"
            )
            print("SKIPPED WITHOUT ERRORS.", flush=True)
            return "skip"

        if isinstance(selected, str) and selected == "quit":
            print("Quit requested.", flush=True)
            return "quit"

        serial = reel_db.get_or_create_serial(selected)
        reel_row = reel_db.get(serial)

        print(f"\nCHOSEN YOUTUBE VIDEO [{serial:04d}]")
        print(f"Title: {selected['title']}")
        print(f"URL:   {selected['url']}", flush=True)

        if reel_row["status"] == "FINISHED":
            playlist_db.set_status(
                playlist_id, original["id"], "FINISHED", serial=serial
            )
            print("Already FINISHED in reels database; skipping duplicate processing.", flush=True)
            return "done"

        duplicate_serial = reel_db.selected_exists(
            selected["id"], exclude_serial=serial
        )
        if duplicate_serial is not None:
            reason = (
                f"Chosen YouTube video is already FINISHED under serial "
                f"{duplicate_serial:04d}."
            )
            reel_db.record_skip(original, reason, serial)
            playlist_db.set_status(
                playlist_id, original["id"], "SKIPPED",
                serial=serial, error=reason
            )
            print(f"SKIPPED: {reason}", flush=True)
            return "skip"

        playlist_db.update_serial(playlist_id, original["id"], serial)
        return process_selected(
            original, selected, serial, reel_db, playlist_db, cfg,
            search_results=results, ranking=ranking,
            reference_info=reference_info,
            mode="automatic" if cfg.get("automation", {}).get(
                "auto_youtube_selection", True
            ) else "manual",
            playlist_id=playlist_id,
        )

    except Exception as exc:
        playlist_db.set_status(
            playlist_id, original["id"], "ERROR", error=str(exc)
        )
        reel_db.event(None, "ERROR", str(exc))
        print(f"\nERROR before processing could begin: {exc}", flush=True)
        return "error"


def retry_serial(serial, reel_db, playlist_db, cfg):
    row = reel_db.get(serial)
    if not row:
        raise SystemExit(f"Serial {serial} was not found.")
    original = json.loads(row["original_json"])
    selected = json.loads(row["selected_json"])
    if not selected.get("id"):
        raise SystemExit(f"Serial {serial} does not contain a valid chosen video.")

    print_header(f"RETRY CHOSEN VIDEO [{serial:04d}]")
    print(f"Title: {selected['title']}")
    print(f"URL:   {selected['url']}", flush=True)

    playlist_id = original.get("playlist_id")
    reference_info = None
    try:
        if original.get("url"):
            reference_info = info(original["url"])
    except Exception:
        pass

    return process_selected(
        original, selected, serial, reel_db, playlist_db, cfg,
        search_results=[], ranking=[], reference_info=reference_info,
        mode="retry", playlist_id=playlist_id,
    )


def reselect_serial(serial, reel_db, playlist_db, cfg):
    row = reel_db.get(serial)
    if not row:
        raise SystemExit(f"Serial {serial} was not found.")

    original = json.loads(row["original_json"])
    if not original.get("title"):
        raise SystemExit(f"Serial {serial} has no original playlist title.")

    print_header(f"RESELECTING FINAL REEL [{serial:04d}]")
    print(f"Original playlist title: {original.get('title', '')}")
    print(f"Original playlist URL:   {original.get('url', '')}")
    print(f"Current chosen video:    {row['selected_video_title']}")
    print(f"Current chosen URL:      {row['selected_video_url']}")

    print("\nSearching YouTube ...", flush=True)
    results = search(original["title"], cfg.get("top_youtube_results", 10))
    selected, _ = choose(results, original["title"], cfg, force_manual=True)

    if isinstance(selected, str):
        if selected == "skip":
            print("Reselection skipped.", flush=True)
            return "skip"
        if selected == "quit":
            print("Reselection cancelled.", flush=True)
            return "quit"

    duplicate_serial = reel_db.selected_exists(
        selected["id"], exclude_serial=serial
    )
    if duplicate_serial is not None:
        reason = (
            f"That YouTube video is already FINISHED under serial "
            f"{duplicate_serial:04d}."
        )
        reel_db.set_status(serial, "ERROR", reason)
        reel_db.event(serial, "ERROR", reason)
        raise SystemExit(reason)

    print(f"\nRESELECTED VIDEO FOR SERIAL [{serial:04d}]")
    print(f"Title: {selected['title']}")
    print(f"URL:   {selected['url']}", flush=True)

    playlist_id = original.get("playlist_id")
    return process_selected(
        original, selected, serial, reel_db, playlist_db, cfg,
        search_results=results, ranking=[], mode="manual_reselection",
        playlist_id=playlist_id,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Professional YouTube playlist-to-reel pipeline."
    )
    parser.add_argument("--retry", type=int, help="reprocess stored chosen video for a reel serial")
    parser.add_argument("--reselect", type=int, help="manually choose a new YouTube video for a reel serial")
    parser.add_argument("--reset", type=int, help="reset a reel serial to PENDING")
    parser.add_argument(
        "--retry-errors", action="store_true",
        help="retry playlist entries remembered as ERROR"
    )
    args = parser.parse_args()

    cfg = _load_config()
    _ensure_directories(cfg)

    with PlaylistDB(cfg["playlist_db_path"]) as playlist_db, ReelDB(cfg["reels_db_path"]) as reel_db:
        playlist_db.recover_processing()
        reel_db.recover_processing()

        if args.reset is not None:
            reel_db.reset(args.reset)

        if args.retry is not None:
            retry_serial(args.retry, reel_db, playlist_db, cfg)
            return

        if args.reselect is not None:
            reselect_serial(args.reselect, reel_db, playlist_db, cfg)
            return

        entries = playlist(cfg["playlist_url"])
        if not entries:
            print("No playlist entries were found.")
            return

        playlist_id = entries[0].get("playlist_id") or PlaylistDB.playlist_id_from_url(
            cfg["playlist_url"]
        )
        playlist_title = entries[0].get("playlist_title", "")

        playlist_id, run_id, stored_entries, changes = playlist_db.sync(
            cfg["playlist_url"], entries, playlist_title
        )

        # Rebuild playlist status from the permanent reel database. This is
        # especially important on the first run after upgrading from the old
        # single-database version: completed reels must not be processed again.
        for entry_row in stored_entries:
            reel_row = reel_db.by_original_video_id(entry_row["original_video_id"])
            if not reel_row:
                continue
            reel_status = str(reel_row["status"] or "").upper()
            if reel_status in {"FINISHED", "SKIPPED", "ERROR"}:
                playlist_db.set_status(
                    playlist_id,
                    entry_row["original_video_id"],
                    reel_status,
                    serial=reel_row["serial"],
                    error=reel_row["error"],
                )
        stored_entries = playlist_db.current_entries(playlist_id)

        print_header(f"PLAYLIST SNAPSHOT RUN #{run_id}")
        print(f"Playlist: {playlist_title or playlist_id}")
        print(f"Current entries: {len(stored_entries)}")
        print(
            f"Changes since previous run: +{changes['added']} added, "
            f"-{changes['removed']} removed, "
            f"{changes['reordered']} reordered, "
            f"{changes['changed']} changed",
            flush=True,
        )

        if args.retry_errors:
            targets = [
                row for row in stored_entries
                if row["processing_status"] in {"PENDING", "ERROR"}
            ]
        else:
            targets = [
                row for row in stored_entries
                if row["processing_status"] == "PENDING"
            ]

        if not targets:
            print("\nNo unprocessed playlist entries. Nothing repeated.", flush=True)
            return

        for row in targets:
            result = process_playlist_entry(
                dict(row), playlist_id, playlist_db, reel_db, cfg
            )
            if result == "quit":
                break


if __name__ == "__main__":
    main()
