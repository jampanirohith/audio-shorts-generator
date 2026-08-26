# Audio Shorts Generator — Final Pipeline

This project takes a configured YouTube playlist, searches YouTube for the corresponding
video song, chooses one result (automatically by default), detects one strong musical
hook from that video's own audio, and renders exactly one 1080x1920 reel.

## Important design rules

- **No lyrics.**
- **No subtitles.**
- **No subtitle downloads.**
- **No automatic YouTube translations.**
- **No lyric analysis.**
- **No Chrome/Edge/Firefox cookie extraction.**
- If YouTube cookies are needed, only `cookies.txt` in the current user's home directory is used.
- YouTube channel reputation is **never** used for automatic ranking.
- YouTube view count **is** used as one ranking signal.
- Only one final hook is rendered.
- Working files are kept directly in `temp/`; there are no per-song temp subfolders.
- yt-dlp download/progress output is intentionally hidden. The terminal shows the meaningful
  pipeline stages, the current playlist entry, the YouTube search results, the selected result,
  and the final success/error message.
- If processing fails, `temp/` is deliberately left intact for debugging.
- If processing succeeds, `temp/` is cleaned after the final reel and its JSON have been written.

---

# Complete pipeline

## 1. Read the playlist

`yt-dlp` reads the configured playlist directly.

The playlist position is **not** the permanent reel serial.

The playlist is used only to provide the original song/video title that becomes the YouTube
search query.

## 2. Show the current playlist entry

The terminal prints the current playlist title and URL.

It does not print the complete yt-dlp download stream.

## 3. Search YouTube

The original playlist **video title** is used as the search query.

The search returns the configured number of candidates.

For each candidate the program records:

- YouTube video ID
- title
- URL
- channel/uploader text for display/reference only
- duration when available
- view count when available
- upload date when available

## 4. Automatic YouTube ranking

Automatic ranking deliberately does **not** consider channel reputation.

Ranking uses:

1. title similarity — strongest factor
2. `Full Video Song` / `Video Song` / related video wording
3. view count using a logarithmic normalization

The view-count signal cannot overwhelm title similarity simply because a video is viral.

The terminal prints all ranked candidates and then the automatically selected result.

Manual mode is also available through `config.json`.

## 5. Permanent serial assignment

A serial is assigned **after a YouTube result has been chosen**.

The serial belongs to the chosen-video/reel record.

The same chosen YouTube video gets the same serial if it is encountered again.

This is why a final file looks like:

```text
0007_VIDEOID_reel.mp4
0007_VIDEOID_reel.json
```

The serial is therefore useful as the permanent handle for later operations.

## 6. Database record

SQLite stores the chosen video as the main reference.

The record contains:

- permanent serial
- chosen YouTube video ID/title/URL
- complete original playlist-song JSON
- chosen search-result JSON
- status
- error text when applicable
- final reel path
- complete metadata JSON

The original playlist song is stored **under the chosen-video record** rather than being
treated as the permanent identity.

### Statuses

The database records:

- `PENDING`
- `PROCESSING`
- `FINISHED`
- `ERROR`

Manual skips are recorded in the separate `skipped` table with their original playlist details
and skip reason.

The `events` table records processing milestones and errors.

## 7. Download

The selected YouTube video is downloaded by yt-dlp into:

```text
temp/
```

There are no per-song temp directories.

Only an explicit home-directory cookie file is considered:

```text
%USERPROFILE%\cookies.txt
```

on Windows, or:

```text
~/cookies.txt
```

on other systems.

No browser-cookie extraction is performed.

The download command uses quiet/no-warning operation so the terminal does not become a wall of
yt-dlp progress output.

## 8. Complete YouTube metadata

After selecting the video, the project requests the full yt-dlp metadata JSON.

That complete metadata is retained for the final JSON handoff.

This includes whatever yt-dlp exposes for the selected video, such as:

- title
- uploader/channel
- IDs
- URL
- duration
- upload date
- description
- thumbnails
- formats
- codecs
- resolution information
- view/like/comment information when exposed
- webpage/player metadata
- other extractor fields returned by yt-dlp

No attempt is made to reduce the selected video's metadata to a tiny summary.

## 9. No lyrics/subtitles stage

There is intentionally no lyrics stage.

There is intentionally no subtitle stage.

There is intentionally no caption download.

There is intentionally no automatic-translation request.

The project does not inspect lyrics to choose a hook.

## 10. Advanced single-hook detection

The selected video's own audio is extracted temporarily.

The detector evaluates many overlapping candidates.

Candidate duration:

- minimum: 35 seconds
- maximum: 60 seconds
- preferred region: approximately 40–55 seconds

The exact configuration is in `config.json`.

The detector considers musical/audio characteristics including:

- RMS energy
- peak level
- onset activity
- build-up
- dynamics
- beat density
- repeated/coherent musical material
- ending quality
- preferred duration

Beat tracking is used to snap the winning boundaries to nearby musical beats where possible.

Exactly **one** hook wins.

There is no hook-choice menu.

## 11. Final reel rendering

Output dimensions are:

```text
1080 x 1920
```

The background is pure black.

The configured source crop is applied first:

```json
"source_crop_width": 0.7,
"source_crop_height": 0.55
```

The crop is centered.

After cropping, the cropped video is **scaled to the full 1080-pixel reel width**.
This is deliberate.

That means small source videos are upscaled instead of becoming a tiny landscape rectangle.

The cropped result's aspect ratio is preserved while scaling to 1080px wide, and the resulting
video is vertically centered on the 1080x1920 black canvas.

The current cinematic adjustment is applied after cropping/scaling.

## 12. GPU acceleration

With:

```json
"video_encoder": "auto"
```

the renderer checks whether FFmpeg exposes:

```text
h264_nvenc
```

If available, NVIDIA NVENC is used.

Otherwise the renderer falls back to CPU `libx264`.

The selected encoder is recorded in the final JSON.

## 13. Permanent final JSON

Every successful reel gets a JSON file beside it:

```text
reels/finished/0007_VIDEOID_reel.mp4
reels/finished/0007_VIDEOID_reel.json
```

The JSON is intentionally detailed so the reel can be processed later for workflows such as:

- audio mastering
- 8D processing
- re-encoding
- alternate rendering
- Instagram upload preparation
- audit/debugging
- re-running a chosen source

It contains:

- schema version
- generation timestamp
- permanent serial
- original playlist details
- chosen video/search details
- complete yt-dlp metadata
- complete YouTube search candidates
- ranking information
- hook start/end/duration
- hook detector statistics
- render dimensions
- crop values
- scaling behavior
- cinematic settings
- encoder
- audio settings
- final file path
- final file size
- pipeline flags
- configuration snapshot

The JSON is written before `temp/` is cleaned.

## 14. Successful cleanup

Only after:

1. download succeeds
2. metadata succeeds
3. hook analysis succeeds
4. final reel succeeds
5. final JSON succeeds
6. database is marked finished

does the program delete the contents of `temp/`.

If any processing stage fails, temporary files remain.

---

# Reselecting a finished reel

Use:

```powershell
python reselect.py
```

Then enter the serial from the final reel filename.

Example:

```text
Enter final reel serial number: 0007
```

The program:

1. opens serial 0007
2. reads its original playlist title
3. searches YouTube again using that original title
4. shows the YouTube results
5. forces a **manual** choice
6. keeps serial `0007`
7. replaces the chosen-video reference
8. downloads the newly chosen video
9. reads complete metadata
10. runs the same single-hook detector
11. renders one new final reel
12. writes a new detailed JSON
13. updates SQLite
14. cleans `temp/` only after success

This is intentionally separate from normal automatic selection.

You do not need to manually delete the old database row.

The serial remains the same because it is the permanent reel/task handle.

The old final MP4 is overwritten by the newly rendered reel with the same serial and the new
YouTube video ID in the filename.

---

# Retry by serial

You can also retry a record directly:

```powershell
python main.py --retry 7
```

This does **not** perform a new YouTube selection. It retries the stored chosen video.

To reset its status:

```powershell
python main.py --reset 7
```

Then run:

```powershell
python main.py --retry 7
```

---

# Project layout

```text
audio-shorts-generator-final/
│
├── main.py
├── reselect.py
├── config.json
├── requirements.txt
├── README.md
├── run.ps1
├── .gitignore
├── .env.example
│
├── modules/
│   ├── __init__.py
│   ├── youtube.py
│   ├── hooks.py
│   ├── db.py
│   └── video.py
│
├── temp/
│   └── (working files only; normally empty after success)
│
├── reels/
│   └── finished/
│       ├── 0001_VIDEOID_reel.mp4
│       └── 0001_VIDEOID_reel.json
│
└── state/
    └── pipeline.db
```

No lyrics files, subtitle files, subtitle fonts, browser-cookie integrations, or per-song temp
folders are part of the final pipeline.

---

# Installation on Windows

Install FFmpeg and make sure these work:

```powershell
ffmpeg -version
ffprobe -version
yt-dlp --version
```

Create the virtual environment:

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

## Cookies

If YouTube requires authentication, place the Netscape-format exported cookie file here:

```text
C:\Users\<your-user>\cookies.txt
```

The program reads only that file.

It does not inspect Chrome, Edge, Firefox, or any other browser profile.

If the file does not exist, yt-dlp simply runs without cookies.

---

# Configuration

The most important settings are:

```json
{
  "hook_min_seconds": 35,
  "hook_preferred_min_seconds": 40,
  "hook_preferred_max_seconds": 55,
  "hook_max_seconds": 60,

  "source_crop_width": 0.7,
  "source_crop_height": 0.55,

  "video_width": 1080,
  "video_height": 1920,

  "video_encoder": "auto"
}
```

YouTube automatic selection:

```json
"auto_youtube_selection": true
```

Set it to `false` if you want the normal manual result selector.

---

# Troubleshooting

### YouTube says "Sign in to confirm you're not a bot"

Put a valid Netscape-format `cookies.txt` in your home directory.

No browser integration is used.

### Final reel looks too small

The final pipeline explicitly scales the cropped source to 1080px width.
This behavior is recorded in the JSON as:

```json
"small_sources_upscaled": true
```

### Processing fails

Do not delete `temp/`.

The project intentionally keeps its temporary working files after a failure so the failure
can be inspected.

### A finished reel uses the wrong YouTube video

Run:

```powershell
python reselect.py
```

Enter the reel serial and manually choose the correct YouTube result.

### You want to process the same chosen video again

Run:

```powershell
python main.py --retry SERIAL
```

---

# Final terminal behavior

During normal automation you should see approximately:

```text
==============================================================================
CURRENT PLAYLIST ENTRY: Example Song
==============================================================================
Original playlist URL: ...

YouTube search results (channel reputation is NOT considered):
[1] score=... | title_match=... video_wording=... views=... | ...
[2] score=... | title_match=... video_wording=... views=... | ...

AUTO CHOSEN:
[VIDEOID] Example Song - Video Song
URL: https://www.youtube.com/watch?v=...

CHOSEN YOUTUBE VIDEO [0007]
Title: Example Song - Video Song
URL: ...

Downloading selected YouTube video to temp/ ...
Reading complete YouTube metadata ...
Analysing audio and selecting the single final hook ...
Rendering final 9:16 reel ...
Crop: 0.70 x 0.55 of source
Final canvas: 1080x1920 | cropped video stretched to 1080px width and vertically centered
Encoder: NVIDIA NVENC/GPU

PROCESSED WITHOUT ERRORS.
Final reel: reels/finished/0007_VIDEOID_reel.mp4
Final reel JSON: reels/finished/0007_VIDEOID_reel.json
```

It intentionally does **not** print yt-dlp's full download progress stream.
