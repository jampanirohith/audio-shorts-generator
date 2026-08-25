# Audio Shorts Generator
 
Turns a youtube video song into a lyrical short-form vertical video, ready for YouTube Shorts, Instagram Reels, and Facebook Reels.

----
 
# Set-Up

## Setting Up Environment
```bash
python -m venv venv 
venv\Scripts\activate
```


## Checking FFmpeg
You also need **ffmpeg** on your PATH (not pip-installable):
- Windows: download from ffmpeg.org, add the `bin` folder to PATH
- Ubuntu: `sudo apt install ffmpeg`
- Mac: `brew install ffmpeg`
```bash
ffmpeg -version
ffprobe -version
```


## Install Packages
```bash
pip install -r requirements.txt
```
 


## Project layout




## Pipeline

```text
YouTube playlist
    ↓
Load playlist + queue/state
    ↓
YouTube search
    ↓
Select movie video
    ↓
Download YouTube MP4
    ↓
Extract YouTube metadata
    ↓
Spotify search
    ↓
Rank Spotify recordings
    ↓
Select recording
    ↓
Download Spotify audio + lyrics (if available)
    ↓
Fingerprint Spotify + YouTube audio
    ↓
Align Spotify timeline → YouTube timeline
    ↓
Detect 3 hook candidates from YouTube audio
    ↓
Select hook
    ↓
Map Spotify lyric timestamps → YouTube timeline
    ↓
Render 1080×1920 reel
    ├── black background
    ├── centered landscape video
    ├── cinematic adjustment
    ├── optional Telugu lyrics
    └── original YouTube audio
    ↓
Save reel + metadata
    ↓
Save Spotify M4A
    ↓
Update SQLite
    ↓
Delete temporary files
    ↓
Next song
```
---
## Source Roles

| Source | Used for |
|---|---|
| **YouTube** | Movie video, final reel audio, hook detection |
| **Spotify** | Recording identification, metadata, artwork, optional synced lyrics |

```text
Spotify audio ──────┐
                    ├── fingerprint + alignment ──→ timestamp mapping
YouTube audio ──────┘

Spotify lyrics
      ↓
YouTube timeline
      ↓
Final reel = YouTube video + YouTube audio + mapped lyrics
```

The alignment accounts for movie intros, logos, dialogue, silence, alternate edits, fades, and other timing differences. fileciteturn0file0L114-L155

## Queue

```text
Playlist
  ↓
oldest added
  ↓
next
  ↓
...
  ↓
newest added
```

When `YOUTUBE_API_KEY` is available, playlist-added timestamps determine order. Otherwise, playlist position is used. Queue state is stored in SQLite. fileciteturn0file0L159-L180

## Automation

```json
"automation": {
  "auto_youtube_selection": true,
  "auto_spotify_selection": true,
  "auto_continue": true,
  "auto_hook_selection": true
}
```

These switches control:

- YouTube source selection
- Spotify recording selection
- queue continuation
- hook selection

## YouTube Selection

Search results are ranked using:

- title similarity
- video-song keywords
- official-channel match
- duration when available

Typical keywords:

```json
"auto_youtube_keywords": [
  "video song",
  "full video song"
]
```

Official-channel allow-list:

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

The selector chooses the highest-scoring result. fileciteturn0file0L223-L307

## YouTube Metadata

After selection, `yt-dlp` extracts:

- title
- uploader/channel
- description
- duration
- upload date
- album
- artist candidates
- movie candidates

These fields are used for Spotify matching. fileciteturn0file0L322-L339

## Spotify Selection

Candidates are collected from:

```text
song + artist
song + artist candidate
song + movie
song + album
song
```

Candidates are ranked by:

1. title similarity
2. artist similarity
3. movie/album similarity
4. duration similarity
5. movie-album match
6. OST naming
7. exact/contained movie-album match

Default bonuses:

```json
"auto_spotify_movie_album_bonus": 0.20,
"auto_spotify_ost_bonus": 0.12,
"auto_spotify_exact_album_bonus": 0.10,
"auto_spotify_min_score": 0.55
```

The final candidate list is limited to five tracks. fileciteturn0file0L375-L483

## Duplicate Prevention

```text
YouTube video ID
      ↓
youtube_done check

Spotify ISRC
      ↓
songs check
```

A previously finalized YouTube video or Spotify recording is skipped. fileciteturn0file0L487-L505

## Temporary Files

```text
temp/
├── _youtube_downloads/<youtube-id>/
└── <ISRC>/
    ├── fingerprints
    ├── WAVs
    ├── alignment data
    ├── hook previews
    ├── subtitles
    └── logs
```

Successful jobs delete their temporary directory. Failed jobs retain it for debugging/resume. fileciteturn0file0L509-L543

## Spotify Download

Primary resolver: SpotDL 4.5.2.

Fallback order:

```text
SpotDL + synced lyrics
        ↓
SpotDL + synced lyrics (alternate mode)
        ↓
SpotDL audio-only
        ↓
SpotDL audio-only (alternate mode)
        ↓
yt-dlp fallback
```

Lyrics are optional. If unavailable, no lyrics are generated or guessed. fileciteturn0file0L547-L580

## Final Spotify Audio

Saved to:

```text
songs/final/
```

The final M4A contains available metadata, artwork, and synced lyrics. No separate final artwork/LRC file is required. fileciteturn0file0L586-L608

## Fingerprinting & Alignment

Both recordings are analyzed:

```text
Spotify audio ──→ fingerprint
YouTube audio ──→ fingerprint
                    ↓
                 alignment
                    ↓
        Spotify → YouTube offset
```

Features include chroma, onset information, beat timing, beat intervals, and tempo. Alignment uses multiple anchors, beat agreement, median offset, and outlier rejection. fileciteturn0file0L614-L684

## Hook Detection

Hook detection runs on **YouTube audio only**.

```json
"hook_min_seconds": 20,
"hook_target_seconds": 30,
"hook_max_seconds": 40
```

The detector uses:

- RMS energy
- onset strength
- beat density
- tempo

Three distinct high-scoring candidates are generated. fileciteturn0file0L696-L723

Automatic mode:

```json
"auto_hook_selection": true,
"auto_hook_min_score": 0.0
```

The highest-scoring candidate is selected. fileciteturn0file0L727-L751

## Reel Composition

Output:

```text
1080 × 1920
```

Layout:

```text
┌──────────────────────────┐
│                          │
│                          │
│     LANDSCAPE VIDEO      │
│        CENTERED          │
│                          │
│                          │
└──────────────────────────┘
```

- black portrait canvas
- centered landscape source
- no stretching
- no mirrored/blurred background
- small source crop
- cinematic adjustment
- optional Telugu subtitles
- original YouTube audio

Default crop:

```json
"source_crop_width": 0.96,
"source_crop_height": 0.92
```

Default visual adjustment:

```json
"cinematic_brightness": 0.025,
"cinematic_contrast": 1.08,
"cinematic_saturation": 1.04
```

fileciteturn0file0L776-L840

## Telugu Lyrics

Lyrics flow:

```text
Spotify lyric timestamps
        ↓
Spotify → YouTube offset
        ↓
YouTube timestamps
        ↓
Selected hook
        ↓
ASS subtitles
        ↓
FFmpeg
```

Font:

```text
Noto Serif Telugu
```

If synced lyrics are unavailable, the reel has no lyric layer. fileciteturn0file0L846-L881

## Final Reel Audio

```text
YouTube video
+
YouTube original audio
+
optional mapped Spotify lyrics
```

Spotify audio is never substituted into the reel. fileciteturn0file0L885-L899

## Encoding

```text
video_encoder = auto
```

```text
NVENC available → h264_nvenc
NVENC unavailable → libx264
```

Other processing remains CPU/network based. fileciteturn0file0L903-L950

## State & Resume

Database:

```text
state/pipeline.db
```

Main states:

```text
DONE
SKIPPED
FAILED
DUPLICATE
```

Failed jobs remain unfinished and retain temporary files. Successful jobs are marked `DONE` only after final outputs and database state are saved. fileciteturn0file0L956-L1030

## Output

```text
songs/
└── final/
    └── Artist - Song [ISRC].m4a

reels/
└── finished/
    ├── <ISRC>_reel.mp4
    └── <ISRC>_reel.json

state/
└── pipeline.db
```

fileciteturn0file0L1035-L1062

## Installation — Windows

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1

python -m pip install -U pip
python -m pip install -r requirements.txt

ffmpeg -version
ffprobe -version
```

For NVIDIA encoding:

```powershell
ffmpeg -hide_banner -encoders | findstr nvenc
```

fileciteturn0file0L1094-L1142

## API Configuration

`.env`:

```text
SPOTIPY_CLIENT_ID=YOUR_SPOTIFY_CLIENT_ID
SPOTIPY_CLIENT_SECRET=YOUR_SPOTIFY_CLIENT_SECRET
YOUTUBE_API_KEY=YOUR_YOUTUBE_API_KEY
```

`YOUTUBE_API_KEY` is optional; without it, playlist position is used for ordering. fileciteturn0file0L1146-L1182

## Fully Automatic Configuration

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

fileciteturn0file0L1186-L1225

## Run

```powershell
.\venv\Scripts\Activate.ps1
python main.py
```

or:

```powershell
.\run.ps1
```

## File Structure

```text
project/
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

## Successful Processing

```text
Playlist entry
    ↓
YouTube selected
    ↓
YouTube MP4 downloaded
    ↓
Spotify recording selected
    ↓
Spotify audio obtained
    ↓
Metadata embedded
    ↓
Spotify + YouTube fingerprinted
    ↓
Timeline aligned
    ↓
3 hooks detected
    ↓
Hook selected
    ↓
Lyrics mapped if available
    ↓
1080×1920 reel rendered
    ↓
Metadata written
    ↓
SQLite updated
    ↓
Temporary files removed
    ↓
DONE
```

## Core Design

```text
Spotify
= recording identification + metadata + lyrics

YouTube
= final movie video + final audio + hook timeline

Alignment
= connects the two timelines

Final reel
= YouTube video + YouTube audio + optional mapped lyrics
```

**Core invariant:** Spotify identifies and annotates the recording; YouTube supplies the final movie-video timeline and audio. fileciteturn0file0L1721-L1804
