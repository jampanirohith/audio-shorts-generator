# Audio Shorts Generator — Clean Final Pipeline

A single-hook YouTube playlist-to-reel pipeline.

The permanent identity of a processed item is the **chosen YouTube video**, not the
playlist position. Every chosen YouTube video receives a stable serial number in SQLite.
That serial is the handle used by the retry and manual reselection tools.

The project is deliberately quiet about low-level downloader output: the terminal shows
the current playlist item, search results, the selected result, meaningful processing
stages, and the final success/error state.

---

## 1. Final pipeline

1. Read the configured YouTube playlist with `yt-dlp`.
2. Do not assign permanent serials from playlist order.
3. Display the current playlist entry.
4. Search YouTube using the original playlist **video title**.
5. Display the returned search results.
6. In automatic mode, rank results using:
   - title similarity,
   - video-song wording,
   - logarithmically normalized view count.
7. Never use channel reputation as an automatic ranking signal.
8. Display the automatically chosen result.
9. After a result is chosen:
   - assign/reuse its stable serial,
   - store the original playlist details under that chosen-video record,
   - store the chosen search-result details,
   - mark the record `PROCESSING`.
10. Skip a chosen video already marked `FINISHED`.
11. Download the selected YouTube video into `temp/` with `yt-dlp`.
12. Read the complete selected-video metadata returned by `yt-dlp`.
13. Probe the actual downloaded source with `ffprobe`.
14. Extract the selected video's own audio for hook analysis.
15. Evaluate overlapping, variable-length candidates from 35–60 seconds.
16. Score energy, peaks, onset activity, build-up, dynamics, beat density,
    repeated/coherent musical material, ending quality, and preferred duration.
17. Snap the winning boundaries to nearby beats when possible.
18. Render exactly one final hook.
19. Create the configured output canvas (the supplied final configuration is 1920×1080).
20. Center-crop the source using the configured crop fractions.
21. Scale the cropped source to the complete output width.
22. Center the scaled cropped video on a pure-black canvas.
23. Use NVIDIA NVENC automatically when available; otherwise use CPU x264.
24. Probe the final reel with `ffprobe`.
25. Write an ultra-detailed JSON beside the final reel.
26. Store the completed metadata and final paths in SQLite.
27. Remove the old reel pair only after a successful replacement.
28. Clean `temp/` only after the reel, JSON, and database completion succeed.
29. If processing fails, leave `temp/` intact for debugging.

---

## 2. Terminal behavior

The normal terminal output is intentionally human-readable rather than a raw downloader log.

You will see:

```text
==============================================================================
CURRENT PLAYLIST ENTRY: Example Song
==============================================================================
Original playlist URL: ...

Searching YouTube ...

YouTube search results (channel reputation is not considered):
[1] score=... | title_match=... | video_wording=... | views=... | ...
[2] score=... | title_match=... | video_wording=... | views=... | ...

AUTO CHOSEN:
[VIDEO_ID] Example Song - Video Song
URL: https://www.youtube.com/watch?v=...

CHOSEN YOUTUBE VIDEO [0007]
Title: Example Song - Video Song
URL: ...

Downloading selected YouTube video to temp/ ...
Reading complete YouTube metadata ...
Analysing audio and selecting the single final hook ...
Rendering final 1920x1080 reel ...

PROCESSED WITHOUT ERRORS.
Final reel: reels/finished/0007_VIDEO_ID_reel.mp4
Final reel JSON: reels/finished/0007_VIDEO_ID_reel.json
```

The detailed `yt-dlp` download/progress stream is suppressed.

---

## 3. YouTube automatic selection

The search query is the original playlist video title.

Automatic ranking deliberately ignores channel identity/reputation.

Current ranking:

```text
58% title similarity
22% video wording
10% view count
10% source-duration similarity
```

The title matcher first extracts the core song name from wrappers such as
`(From "Movie")`. Exact core-song matches are strongest, while compact matching tolerates
common spacing/repeated-letter differences such as `Koppamga` vs `Kopam Ga`.

Results containing real `Video Song` / `Full Video Song` wording receive a strong bonus.
`Video with Lyrics`, lyric/lyrical, audio, slowed/reverb, remix, cover, BTS, promo and
collection results receive quality penalties so a large view count cannot push an inferior
variant above the actual music video.

The original playlist video's metadata is read silently as a reference. Its duration is used
as a supporting signal when several search results have similar titles. The original video
is never downloaded, never assigned a serial, and is not used as a channel-reputation signal.

View count is normalized logarithmically relative to the largest returned result, so a viral
result cannot overwhelm a substantially better title match simply because it has more views.

The complete ranking calculation is saved in the final JSON.

Set:

```json
"auto_youtube_selection": false
```

to use manual selection during normal playlist processing.

---

## 4. Stable serial design

A playlist position is not the permanent identity.

When a YouTube result is chosen, the database looks up its YouTube video ID:

- if that video ID already has a serial, the same serial is reused;
- otherwise the next serial is assigned.

Example:

```text
0007_A3Im3P0--aE_reel.mp4
0007_A3Im3P0--aE_reel.json
```

Serial `0007` therefore identifies the chosen-video record.

The database keeps the original playlist details inside that chosen-video record:

```text
queue
 └── serial 0007
      ├── selected YouTube video
      ├── original playlist song
      ├── search information
      ├── processing status
      ├── hook information
      ├── render information
      └── final paths
```

---

## 5. Database statuses

`state/pipeline.db` contains:

### `queue`

Permanent chosen-video records.

Important fields:

- `serial`
- `selected_video_id`
- `selected_video_title`
- `selected_video_url`
- `original_json`
- `selected_json`
- `status`
- `error`
- `metadata_json`
- `final_path`
- `final_json_path`
- timestamps

Statuses are:

- `PENDING`
- `PROCESSING`
- `FINISHED`
- `SKIPPED`
- `ERROR`

### `skipped`

Stores explicit skips and duplicate-prevention skips together with the original
playlist information and reason.

### `events`

Stores processing milestones and error messages for auditing/debugging.

The database initialization is migration-safe for the fields used by earlier versions:
existing compatible queue data is not renamed away simply because a newer field is needed.

---

## 6. Cookie behavior

If YouTube requires a cookie file, the only supported location is:

```text
Windows:
C:\Users\<your-user>\cookies.txt

Other systems:
~/cookies.txt
```

The program passes that explicit file to `yt-dlp` when it exists.

No browser profile extraction is performed.

No Chrome, Edge, Firefox, or other browser cookie integration is used.

---

## 7. Working files

All working files are placed directly inside:

```text
temp/
```

There are no per-song temporary subdirectories.

Typical temporary files include:

```text
temp/
    source_VIDEO_ID.mp4
    hook_analysis.wav
```

A failed processing attempt intentionally leaves these files in place.

A successful attempt removes the contents of `temp/` only after the permanent reel,
permanent JSON, and database update are complete.

The next attempt uses deterministic source filenames so an old failed download is not
mistaken for a different YouTube result.

---

## 8. Hook detection

Only one final hook is produced.

Default candidate range:

```text
minimum: 35 seconds
maximum: 60 seconds
preferred region: 40–55 seconds
```

The detector evaluates many overlapping candidates at one-second start spacing and
five-second duration increments.

Features include:

- RMS energy
- peak level
- onset activity
- build-up
- dynamics
- beat density
- repeated/coherent musical material
- ending quality
- preferred duration

The winning interval is optionally snapped to nearby beat boundaries when the resulting
duration remains inside the configured limits.

The complete detector result is saved in the final JSON.

---

## 9. Video rendering

The supplied final configuration uses:

```json
"video_width": 1920,
"video_height": 1080
```

That produces a **16:9 1920×1080 final reel**.

Crop defaults:

```json
"source_crop_width": 0.7,
"source_crop_height": 0.55
```

The rendering order is:

```text
selected source
    ↓
center crop
    ↓
scale cropped image to full output width
    ↓
apply cinematic adjustment
    ↓
place in vertical center of black canvas
    ↓
encode final MP4
```

This means a small source is intentionally upscaled to the complete 1920-pixel output width
instead of remaining as a small landscape rectangle.

The crop remains centered.

The output canvas remains pure black around the scaled cropped video.

---

## 10. GPU acceleration

With:

```json
"video_encoder": "auto"
```

the renderer checks FFmpeg for `h264_nvenc`.

If available:

```text
h264_nvenc
```

is used.

Otherwise:

```text
libx264
```

is used.

The actual encoder and complete FFmpeg output probe are stored in the final JSON.

---

## 11. Final reel JSON

Every successful reel has a JSON file beside it:

```text
reels/finished/
    0007_VIDEO_ID_reel.mp4
    0007_VIDEO_ID_reel.json
```

The JSON is intended to be a permanent handoff/audit document.

It contains:

- schema version
- generation timestamp
- stable serial
- chosen-video identity
- original playlist details
- selected search result
- complete `yt-dlp` metadata
- all search results
- ranking calculations
- ranking policy
- source download filename and size
- source `ffprobe` data
- hook detector result
- crop settings
- scaling behavior
- canvas dimensions
- cinematic settings
- encoder
- audio settings
- final `ffprobe` data
- final file size/path
- configuration snapshot
- pipeline behavior flags
- cookie-file presence/path information

This provides enough persistent information for later processing such as re-encoding,
audio mastering, 8D work, alternate exports, audit/debugging, and upload preparation.

---

## 12. Manual reselection

Use:

```powershell
python reselect.py
```

Then enter the serial:

```text
Enter final reel serial number: 7
```

The tool:

1. opens the existing serial;
2. reads its stored original playlist title;
3. searches YouTube again;
4. shows the search results;
5. forces manual selection;
6. keeps the same serial;
7. changes the chosen YouTube video reference;
8. downloads the newly chosen video;
9. reads its complete metadata;
10. runs the same hook detector;
11. renders one new reel;
12. writes the new detailed JSON;
13. updates SQLite;
14. removes the previous reel/JSON pair only after the replacement succeeds;
15. cleans `temp/` only after successful completion.

This avoids creating a new serial simply because the selected YouTube video was corrected.

If the newly selected video is already `FINISHED` under another serial, reselection is rejected
to prevent duplicate final references.

---

## 13. Retry

To process the stored chosen video again:

```powershell
python main.py --retry 7
```

Retry does not perform a new YouTube search.

It uses the chosen YouTube video currently stored for serial 7.

`--retry` is allowed for both completed and failed records.

Optional reset:

```powershell
python main.py --reset 7
```

Then:

```powershell
python main.py --retry 7
```

---

## 14. Project structure

```text
audio-shorts-generator-final/
│
├── main.py
├── reselect.py
├── config.json
├── requirements.txt
├── README.md
├── run.ps1
├── .env.example
├── .gitignore
│
└── modules/
    ├── __init__.py
    ├── youtube.py
    ├── hooks.py
    ├── video.py
    └── db.py
```

Runtime directories are created automatically:

```text
temp/
reels/finished/
state/
```

They are intentionally not required to be present in the source ZIP.

---

## 15. Installation on Windows

Verify:

```powershell
ffmpeg -version
ffprobe -version
yt-dlp --version
```

Create a virtual environment:

```powershell
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Run:

```powershell
python main.py
```

---

## 16. Configuration

The most important settings are:

```json
{
  "video_width": 1920,
  "video_height": 1080,

  "source_crop_width": 0.7,
  "source_crop_height": 0.55,

  "hook_min_seconds": 35,
  "hook_preferred_min_seconds": 40,
  "hook_preferred_max_seconds": 55,
  "hook_max_seconds": 60,

  "video_encoder": "auto"
}
```

For automatic YouTube selection:

```json
"auto_youtube_selection": true
```

For manual selection during normal processing:

```json
"auto_youtube_selection": false
```

---

## 17. Expected failure behavior

### YouTube anti-bot/authentication error

If `yt-dlp` reports that authentication is required, provide a valid Netscape-format
`cookies.txt` at the supported home-directory location.

The application does not attempt browser extraction.

### FFmpeg/FFprobe not found

Install FFmpeg and make sure both commands are available on `PATH`.

### Hook analysis failure

The record is marked `ERROR`, the exception is written to the database event log, and
`temp/` is retained.

### Render failure

The permanent output is not replaced by a partial `.rendering.mp4` file. The temporary
render file is removed and the database record becomes `ERROR`.

### Final JSON failure

The reel is not considered a completed pipeline result until its JSON has been written and
the database has been updated.

---

## 18. Professional invariants

The final implementation maintains these invariants:

- Playlist order never becomes the permanent reel serial.
- The selected YouTube video is the primary database identity.
- One serial maps to one current chosen YouTube video.
- A finished YouTube video is not silently duplicated under another serial.
- Manual reselection keeps the same serial.
- Retry does not perform a new search.
- Exactly one hook is rendered.
- The output dimensions always come from `config.json`.
- The cropped source always targets the complete output width.
- Low-level downloader progress is hidden.
- Meaningful processing stages remain visible in the terminal.
- Temporary files remain after failures.
- Temporary files are cleaned only after successful completion.
- A replacement reel is not allowed to destroy the previous finished reel until the
  replacement has succeeded.
- The final JSON and database record describe the actual generated output.
