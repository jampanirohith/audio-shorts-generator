# Audio Shorts Generator — Professional Final Pipeline

A persistent YouTube-playlist-to-final-reel pipeline. The selected YouTube video is the
permanent identity of a final reel; playlist position is tracked separately only for
playlist history and ordering.

## What this version fixes

- Remembers the complete playlist snapshot and its order across runs.
- Detects additions, removals, reordering and metadata changes.
- Does not repeatedly search/process playlist entries already marked `FINISHED`,
  `SKIPPED` or `ERROR`.
- Uses two professional SQLite databases:
  - `state/playlist.db` — playlist membership, ordering, history and source status.
  - `state/reels.db` — final reels, chosen YouTube video identity, metadata and events.
- Stable reel serials belong to the **chosen YouTube video ID**, not playlist position.
- `reselect.py` keeps the same serial while changing its chosen YouTube video.
- Automatic selection uses title similarity, video-song wording, views and source duration.
  Channel reputation is never used.
- When the original playlist video's metadata is available, its real title is used as an
  additional disambiguation signal. This is particularly important for ambiguous titles
  such as a song name shared by multiple movies.
- No browser-cookie extraction exists. Only `~/cookies.txt` / `%USERPROFILE%\cookies.txt`
  is used when present.
- Download progress and low-level FFmpeg output stay hidden; meaningful pipeline stages
  remain visible in the terminal.
- Complete source metadata is captured before the temporary source is deleted.
- Final MP4 and ultra-detailed JSON are written atomically.
- A reel is not marked `FINISHED` until both permanent files exist.
- Failed runs keep `temp/` for debugging.
- Successful runs clean `temp/`.
- NVENC is used automatically when available, with CPU x264 fallback.
- Final rendering uses center crop -> full output-width scaling -> cinematic treatment ->
  centered black canvas.

## Pipeline

1. Read the configured YouTube playlist with `yt-dlp`.
2. Record a playlist snapshot and compare it with the previous snapshot.
3. Preserve playlist order in `playlist.db`.
4. Skip playlist entries whose remembered status is `FINISHED`, `SKIPPED` or `ERROR`.
5. Search YouTube using the original playlist video title.
6. Show search results.
7. Automatically rank or manually choose one result.
8. Assign/reuse the stable reel serial for the chosen YouTube video ID.
9. Store original playlist details under the reel record.
10. Download the selected video into `temp/`.
11. Capture complete `yt-dlp` metadata and `ffprobe` metadata.
12. Analyse the selected video's own audio for one 35–60 second hook.
13. Render one final reel.
14. Probe the final file.
15. Write the detailed JSON beside the MP4.
16. Commit the final reel state to `reels.db`.
17. Mark the source playlist entry `FINISHED`.
18. Remove temporary files only after all permanent work succeeds.

## Databases

### `state/playlist.db`

The playlist database is the source of truth for the configured playlist.

`playlists` stores the playlist itself.

`playlist_runs` stores each synchronization run and counts:

- added
- removed
- reordered
- changed

`playlist_entries` stores:

- playlist ID
- original YouTube video ID
- original title and URL
- current and previous positions
- first/last seen timestamps
- current membership
- processing status
- attempts
- last error
- final reel serial

`playlist_entry_history` stores the event history for each run.

### `state/reels.db`

The reels database is the source of truth for generated reels.

`reels` stores:

- stable serial
- selected YouTube video ID (unique primary reel reference)
- selected title and URL
- original playlist identity
- original playlist JSON
- selected video JSON
- search JSON
- status
- attempts
- complete generated metadata
- source/final hashes
- final MP4 path
- final JSON path
- timestamps

`reel_selection_history` records every initial selection/reselection.

`reel_skips` records explicit and duplicate-prevention skips.

`reel_events` records processing milestones and errors.

Statuses:

- `PENDING`
- `PROCESSING`
- `FINISHED`
- `SKIPPED`
- `ERROR`

The databases use foreign keys, indexes, WAL mode, transactions and schema versioning.

## Upgrade from the previous single database

If an older `state/pipeline.db` exists when `state/reels.db` is first created, the project
imports the previous queue records once and preserves their serials, selected video IDs,
statuses, metadata and final paths. The legacy database is never modified or deleted.
The first playlist synchronization then links those preserved reel records back to the
corresponding original playlist entries so completed work is not repeated.

## Playlist memory and repeated runs

The first:

```powershell
python main.py
```

creates the initial playlist snapshot.

A later run compares the newly read playlist against the stored state.

Example:

```text
Run 1:
1 Song A
2 Song B
3 Song C

Run 2:
1 Song A
2 NEW SONG
3 Song B
4 Song C
```

The database records `NEW SONG` as `ADDED` and the moved entries as `REORDERED`.

The permanent reel serial is not changed because of playlist reordering.

A successful item is not searched/downloaded again simply because its playlist position
changed.

By default, an `ERROR` item is also not automatically retried. Use `--retry-errors` when
you deliberately want the current error entries retried.

## Terminal output

The terminal intentionally shows the important work:

```text
==============================================================================
CURRENT PLAYLIST ENTRY [12]: Guruvaram
==============================================================================

Searching YouTube ...

Top YouTube results:
[1] ...
[2] ...
...

AUTO CHOSEN:
[VIDEO_ID] ...
URL: ...

CHOSEN YOUTUBE VIDEO [0012]
Title: ...
URL: ...

Downloading selected YouTube video to temp/ ...
Reading complete YouTube metadata ...
Analysing audio and selecting the single final hook ...
Rendering final 1920x1080 reel ...
Temporary files cleaned successfully.

PROCESSED WITHOUT ERRORS.
Final reel: reels/finished/0012_VIDEO_ID_reel.mp4
Final reel JSON: reels/finished/0012_VIDEO_ID_reel.json
```

The detailed downloader progress is intentionally suppressed.

## Automatic YouTube selection

The search query remains the original playlist video title.

Ranking uses:

- 54% title similarity
- 22% video-song wording
- 8% logarithmic view count
- 16% source-duration similarity
- a small real-video wording bonus
- quality penalties for alternate-speed, remix/remaster, cover/instrumental, BTS,
  promo/short, audio-only and collection results

Channel reputation is never considered.

For ambiguous playlist titles, the complete metadata title of the original playlist video
is also compared against each search result. This gives titles such as:

```text
Dookudu : Guruvaram March Okati Full Video Song
```

a much stronger identity signal than the one-word playlist title:

```text
Guruvaram
```


## Reselection

Run:

```powershell
python reselect.py
```

Enter the existing final reel serial.

The same serial is retained. YouTube is searched again and the choice is manual.

The replacement is processed completely before the previous MP4/JSON pair is removed.

If the newly selected YouTube video is already a finished reel under another serial,
reselection is rejected.

## Retry

Retry a stored chosen video:

```powershell
python main.py --retry 12
```

Retry does not perform a new YouTube search.

Reset its status first if needed:

```powershell
python main.py --reset 12
python main.py --retry 12
```

Retry all remembered playlist errors deliberately:

```powershell
python main.py --retry-errors
```

## Final JSON

Every successful reel has:

```text
reels/finished/
    0012_VIDEO_ID_reel.mp4
    0012_VIDEO_ID_reel.json
```

The JSON contains:

- schema and processing timestamps
- stable serial
- selected YouTube identity
- original playlist details
- complete original-video metadata when available
- complete selected-video `yt-dlp` metadata
- every search result
- ranking calculations
- ranking policy
- downloaded source filename, size and SHA-256
- source `ffprobe`
- hook-analysis details
- crop configuration
- output dimensions
- scaling behavior
- cinematic parameters
- encoder and actual FFmpeg command
- FFmpeg version
- final `ffprobe`
- final size and SHA-256
- complete configuration snapshot
- runtime information

This JSON is intended as a permanent handoff document for later re-encoding, 8D/audio
work, alternate exports, Instagram upload tooling and debugging.

## Rendering / cinematic treatment

Current output:

```json
"video_width": 1920,
"video_height": 1080
```

Crop defaults:

```json
"source_crop_width": 0.7,
"source_crop_height": 0.55
```

Rendering:

```text
source
  ↓
center crop
  ↓
scale cropped source to full 1920 px output width
  ↓
subtle cinematic contrast / saturation / gamma
  ↓
restrained sharpening
  ↓
subtle vignette
  ↓
center on pure-black 1920×1080 canvas
```

Small source videos are deliberately upscaled to the complete output width.

The cinematic treatment is deliberately restrained so it improves perceived contrast,
color separation and focus without aggressively changing the source.

Tune in `config.json`:

```json
"cinematic_enabled": true,
"cinematic_brightness": 0.0,
"cinematic_contrast": 1.10,
"cinematic_saturation": 1.03,
"cinematic_gamma": 1.02,
"cinematic_sharpen": 0.30,
"cinematic_vignette_divisor": 7
```

## Cookies

Only this explicit file is used:

```text
Windows: C:\Users\<username>\cookies.txt
Linux/macOS: ~/cookies.txt
```

No Chrome/Edge/Firefox/browser profile extraction is performed.

Keep `cookies.txt` outside the project and never commit it.

## Requirements

Install:

```powershell
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

FFmpeg and FFprobe must be available on `PATH`.

Run:

```powershell
python main.py
```

## Project structure

```text
audio-shorts-generator/
├── main.py
├── reselect.py
├── config.json
├── requirements.txt
├── README.md
├── run.ps1
├── .env.example
├── .gitignore
└── modules/
    ├── __init__.py
    ├── db.py
    ├── hooks.py
    ├── video.py
    └── youtube.py
```

Runtime directories are created automatically:

```text
temp/
reels/finished/
state/
```

They are intentionally ignored by Git.
