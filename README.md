# Audio Shorts Generator — Final Clean

## What this project does
This is a YouTube-only pipeline. Spotify, SpotDL, ISRC matching, Spotify metadata, Spotify audio, audio alignment, browser cookies, and YouTube Data API usage are removed.

Pipeline:

1. Read the configured YouTube playlist directly with `yt-dlp`.
2. Assign every playlist entry a stable serial number based on playlist order.
3. Upsert the original playlist song details into SQLite before processing.
4. Skip entries already marked `DONE`.
5. Search YouTube using the original playlist title.
6. Either show manual choices or automatically choose a result.
7. Automatic ranking deliberately ignores channel reputation. Exact title matching is weighted heavily, and `Full Video Song` / `Video Song` wording receives a strong priority bonus.
8. Download the selected original MP4.
9. Read metadata from that selected video.
10. Optionally download only creator-provided subtitle tracks. Auto-generated captions and automatic translations are never requested.
11. Run advanced non-lyrics hook analysis on the selected video's own audio.
12. Evaluate many overlapping, variable-length candidates between 35 and 75 seconds.
13. Score energy, peaks, onset activity, build-up, dynamics, beat density, repeated/coherent musical material, ending quality and preferred duration.
14. Snap the winning boundaries to nearby beats when possible.
15. Render one final hook only.
16. Create a 1080x1920 reel with a pure black canvas, centered landscape source, small center crop for edge artifacts, cinematic adjustment, and subtitles only when a creator-provided synced track exists.
17. Use NVIDIA NVENC automatically when available; otherwise use CPU x264.
18. Save detailed original-song details, selected-video details, hook details and final path in SQLite.
19. Delete `temp/` contents only after successful completion. If processing fails, temporary files remain for debugging.

## Database and reruns

`state/pipeline.db` contains the `queue` table. Each row has:
- `serial`
- original playlist ID/title/URL
- selected video ID/title/URL
- status
- error
- detailed JSON metadata
- final reel path

If a wrong video was chosen, reset its serial:

```powershell
python main.py --reset 5
python main.py --retry 5
```

You may delete the corresponding final reel first if you want it regenerated.

## Setup

Install FFmpeg and ensure `ffmpeg` is available on PATH.

```powershell
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

No YouTube API key is required. No cookies are used.

## Configuration

`auto_youtube_selection: true` chooses automatically. Set it to `false` for manual choice.

`auto_continue: true` processes continuously.

`source_crop_width` and `source_crop_height` control the small centered crop used to remove edge artifacts. Lower values crop more.

`cinematic_brightness`, `cinematic_contrast`, and `cinematic_saturation` control the FFmpeg image adjustment.

`video_encoder: "auto"` uses NVENC when the installed FFmpeg exposes `h264_nvenc`; otherwise it falls back to x264.

## Output

Only successful final reels remain permanently under `reels/finished/`. Working MP4, WAV, subtitle and analysis files live directly in `temp/` with no per-song subfolders.
