# Audio Shorts Generator — Final Integrated Baseline

This version integrates the agreed pipeline decisions: append-only playlist identity by YouTube video ID; simple playlist status (`YET_TO_START`/`FINISHED`); atomic never-reused serials; independent YouTube/Spotify automatic-or-manual selection in `config.json`; YouTube ranking with views as a supporting signal; Spotify search using selected YouTube metadata; YouTube manual-LRC preference; no Spotify↔YouTube synchronization when usable YouTube LRC exists; whole-song energy highs/lows synchronization with time-offset estimation otherwise; candidate-based whole-song hook analysis; lyric-aware hook scoring only when LRC exists; beat/musical/lyric boundary optimization with a small engaging lead-in; duplicate song detection using selected YouTube identity plus canonical Spotify song key; delayed canonical song creation; LibreLyrics LRC in the canonical song; final validation; and cleanup/reset on cancellation or failure.

## Install

Python 3.10+ is recommended/required by current spotDL/LibreLyrics releases. FFmpeg and FFprobe must be on PATH.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

spotDL currently supports Spotify search through its `Spotdl.search()` API and download through its downloader; current spotDL releases may also use Deno for some YouTube downloads. If a specific environment requires it, install Deno using spotDL's documented setup.

## Configuration

```json
"youtube_selection_mode": "automatic",
"spotify_selection_mode": "automatic"
```

Change either independently to `manual`. Manual mode displays the ranked top five. Automatic mode chooses rank #1.

Spotify and LibreLyrics credentials are configured in one place: `config.json`.

```json
"spotify": {
  "client_id": "YOUR_SPOTIFY_CLIENT_ID",
  "client_secret": "YOUR_SPOTIFY_CLIENT_SECRET"
},
"librelyrics": {
  "sp_dc": "YOUR_SPOTIFY_SP_DC"
}
```

`client_id`/`client_secret` are used by spotDL. `sp_dc` is the Spotify Web Player cookie required by the LibreLyrics Spotify plugin. Before fetching lyrics, the pipeline mirrors `librelyrics.sp_dc` into LibreLyrics' own plugin configuration automatically. Do not commit real credentials or the `sp_dc` cookie to source control.

## Databases

`state/playlist.db` contains only playlist entries, their persistent append-only order, YouTube identity/title/URL, and the simple processing status plus completion serial; it does not contain hook, Spotify, rendering, or source metadata.

`state/reel.db` contains the permanent serial allocator and reel identity. Serial allocation is transactional and consumed numbers are never reused.

`state/songs.db` contains canonical song records and duplicate identity (`selected YouTube video ID` OR normalized Spotify title/artist/album key).

## Pipeline

1. Read the configured playlist with yt-dlp.
2. Synchronize playlist membership using YouTube video ID.
3. Existing playlist entries keep their original order forever; new entries append to the bottom.
4. Select the first `YET_TO_START` entry.
5. Search YouTube using the original playlist title.
6. Rank candidates using title/metadata identity, artist/movie-album evidence, trusted-channel evidence, version quality, duration, full-video wording, and view count. Views support the decision but do not dominate it.
7. Automatic/manual selection is controlled only by config.
8. Allocate a permanent serial atomically after YouTube selection.
9. Check duplicate selected YouTube video identity.
10. Download best video + best audio and let FFmpeg merge them into one MP4.
11. Inspect manual YouTube subtitles only; choose original-language > English > other. Automatic captions are not used.
12. Capture complete yt-dlp metadata.
13. Search Spotify using selected YouTube title + artist + movie/album metadata.
14. Rank Spotify candidates and use config-controlled automatic/manual selection.
15. Check canonical song duplicate identity.
16. Download Spotify audio/metadata/artwork with spotDL.
17. Download Spotify synced LRC with LibreLyrics.
18. If YouTube LRC exists, do not synchronize Spotify/YouTube. If it does not, synchronize the entire-song energy high/low envelopes and estimate a time offset.
19. Generate many overlapping hook candidates across the entire YouTube song.
20. Score energy, sustained strength, peaks, onset/rhythm, build-up, dynamics, beat density, musical coherence, repetition, lyrics when available, music/lyric overlap, boundary quality and duration. Penalize dead space, awkward cuts, weak sections and incomplete lyric phrases.
21. Prefer 35–60 seconds but do not force the range when a naturally superior hook is slightly outside it.
22. Find a natural beat + musical phrase + lyric phrase boundary and search slightly earlier for an engaging lead-in.
23. Use YouTube LRC for hook analysis when present; otherwise synchronized Spotify LRC; otherwise no lyrics.
24. Render selected LRC lines as centered timed lyrics in the middle of the reel; the lead-in remains lyric-free until the first applicable lyric timestamp.
25. Render the reel and probe it.
26. Only after successful reel render/probe, create the permanent canonical song from spotDL audio + metadata/artwork and the LibreLyrics Spotify LRC. Never use YouTube LRC in the canonical song.
27. Update songs.db, write detailed JSON, update reel.db, validate permanent outputs, mark playlist entry FINISHED, then delete `temp/<serial>`.
28. On cancellation/failure, delete the current job, remove its transient reel record, reset the playlist entry to `YET_TO_START`, and never reuse the consumed serial.

## Runtime outputs

```text
temp/<serial>/
reels/<serial>.mp4
reels/<serial>.json
songs/<serial>.mp3
state/playlist.db
state/reel.db
state/songs.db
```


## SpotDL job isolation

The pipeline uses spotDL's Python API for the actual Spotify download rather than
the `spotdl` console command. This is intentional: the console can load a user's
global `~/.spotdl/config.json` and reintroduce unrelated `archive`/`save_errors`
paths. The pipeline supplies its own per-job downloader settings, so temporary
SpotDL state stays under `temp/<serial>/`.


## Configurable lyric typography and two-line rendering

Lyric font, size, colors, outline, opacity, position, line spacing, and wrapping are configurable in `config.json`. Lyrics are rendered onto the cropped foreground video before it is placed on the black 16:9 canvas, so both lines remain inside the actual video area. Long lyric segments are wrapped into at most two lines without truncating lyric text; a balanced word boundary is preferred, with a character split as a fallback for scripts without spaces.
