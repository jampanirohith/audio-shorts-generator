# Phase 3 — Timeline-Driven Telugu Reel Generator

This is a standalone Phase 3 project. It reads only the final `MP3 + LRC + JSON` package placed in `songs/final/` and writes finished Reels to `reels/generated/`.

## The hook is chosen by you

Automatic hook discovery, scoring, finalist selection, smart crop, and manual prompt-based hook selection are removed from the active pipeline.

The only hook-selection input is the project-home JSON file:

```text
hook_timeline.json
```

Example:

```json
{
  "schema_version": 1,
  "songs": [
    {
      "song_path": "songs/final/My Song.mp3",
      "hook": {
        "start": "00:01:42.500",
        "end": "00:02:11.800"
      }
    }
  ]
}
```

Rules:

- `song_path` is shown explicitly for every song.
- Relative paths are relative to the project home.
- `hook.start` and `hook.end` are the exact local MP3 timeline used for the Reel audio.
- There is **no maximum hook/Reel duration**. The Reel uses exactly the `hook.start` to `hook.end` timeline you enter.
- The MP3, LRC, and JSON must share the same basename.
- The source package is never modified.


### Auto-fill the hook timeline file

To populate `hook_timeline.json` with every MP3 currently in `songs/final/`:

```bash
python main.py --fillhookjson
```

This command:

- scans `songs/final/` for all MP3 files;
- writes the matching `lrc_path` for each song;
- preserves any existing `hook.start` and `hook.end` values for the same song basename;
- leaves new hook times blank because hook selection remains manual;
- does not modify the source MP3/LRC/JSON files.

After filling the JSON, edit the blank `hook.start` and `hook.end` values and run `python main.py`.

## Running

After editing `hook_timeline.json`:

```bash
python main.py
```

`python main.py` is equivalent to processing every entry in `hook_timeline.json`. At startup it prints each song path and its configured timeline before any processing begins.

Useful commands:

```bash
python main.py --doctor
python main.py --scan
python main.py --process "My Song"
python main.py --process-all
python main.py --resume
python main.py --inspect-match "My Song"
python main.py --validate "My Song"
python main.py --force
```

## Pipeline

1. Read and validate `hook_timeline.json`.
2. Validate each final `MP3 + LRC + JSON` package.
3. Run Demucs on the full song so all four stems are available.
4. Run full-song acoustic and lyric analysis for provenance/diagnostics; **none of this changes the user-selected hook**.
5. Download the complete YouTube song audio and calculate one global audio offset against the original local song.
6. Map the user-selected hook by adding that single offset to the original hook start/end; no hook-level re-matching is performed.
7. Download the matched YouTube video section with a small guard band and exact-trim it to the hook duration.
8. Render the source video with a **static centered layout** — no face detection, no subject tracking, no dynamic smart crop. The source video is zoomed to about **80% of the 9:16 canvas height** and centered vertically; the horizontal crop is always centered.
9. Crop the exact selected interval from Demucs vocals, drums, bass, and other stems and build the final timeline-preserving 8D mix.
10. Render **one LRC lyric line at a time**. The line text comes from the LRC file; individual words are highlighted according to LRC word timestamps when available, with Phase 2 JSON word timing as fallback. When the next LRC line starts, the previous line disappears.
11. Assemble the final 1080x1920 Reel using NVENC when available, with CPU fallback.
12. Validate and write a separate output JSON containing the hook timeline, match, video layout, 8D manifest, lyric plan, hashes, and validation results.

## Output

```text
reels/generated/
├── SongName_reel.mp4
└── SongName_reel.json
```

The final Reel audio always comes from the local song. YouTube audio is used only to locate the corresponding visual section.

Instagram publishing remains manual.
