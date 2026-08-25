# Audio Shorts Generator — Automated v5

## 1. What this project does

This project turns songs listed in a YouTube playlist into finished vertical song reels while preserving the original YouTube movie-video audio/video as the master source for the reel.

The pipeline has two different source roles:

- **YouTube:** source of the movie video, source of the final reel video, and source of the audio used for hook detection.
- **Spotify:** identification/recording-selection source, metadata source, artwork source, and optional synced-lyrics source.

The important design decision is that the Spotify recording is **not** substituted into the final reel. Spotify and YouTube audio are fingerprinted and aligned so Spotify lyrics can be mapped onto the YouTube timeline. The final reel continues to use the selected YouTube video's original audio.

This build adds four configurable automation switches:

1. **Automatic YouTube video selection** — ranks YouTube search results using the song title, video-song keywords, and a configurable allow-list of official movie-music channels.
2. **Automatic Spotify recording selection** — chooses the highest-scoring Spotify recording and gives substantially more weight to movie/album evidence, especially an album matching the movie and albums containing phrases such as `Original Motion Picture Soundtrack`.
3. **Automatic queue continuation** — starts every pending song without asking for ENTER/skip confirmation.
4. **Automatic hook selection** — selects the highest-scoring hook without asking for `[1-3]`.

All four are independently configurable. You can enable one, several, or all of them.

---

# 2. End-to-end pipeline

The complete logical flow is:

```text
YouTube playlist
      │
      ├── read playlist entries
      │
      ├── determine processing order
      │       └── playlist-added timestamp when YouTube Data API is available
      │           otherwise playlist position
      │
      ├── queue/state database upsert
      │
      ├── optional automatic continue / manual confirmation
      │
      ├── YouTube search
      │       ├── song title query
      │       └── automatic mode ranks official video-song candidates
      │
      ├── selected YouTube movie video
      │       │
      │       ├── download original MP4 into temporary staging
      │       ├── read yt-dlp metadata
      │       └── extract title / artist / movie / album clues
      │
      ├── Spotify search
      │       ├── title + artist
      │       ├── title + artist candidates
      │       ├── title + movie candidates
      │       └── title + album
      │
      ├── Spotify ranking
      │       ├── title similarity
      │       ├── artist similarity
      │       ├── movie/album similarity
      │       ├── duration similarity
      │       ├── movie-album bonus
      │       ├── OST-name bonus
      │       └── exact/contained movie-album bonus
      │
      ├── manual Spotify choice OR automatic highest-score choice
      │
      ├── duplicate checks
      │       ├── exact YouTube video ID
      │       └── Spotify ISRC
      │
      ├── Spotify recording download
      │       ├── SpotDL attempts
      │       ├── synced lyrics when available
      │       └── robust YouTube/yt-dlp fallback for audio
      │
      ├── embed Spotify metadata/artwork/lyrics into final M4A
      │
      ├── fingerprint Spotify audio
      ├── fingerprint YouTube video audio
      │
      ├── synchronize recordings
      │       ├── onset envelope
      │       ├── chroma features
      │       ├── multiple timeline anchors
      │       └── beat-time consistency
      │
      ├── hook detection on YouTube audio ONLY
      │
      ├── generate 3 hook preview videos
      │
      ├── manual hook choice OR automatic highest-score hook
      │
      ├── map Spotify lyric timestamps onto YouTube timeline
      │
      ├── render final 1080x1920 reel
      │       ├── pure black background
      │       ├── centered landscape source
      │       ├── small center crop to remove edge artifacts
      │       ├── cinematic image adjustment
      │       ├── cinematic Telugu subtitles when lyrics exist
      │       └── YouTube original audio
      │
      ├── save final reel + detailed metadata
      ├── save final Spotify M4A
      ├── record everything in SQLite
      │
      └── delete temporary working files after successful completion
```

---

# 3. Important source/timeline rule

The selected Spotify song and selected YouTube movie video are treated as two versions of the same musical recording.

The Spotify recording is **not** used as the final reel's audio.

The pipeline does this instead:

```text
Spotify audio ───────────────┐
                             ├── fingerprint + alignment ──> timestamp mapping
YouTube video audio ─────────┘
                                      │
                                      ▼
                              Spotify lyric timestamps
                                      │
                                      ▼
                              YouTube timeline
                                      │
                                      ▼
Final reel = YouTube video + YouTube audio + mapped lyrics
```

This is necessary because movie videos frequently contain:

- studio logos
- cinematic introductions
- dialogue
- silence
- extended shots
- different fades
- alternate edits
- different mastering
- a song beginning later than the Spotify recording

The alignment stage estimates the transformation:

```text
YouTube time = Spotify time + measured offset
```

The offset is estimated from multiple audio anchors instead of assuming that both files start at exactly the same instant.

---

# 4. Playlist processing order

The pipeline is designed to process the playlist from oldest-added entry to newest-added entry.

When `YOUTUBE_API_KEY` is configured, the YouTube Data API is used to obtain playlist item metadata. The pipeline uses the playlist-item timestamp as the primary ordering value.

When the API cannot be used, the pipeline falls back deterministically to playlist position.

The queue is also stored in SQLite, so previously encountered entries retain their state.

The order is therefore conceptually:

```text
oldest playlist-added song
        ↓
next song added
        ↓
next song added
        ↓
...
        ↓
newest playlist-added song
```

This matters because adding new songs to the same playlist should not cause newly added songs to jump ahead of older pending songs.

---

# 5. Automation configuration

All automation controls live in `config.json` under the `automation` object.

The default configuration keeps automation disabled so the pipeline can still be run interactively.

## Enable all requested automation

Set:

```json
"automation": {
  "auto_youtube_selection": true,
  "auto_spotify_selection": true,
  "auto_continue": true,
  "auto_hook_selection": true
}
```

You can also enable only individual features.

For example:

```json
"automation": {
  "auto_youtube_selection": true,
  "auto_spotify_selection": false,
  "auto_continue": true,
  "auto_hook_selection": false
}
```

That configuration automatically chooses the YouTube movie video and automatically advances through songs, but still asks you to choose the Spotify recording and final hook.

---

# 6. Automatic YouTube selection

## 6.1 Purpose

In manual mode the pipeline displays the top YouTube results and asks you to choose one.

In automatic mode the pipeline still performs a YouTube search, but instead of asking you to select a result it scores the results.

The intention is to favor an official movie video song rather than:

- lyric uploads
- fan uploads
- status videos
- cover versions
- random reuploads
- unrelated songs with similar names

## 6.2 Configurable search keywords

The relevant configuration is:

```json
"auto_youtube_keywords": [
  "video song",
  "full video song"
]
```

You can add other phrases if your target catalogue uses them frequently.

For example:

```json
"auto_youtube_keywords": [
  "video song",
  "full video song",
  "full video",
  "official video song"
]
```

The title scorer checks whether these phrases occur in the result title.

## 6.3 Official channel allow-list

The official-channel preference is controlled by:

```json
"auto_youtube_official_channels": [
  "Saregama Telugu",
  "Aditya Music",
  "Sony Music South",
  "Lahari Music",
  "T-Series Telugu",
  "Tips Telugu",
  "Mango Music",
  "Mango Telugu"
]
```

This list is intentionally configurable.

If a different official music channel becomes more useful for your catalogue, add its channel name here.

The channel list is a **ranking preference**, not a guarantee that every channel/result is the correct recording.

## 6.4 YouTube automatic score

The automatic selector combines:

- source-title similarity
- video-song keyword presence
- official-channel match
- a small extra bonus for the exact `full video song` phrase

The configurable weights are:

```json
"auto_youtube_title_weight": 0.35,
"auto_youtube_keyword_weight": 0.22,
"auto_youtube_channel_weight": 0.28,
"auto_youtube_duration_weight": 0.10
```

The duration field is reserved in the configuration for the broader ranking design; the current selector primarily relies on title, keyword and channel evidence because the initial search result often does not expose a trustworthy duration.

The selector prints the score components before choosing, for example:

```text
AUTO YouTube selection:
[1] score=0.694 | title=0.410 keyword=1.000 official_channel=1.000 | ...
[2] score=0.187 | title=0.533 keyword=0.000 official_channel=0.000 | ...
AUTO selected YouTube: ...
```

This makes the automatic decision auditable in the terminal.

---

# 7. YouTube metadata extraction

After selecting the YouTube result, `yt-dlp` is queried for complete metadata.

The pipeline extracts:

- video title
- original/full title
- uploader
- channel
- description
- duration
- upload date
- album information when exposed
- artist candidates
- movie candidates

The metadata is then used to improve Spotify matching.

## Telugu movie-title patterns

The parser handles common official-upload structures such as:

```text
Atithi Devo Bhava - Baguntundhi Nuvvu Navvithe Video
```

and:

```text
Oka Life - 8K Video Song | Oopiri | Nagarjuna | ...
```

The first pattern can identify:

```text
movie = Atithi Devo Bhava
song  = Baguntundhi Nuvvu Navvithe
```

The second pattern keeps:

```text
song = Oka Life
movie = Oopiri
```

when the movie is exposed as a separate title component.

This is intentionally heuristic because YouTube title formatting is not standardized.

---

# 8. Automatic Spotify selection

## 8.1 Purpose

Spotify can contain multiple recordings with the same title:

- soundtrack recording
- single release
- compilation
- anniversary edition
- live version
- cover
- remaster
- playlist/collection release
- alternate recording

Therefore the pipeline does not blindly choose the first Spotify result.

It gathers candidates from several searches and scores them.

## 8.2 Spotify search queries

The search stage uses combinations of:

```text
song title + primary artist
song title + artist candidate
song title + album
song title + movie candidate
song title
```

The resulting tracks are de-duplicated by Spotify track ID.

## 8.3 Top five

The final Spotify candidate list is limited to **5 results**.

Manual mode displays all five.

Automatic mode displays them for transparency and then chooses the highest scoring valid result.

## 8.4 Spotify scoring

The ranking considers:

1. title similarity
2. artist similarity
3. movie/album similarity
4. duration similarity
5. movie-album bonus
6. Original Motion Picture Soundtrack bonus
7. exact/contained movie-album bonus

The base score is built from title, artist, movie/album and duration evidence.

The automatic mode then adds configurable movie/OST bonuses.

Current defaults:

```json
"auto_spotify_movie_album_bonus": 0.20,
"auto_spotify_ost_bonus": 0.12,
"auto_spotify_exact_album_bonus": 0.10
```

This means a candidate whose album clearly corresponds to the movie gets a substantial advantage.

## 8.5 Original Motion Picture Soundtrack preference

The scorer explicitly recognizes album names containing phrases such as:

```text
Original Motion Picture Soundtrack
Original Soundtrack
Motion Picture Soundtrack
Original Movie Soundtrack
Film Soundtrack
```

An OST phrase receives an additional configurable bonus.

This is important for cases where Spotify contains both:

```text
Song Title
```

and:

```text
Song Title — Movie Name (Original Motion Picture Soundtrack)
```

The soundtrack release should normally rank higher when the other evidence is compatible.

## 8.6 Minimum confidence

Automatic Spotify selection can be protected with:

```json
"auto_spotify_min_score": 0.55
```

If the highest candidate falls below this value, the song is not silently accepted.

The pipeline raises an error and leaves the state/temporary work available for diagnosis.

This prevents low-confidence automatic selections from silently contaminating the final song database.

---

# 9. Spotify ISRC and duplicate prevention

The selected Spotify track's ISRC is used as the stable recording identifier whenever Spotify supplies one.

The pipeline checks both:

## YouTube duplicate

The exact YouTube video ID is checked against `youtube_done`.

If the same video was already finalized, the pipeline skips it.

## Spotify recording duplicate

The selected Spotify ISRC is checked against the songs table.

If the same recording was already finalized and its final files exist, the pipeline skips the duplicate.

This means choosing the same YouTube movie video again does not create another final reel.

---

# 10. Temporary directory design

Each active song is processed under:

```text
temp/<ISRC>/
```

There is also a temporary YouTube staging directory:

```text
temp/_youtube_downloads/<youtube-id>/
```

The intended lifecycle is:

```text
YouTube MP4
    ↓
temp/_youtube_downloads/<youtube-id>/
    ↓
selected recording confirmed
    ↓
temp/<ISRC>/
    ↓
all fingerprints / WAVs / alignment / hook previews / logs / ASS
    ↓
final outputs
    ↓
SQLite state saved
    ↓
temp/<ISRC>/ deleted after successful DONE
```

If the process fails, the temporary directory is intentionally retained so the exact failed stage can be inspected and resumed.

---

# 11. Spotify downloading

The project uses SpotDL 4.5.2 as the primary Spotify-recording resolver.

The downloader uses the same Python interpreter as `main.py`:

```text
sys.executable -m spotdl
```

This prevents Windows systems from accidentally running a different global SpotDL installation.

## Retry strategy

The downloader attempts several configurations:

1. official SpotDL API + synced lyrics
2. normal SpotDL + synced lyrics
3. official SpotDL audio-only
4. normal SpotDL audio-only
5. yt-dlp metadata-based fallback

The downloader also creates the required error-output location before invoking SpotDL. This avoids the secondary `FileNotFoundError` that can otherwise hide the original SpotDL lookup failure.

## Lyrics failure behavior

Lyrics are optional.

If synced Spotify lyrics are not available:

- the audio download is still allowed to succeed
- no fake lyrics are generated
- no guessed lyrics are inserted
- the final reel is rendered without lyric subtitles

This is deliberate because incorrect Telugu lyrics are worse than no lyrics.

---

# 12. Final audio file

The final Spotify audio is saved directly in:

```text
songs/final/
```

There are **no ISRC subfolders** in the final song directory.

The final M4A contains embedded metadata such as:

- title
- artist
- album
- album artist
- release date
- ISRC
- Spotify track information
- artwork
- lyrics when available

The project does not require separate final artwork or LRC files.

Temporary metadata files can exist under `temp/<ISRC>/` while processing, but successful completion cleans them up.

---

# 13. Fingerprinting

Both recordings are fingerprinted:

```text
Spotify audio
YouTube video audio
```

The fingerprint uses a feature representation containing:

- chroma
- onset information
- beat intervals
- beat timing
- tempo

A SHA-256 digest of quantized feature data is stored together with the detailed measurements.

The fingerprint is not used as a magical universal song-identification service. Its primary role here is to record and compare the musical characteristics of the two selected recordings before alignment.

---

# 14. Spotify ↔ YouTube timeline alignment

This is one of the most important parts of the project.

The Spotify recording may start at:

```text
0.0 seconds = actual song
```

while the YouTube movie video may start at:

```text
0.0 seconds = logo / movie intro / silence / dialogue
```

Therefore simply assuming:

```text
Spotify 30s == YouTube 30s
```

would place lyrics at the wrong locations.

The alignment stage extracts normalized audio features and searches for matching sections.

It uses:

- onset-strength envelopes
- chroma-CQT features
- multiple anchors at different positions in the Spotify recording
- beat-time agreement
- median offset estimation
- outlier rejection

The result contains:

```json
{
  "spotify_to_youtube_offset_seconds": 12.345,
  "confidence": 0.82,
  "feature_confidence": 0.86,
  "beat_alignment_confidence": 0.71,
  "offset_spread_seconds": 0.18
}
```

The exact values depend on the two recordings.

A positive offset means:

```text
YouTube time = Spotify time + offset
```

The alignment stage rejects suspiciously inconsistent matches rather than blindly producing a reel.

---

# 15. Hook detection

Hook detection uses **YouTube audio only**.

Spotify audio is not used to decide which part of the movie video is the hook.

This is important because the final reel uses the original YouTube movie video and its original audio.

The detector analyzes:

- RMS energy
- onset strength
- beat density
- tempo

It evaluates possible windows across the song and combines the musical-energy measurements into a hook score.

The configuration controls the window:

```json
"hook_min_seconds": 20,
"hook_target_seconds": 30,
"hook_max_seconds": 40
```

The pipeline then selects three distinct high-scoring candidates.

The candidates are intentionally separated so the three choices are not merely three overlapping windows of the same moment.

---

# 16. Automatic hook selection

Enable:

```json
"auto_hook_selection": true
```

The pipeline will select the hook with the highest hook score.

Optional minimum:

```json
"auto_hook_min_score": 0.0
```

If you increase this value, a weak song can be rejected instead of automatically accepting a low-quality hook.

Example:

```json
"auto_hook_min_score": 0.35
```

The selected hook is recorded in the SQLite database and final JSON metadata.

---

# 17. Manual hook mode

When automatic hook selection is disabled, the pipeline creates three preview reels.

It prints both an absolute path and a `file:///` path, for example:

```text
OPTION 1: C:\...\temp\INS123\reel_option_1.mp4
          file:///C:/.../temp/INS123/reel_option_1.mp4
```

These paths are intended to be clickable/openable from a VS Code terminal.

Then:

```text
Choose final reel [1-3], or s=skip, q=quit:
```

---

# 18. Final video composition

The final output resolution is exactly:

```text
1080 × 1920
```

The portrait canvas is created as a **plain black background**.

There are no:

- reflections
- mirrored copies
- blurred copies
- fake background extensions

The original landscape video is placed in the center.

## Source crop

A small center crop is applied before scaling.

Defaults:

```json
"source_crop_width": 0.96,
"source_crop_height": 0.92
```

This means the outer edges are trimmed slightly from the original landscape frame.

The purpose is to reduce:

- black bars already present in the source
- corner watermark pixels
- unwanted edge material

The source is **not converted into a portrait crop**.

It remains a landscape image centered inside the 9:16 canvas.

## No stretching

The landscape frame keeps its aspect ratio.

The project does not stretch the source to fill the portrait canvas.

Therefore black space above and below the landscape video is expected and intentional.

---

# 19. Cinematic visual treatment

The video receives a restrained cinematic adjustment using FFmpeg's `eq` filter.

Current defaults:

```json
"cinematic_brightness": 0.025,
"cinematic_contrast": 1.08,
"cinematic_saturation": 1.04
```

The purpose is a small tonal enhancement rather than an aggressive color transformation.

These values can be changed in `config.json`.

---

# 20. Telugu lyrics

The project uses a bundled Telugu font:

```text
fonts/NotoSerifTelugu-Medium.ttf
fonts/NotoSerifTelugu-Regular.ttf
```

The default font name is:

```json
"telugu_font": "Noto Serif Telugu"
```

The styling is centered and serif-based with an italic cinematic treatment in the ASS subtitle style.

This was chosen because it provides reliable Telugu shaping on Windows while giving a cinematic serif appearance similar in spirit to the requested Gurajada-italic aesthetic.

If Spotify synced lyrics are available:

```text
Spotify lyric timestamp
        ↓
Spotify → YouTube alignment offset
        ↓
YouTube timestamp
        ↓
only lyric lines overlapping the selected hook
        ↓
ASS subtitle
        ↓
FFmpeg subtitles filter
```

If Spotify lyrics are not available, the final reel contains **no lyric layer**.

---

# 21. Final reel audio

The final reel maps:

```text
YouTube video stream
+
YouTube original audio
+
optional mapped Spotify lyrics
```

The Spotify audio is not substituted into the reel.

This preserves the exact timing and sound of the selected movie video.

---

# 22. GPU acceleration

The pipeline is hybrid.

It is **not entirely GPU accelerated**.

The final FFmpeg H.264 encoding can use NVIDIA NVENC when available:

```json
"video_encoder": "auto"
```

In automatic mode:

```text
NVENC available
    ↓
use h264_nvenc

NVENC unavailable/fails
    ↓
fall back to libx264 CPU encoding
```

Force NVIDIA:

```json
"video_encoder": "nvenc"
```

Force CPU:

```json
"video_encoder": "cpu"
```

Other stages remain CPU/network oriented:

- Spotify API calls
- YouTube API calls
- yt-dlp
- SpotDL
- SQLite
- librosa fingerprinting
- onset detection
- chroma analysis
- beat analysis
- alignment calculations

GPU encoding mainly accelerates the final video rendering stage.

---

# 23. Database

SQLite database:

```text
state/pipeline.db
```

The database stores queue state, selected sources, errors, events, final outputs, and song-level information.

Important tables include:

## `queue`

Stores:

- queue ID
- title
- playlist URL
- playlist position
- playlist-added timestamp
- selected YouTube ID
- Spotify ISRC
- current status
- selected Spotify index
- selected hook
- error
- JSON state

## `youtube_done`

Used to prevent the same YouTube video from being finalized twice.

## `songs`

Stores final Spotify recording information keyed by ISRC.

## `events`

Stores a chronological pipeline history for debugging.

---

# 24. Resume behavior

A failed song is **not marked DONE**.

Its state remains in SQLite.

The temporary directory remains available.

On the next run the pipeline can resume using the saved state.

Successful completion changes the queue state to:

```text
DONE
```

Skipped entries become:

```text
SKIPPED
```

Failures become:

```text
FAILED
```

Duplicate detections become:

```text
DUPLICATE
```

---

# 25. Output structure

After successful processing:

```text
songs/
└── final/
    ├── Artist - Song [ISRC].m4a
    └── ...

reels/
└── finished/
    ├── <ISRC>_reel.mp4
    ├── <ISRC>_reel.json
    └── ...

state/
└── pipeline.db
```

Temporary processing data exists only during active/failed processing:

```text
temp/
└── <ISRC>/
```

After successful completion the temporary song directory is deleted.

---

# 26. Final reel metadata JSON

Each final reel receives a detailed JSON file containing information such as:

- ISRC
- Spotify metadata
- Spotify URL
- YouTube video ID
- YouTube URL
- YouTube title
- YouTube channel
- extracted YouTube metadata clues
- Spotify fingerprint
- YouTube fingerprint
- alignment result
- all three hook candidates
- selected hook
- lyric source
- whether lyrics were embedded
- final reel path
- final audio path
- video layout
- font

This makes the final output auditable without reopening the entire temporary workspace.

---

# 27. Installation — Windows

## 27.1 Python

Use Python 3.12 or another version supported by the installed dependencies.

Create a virtual environment:

```powershell
python -m venv venv
```

Activate it:

```powershell
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run the appropriate execution-policy command for your Windows environment or activate the environment through CMD/VS Code.

## 27.2 Install Python packages

```powershell
python -m pip install -U pip
python -m pip install -r requirements.txt
```

## 27.3 FFmpeg

Install FFmpeg and make sure both commands work:

```powershell
ffmpeg -version
ffprobe -version
```

They must be available through PATH.

For NVIDIA encoding, use an FFmpeg build containing:

```text
h264_nvenc
```

Check:

```powershell
ffmpeg -hide_banner -encoders | findstr nvenc
```

---

# 28. Spotify API setup

Create a Spotify developer application and obtain:

```text
Client ID
Client Secret
```

Set them in `.env`.

Copy `.env.example` to `.env` and replace:

```text
SPOTIPY_CLIENT_ID=YOUR_SPOTIFY_CLIENT_ID
SPOTIPY_CLIENT_SECRET=YOUR_SPOTIFY_CLIENT_SECRET
```

Do not commit `.env` to Git.

---

# 29. YouTube Data API setup

A YouTube Data API key is optional.

It is recommended because it provides better playlist-added ordering.

Set:

```text
YOUTUBE_API_KEY=YOUR_YOUTUBE_API_KEY
```

If it is missing or invalid, the pipeline falls back to playlist position ordering.

YouTube search/download itself does not depend exclusively on this API key because yt-dlp is used for search and media retrieval.

---

# 30. Recommended fully automatic configuration

For unattended processing, set:

```json
"automation": {
  "auto_youtube_selection": true,
  "auto_youtube_keywords": [
    "video song",
    "full video song"
  ],
  "auto_youtube_official_channels": [
    "Saregama Telugu",
    "Aditya Music",
    "Sony Music South",
    "Lahari Music",
    "T-Series Telugu",
    "Tips Telugu",
    "Mango Music",
    "Mango Telugu"
  ],
  "auto_youtube_channel_weight": 0.28,
  "auto_youtube_keyword_weight": 0.22,
  "auto_youtube_title_weight": 0.35,
  "auto_youtube_duration_weight": 0.10,
  "auto_youtube_result_limit": 10,

  "auto_spotify_selection": true,
  "auto_spotify_min_score": 0.55,
  "auto_spotify_movie_album_bonus": 0.20,
  "auto_spotify_ost_bonus": 0.12,
  "auto_spotify_exact_album_bonus": 0.10,

  "auto_continue": true,
  "auto_hook_selection": true,
  "auto_hook_min_score": 0.0
}
```

With this configuration there are no normal selection prompts.

The pipeline will:

```text
song 1
 ↓
automatic YouTube selection
 ↓
automatic Spotify selection
 ↓
automatic alignment
 ↓
automatic hook detection
 ↓
automatic highest-score hook
 ↓
final reel
 ↓
cleanup
 ↓
next playlist song
```

---

# 31. Safer semi-automatic configuration

If you want to supervise the two decisions that can be most sensitive, use:

```json
"automation": {
  "auto_youtube_selection": false,
  "auto_spotify_selection": false,
  "auto_continue": true,
  "auto_hook_selection": false
}
```

This automatically moves through the playlist but still lets you verify:

- exact YouTube movie video
- exact Spotify recording
- final hook

---

# 32. Running the project

Activate the virtual environment:

```powershell
.\venv\Scripts\Activate.ps1
```

Then:

```powershell
python main.py
```

Or use:

```powershell
.\run.ps1
```

The program prints its automation configuration at startup so you can verify that the intended mode is active.

---

# 33. Typical automatic terminal flow

A fully automatic run should look conceptually like:

```text
Automation: {...auto_youtube_selection: true, ...}
Playlist entries: 498

================================================================================
[1/498] Urike Urike
Playlist position: 1
================================================================================
AUTO-CONTINUE enabled: starting without confirmation.

AUTO YouTube selection:
[1] score=...
[2] score=...
...
AUTO selected YouTube: Urike Urike - Video Song ...

AUTO Spotify selection:
[1] ... album: HIT 2 (Original Motion Picture Soundtrack) ...
[2] ...
...
AUTO selected Spotify: ...

Audio alignment: offset=...s, confidence=...

THREE HOOK OPTIONS ...

AUTO selected hook [2] with highest score=...

DONE: ...\reels\finished\...
FINAL AUDIO: ...\songs\final\...

================================================================================
[2/498] Next Song
================================================================================
AUTO-CONTINUE enabled: starting without confirmation.
...
```

---

# 34. Important limitations of automation

Automatic selection is a ranking system, not a guarantee of correctness.

YouTube titles are inconsistent.

Spotify album naming is inconsistent.

Some official channels use:

```text
Video Song
Full Video
Lyric Video
Full Video Song
Official Video
```

while other official uploads may not contain any of these words.

Likewise, a soundtrack may be released on Spotify as:

```text
Movie Name
Movie Name (Original Motion Picture Soundtrack)
Song Name
Song Name (From "Movie Name")
Compilation Name
```

The scoring system therefore combines multiple signals instead of depending on one exact string.

The configurable channel allow-list is particularly important for Telugu music because it lets the automatic selector encode the user's preferred official-source ecosystem.

---

# 35. How to improve automatic YouTube selection later

The easiest future improvement is to extend:

```json
"auto_youtube_official_channels"
```

with additional verified official music channels used by the target catalogue.

You can also extend:

```json
"auto_youtube_keywords"
```

with additional official-video wording.

No code change is required for either of those changes.

---

# 36. How to tune Spotify automation

If automatic Spotify selection is too conservative:

```json
"auto_spotify_min_score": 0.50
```

If it is accepting candidates too easily:

```json
"auto_spotify_min_score": 0.65
```

If movie album identity should dominate even more:

```json
"auto_spotify_movie_album_bonus": 0.25
```

If soundtrack albums should dominate more strongly:

```json
"auto_spotify_ost_bonus": 0.18
```

If exact movie-name album matches should be strongly preferred:

```json
"auto_spotify_exact_album_bonus": 0.15
```

These values should be tuned against the actual catalogue rather than treated as universal constants.

---

# 37. How to tune hook automation

The hook detector's window is controlled by:

```json
"hook_min_seconds": 20,
"hook_target_seconds": 30,
"hook_max_seconds": 40
```

For shorter reels, lower the target.

For longer musical sections, increase it.

Automatic hook selection always chooses the highest score among the three generated candidates, subject to:

```json
"auto_hook_min_score"
```

---

# 38. Why the final reel does not use Spotify audio

Using Spotify audio directly would create a synchronization problem whenever the Spotify and movie versions differ.

The selected YouTube movie video can contain an introduction before the song.

Therefore:

```text
Spotify
= reference recording + metadata + lyrics

YouTube
= final visual + final audio + hook timeline
```

The alignment stage only connects their timelines.

---

# 39. Why lyrics can still align after a movie intro

Suppose:

```text
Spotify song starts at 0.0s
YouTube song starts at 17.4s
```

The alignment may produce:

```text
spotify_to_youtube_offset_seconds = 17.4
```

A Spotify lyric at:

```text
12.0s
```

is therefore placed around:

```text
29.4s
```

on the YouTube timeline.

The actual value is calculated from audio features rather than hardcoded.

---

# 40. Error handling philosophy

A processing error should not be mistaken for successful completion.

Therefore:

```text
FAILED
```

means the queue entry is intentionally left unfinished.

Temporary files remain available.

The terminal reports the failed stage and log path.

Only after final reel creation, final audio creation and database persistence does the item become:

```text
DONE
```

Then temporary work is deleted.

---

# 41. SpotDL failure diagnosis

If SpotDL reports:

```text
YouTube Music returned no usable results
```

that means the resolver could not find a usable matching source for the Spotify recording.

It does **not** necessarily mean the Spotify track is invalid.

This build attempts additional resolution methods and also ensures SpotDL's error file destination exists, avoiding the previous secondary error:

```text
FileNotFoundError:
... songs/downloaded/.spotdl_errors.txt
```

The full SpotDL command output is retained under:

```text
temp/<ISRC>/spotdl_stdout.log
```

until successful completion.

---

# 42. File/folder summary

```text
project/
│
├── main.py
├── config.json
├── requirements.txt
├── .env.example
├── run.ps1
├── README.md
│
├── modules/
│   ├── youtube.py
│   ├── spotify.py
│   ├── fingerprint.py
│   ├── align.py
│   ├── hooks.py
│   ├── video.py
│   └── db.py
│
├── fonts/
│   ├── NotoSerifTelugu-Medium.ttf
│   ├── NotoSerifTelugu-Regular.ttf
│   └── README.txt
│
├── temp/
├── songs/
│   └── final/
├── reels/
│   └── finished/
└── state/
    └── pipeline.db
```

---

# 43. Configuration reference

| Setting | Purpose |
|---|---|
| `playlist_url` | Input YouTube playlist |
| `temp_dir` | Temporary processing root |
| `songs_final_dir` | Final Spotify M4A directory |
| `reels_finished_dir` | Final reel directory |
| `db_path` | SQLite state database |
| `top_youtube_results` | Manual YouTube search result count |
| `top_spotify_results` | Spotify result configuration; final selector uses five |
| `spotdl_bitrate` | SpotDL bitrate mode |
| `hook_min_seconds` | Minimum hook length |
| `hook_target_seconds` | Target hook length |
| `hook_max_seconds` | Maximum hook length |
| `video_width` | Final reel width |
| `video_height` | Final reel height |
| `foreground_width` | Landscape foreground width |
| `video_fps` | Final frame rate |
| `video_crf` | CPU x264 quality |
| `cinematic_brightness` | Brightness adjustment |
| `cinematic_contrast` | Contrast adjustment |
| `cinematic_saturation` | Saturation adjustment |
| `subtitle_font_size` | Telugu subtitle size |
| `subtitle_outline` | Subtitle outline width |
| `subtitle_margin_v` | Subtitle vertical position |
| `telugu_font` | Font family name |
| `telugu_font_path` | Bundled Telugu font path |
| `video_encoder` | `auto`, `nvenc`, or `cpu` |
| `nvenc_preset` | NVIDIA encoding preset |
| `nvenc_cq` | NVIDIA constant-quality value |
| `cpu_preset` | x264 CPU preset |
| `source_crop_width` | Horizontal source crop ratio |
| `source_crop_height` | Vertical source crop ratio |
| `auto_youtube_selection` | Automatic YouTube choice |
| `auto_youtube_keywords` | Preferred video-song phrases |
| `auto_youtube_official_channels` | Preferred official music channels |
| `auto_youtube_channel_weight` | Official-channel score weight |
| `auto_youtube_keyword_weight` | Keyword score weight |
| `auto_youtube_title_weight` | Title similarity weight |
| `auto_youtube_duration_weight` | Reserved duration weight |
| `auto_youtube_result_limit` | Search breadth in automatic mode |
| `auto_spotify_selection` | Automatic Spotify choice |
| `auto_spotify_min_score` | Minimum accepted Spotify score |
| `auto_spotify_movie_album_bonus` | Movie/album preference |
| `auto_spotify_ost_bonus` | OST naming preference |
| `auto_spotify_exact_album_bonus` | Exact/contained movie album preference |
| `auto_continue` | Skip the pre-song ENTER prompt |
| `auto_hook_selection` | Automatically choose highest hook |
| `auto_hook_min_score` | Minimum acceptable automatic hook score |

---

# 44. Recommended first test

Do not immediately run all 498 entries unattended after changing configuration.

For the first test, temporarily use:

```json
"auto_youtube_selection": true,
"auto_spotify_selection": true,
"auto_continue": false,
"auto_hook_selection": true
```

This allows you to inspect one song at a time while the automatic YouTube/Spotify/hook logic is tested.

After verifying several songs, set:

```json
"auto_continue": true
```

for unattended queue processing.

---

# 45. What successful processing means

A song is considered successfully processed only when all applicable stages complete:

```text
playlist entry loaded
        ↓
YouTube source selected
        ↓
YouTube MP4 downloaded
        ↓
Spotify recording selected
        ↓
Spotify audio obtained
        ↓
final M4A metadata embedded
        ↓
Spotify + YouTube fingerprinted
        ↓
alignment accepted
        ↓
three hooks detected
        ↓
hook selected
        ↓
lyrics mapped if available
        ↓
1080x1920 reel rendered
        ↓
final reel metadata written
        ↓
SQLite updated
        ↓
temporary workspace deleted
        ↓
DONE
```

If any required stage fails, the pipeline does not falsely mark the song as complete.

---

# 46. Final design summary

The automated version is intended to operate as a long-running playlist processor:

```text
                 ┌─────────────────────────────┐
                 │     YouTube Playlist        │
                 └──────────────┬──────────────┘
                                │
                                ▼
                    oldest → newest queue
                                │
                                ▼
                    automatic/manual YouTube
                                │
                                ▼
                         official movie video
                                │
                    ┌───────────┴───────────┐
                    │                       │
                    ▼                       ▼
              video metadata          YouTube audio
                    │                       │
                    ▼                       │
             Spotify search                 │
                    │                       │
                    ▼                       │
             Spotify ranking                │
                    │                       │
                    ▼                       │
             selected recording             │
                    │                       │
                    ▼                       │
              Spotify audio                 │
                    │                       │
                    └──────────┬────────────┘
                               ▼
                         fingerprint
                               │
                               ▼
                           alignment
                               │
                               ├───────────────┐
                               │               │
                               ▼               ▼
                        Spotify lyrics    YouTube hook analysis
                               │               │
                               └───────┬───────┘
                                       ▼
                                chosen hook
                                       │
                                       ▼
                           original YouTube video
                                       │
                                       ▼
                                1080 × 1920
                                       │
                                       ▼
                            pure black background
                                       │
                                       ▼
                         centered landscape video
                                       │
                                       ▼
                       optional mapped Telugu lyrics
                                       │
                                       ▼
                             final reel + metadata
                                       │
                                       ▼
                              SQLite state saved
                                       │
                                       ▼
                              temporary files removed
                                       │
                                       ▼
                                NEXT SONG
```

The central invariant is:

> **Spotify identifies and annotates the song; YouTube supplies the final movie-video timeline and audio.**

That invariant is what prevents a Spotify/YouTube intro mismatch from corrupting hook selection and lyric timing.
