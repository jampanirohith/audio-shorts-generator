# BUILD INFO

Implementation revision: **1.0.16**

This build replaces automatic hook discovery with an authoritative project-home `hook_timeline.json`, removes Smart Crop/subject tracking from the active renderer, uses a static centered 80%-height video layout, renders one LRC line at a time with per-word highlighting, and keeps exact-hook Demucs-based 8D audio plus a single global original-song to YouTube-audio offset calculation.

This build adds `python main.py --fillhookjson`, which scans `songs/final/`, populates every song with its MP3 and matching LRC path, and preserves existing manually entered hook timelines.

This build automatically synchronizes `hook_timeline.json` from `songs/final/` at the start of every processing invocation, including plain `python main.py`, `--process-all`, `--process`, and `--resume`. Existing hook times remain untouched.


Revision 1.0.14 fixes manual timeline processing for MM:SS.xx inputs, invalidates stale cached YouTube video sections when the requested timeline changes, verifies downloaded-section duration, and uses deterministic exact-duration video re-encoding (NVENC first, libx264 fallback) instead of fragile stream-copy trimming.


Revision 1.0.14 replaces full-track correlation with a simple first-15-second original-song anchor scan across the YouTube audio using RMS high/low energy shape plus peak/valley changes. The earliest near-best match is selected and used as the single global offset.


Revision 1.0.15 fixes the guard-aware trim implementation so trim_start_ms is propagated into both NVENC and libx264 exact-duration encoding paths. This prevents the NameError seen during guarded YouTube section trimming and preserves the exact manual hook duration.


Revision 1.0.16 changes the static centered video panel from 70% to 80% of the 9:16 canvas height and recomputes final validation status directly from the actual boolean checks, preventing a stale overall flag from rejecting an otherwise valid MP4.
