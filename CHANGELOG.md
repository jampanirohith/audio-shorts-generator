## 1.0.13
- Replaced whole-track global correlation with a first-15-second original-song anchor scan.
- Scans YouTube audio forward from 0 using simple RMS/high-low energy shape and peak/valley changes.
- Uses one global offset; the manual hook is still never re-searched.
- Prefers the earliest candidate within a small tolerance of the best score to avoid later repeated sections.


## 1.0.13
- Explicitly regression-tested manual timeline syntax such as `02:12.92` and `03:11.72`.
- Fixed stale `downloaded_with_guard.mp4` reuse by caching the exact requested YouTube section metadata and invalidating mismatches.
- Added downloaded-section duration verification before exact trimming.
- Replaced fragile stream-copy trimming with deterministic exact-duration video re-encoding, NVIDIA NVENC first with CPU fallback.
- Improved trim failures to report source duration and requested duration separately.
## 1.0.11

- Removed the 40-second Reel/hook duration limit. The user-entered `hook.start` → `hook.end` timeline is authoritative for Reel duration.
- Replaced hook-level peak-pattern matching with one global original-song ↔ YouTube-audio offset calculation.
- YouTube hook timing is now computed as `original hook time + global offset`.
- Kept the simple static-center 9:16 video layout and existing NVIDIA-first rendering path.

## 1.0.10
- `python main.py` now automatically synchronizes `hook_timeline.json` from `songs/final/` before processing.
- The same automatic sync runs for processing/resume entry points.
- Existing hook start/end values are preserved.
- Existing explicit `lrc_path` values are preserved; newly discovered songs receive their matching `.lrc` path automatically.
- `--fillhookjson` remains available as an explicit/manual sync command.

## 1.0.9
- Added `python main.py --fillhookjson`.
- The command scans every MP3 in `songs/final/` and regenerates the project-home `hook_timeline.json` song list.
- Added explicit `lrc_path` for every song entry.
- Existing hook start/end values are preserved by song basename.
- New songs are added with blank hook start/end values; no automatic hook selection is performed.
- Hook-plan loading now validates the explicit LRC path and uses it for lyric rendering.

# Changelog

## 1.0.8
- Removed automatic hook discovery/selection from the processing pipeline.
- Added project-home `hook_timeline.json` as the sole authoritative hook-selection input.
- `python main.py` now loads and prints all configured song timelines before processing.
- Added strict timeline validation with a 40-second maximum.
- Removed Smart Crop/subject tracking from the active rendering path.
- Replaced it with a static centered video layout at approximately 70% of 9:16 canvas height.
- Kept NVENC-first video encoding with CPU fallback.
- Changed lyrics to one LRC line at a time; line text is sourced from LRC and the current word is highlighted.
- Kept exact selected-hook Demucs stem cropping and 8D rendering.
- Kept simple full-track YouTube peak-pattern matching for visual synchronization.
- Output JSON now records the timeline-file hook decision and static video layout.


## 1.0.14
- Fixed guarded YouTube section trimming to remove the guard-before interval before exact hook extraction.
- Final assembly now accepts the requested hook duration explicitly.
- Final validation now writes validation/final_validation.json and reports failed checks and probe data in the error.


## 1.0.15
- Fixed `VideoGrabber.trim_exact()` guard-start regression by passing `trim_start_ms` into the actual FFmpeg trim encoder.
- Applies consistently to both NVIDIA NVENC and libx264 fallback.
- Preserves exact manual hook duration after removing the downloaded guard-before interval.


## 1.0.16
- Changed the static centered video panel from 70% to 80% of the 1080x1920 canvas height.
- Updated render/provenance defaults to 80% static-center layout.
- Recomputed final validation `overall` directly from the current boolean checks so stale state cannot falsely reject a valid output.
