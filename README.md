# Audio Shorts Generator — Final 16:9 Spotify-Master Pipeline

## What it does

The application reads a **Spotify playlist**, analyzes each Spotify recording, automatically selects the best hook, searches YouTube only after the hook is known, downloads a YouTube video for visuals, synchronizes the two recordings, and renders a **16:9** reel using:

- **Video:** YouTube visual footage
- **Audio:** Spotify recording
- **Lyrics:** Spotify LRC from LibreLyrics

Spotify is the musical truth; YouTube is the visual truth.

## Setup

1. Create and activate your Python virtual environment.
2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Install FFmpeg and FFprobe and make both available on `PATH`.
4. Copy `.env.example` to `.env`.
5. Put the Spotify credentials in `.env`:

```text
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_SP_DC=...
```

6. Put your Spotify playlist URL in `config.json`.
7. Put the desired lyric font in `fonts/` and point `lyrics_fontfile` to it.
8. Run:

```powershell
python main.py
```

## Normal processing order

```text
Spotify playlist
 → exact Spotify track
 → Spotify audio
 → Spotify LRC
 → whole-song hook analysis
 → automatic best hook
 → YouTube search
 → candidate display / configured selection
 → YouTube visual download
 → audio-envelope synchronization
 → Spotify hook mapped to YouTube timeline
 → 16:9 rendering
 → centered Spotify lyrics
 → validation
 → canonical Spotify song
 → database completion
```

## Important behavior

- `main.py` processes the queue automatically.
- `continue_on_error=true` skips a failed track for the current run and continues.
- Failed stages retain recoverable temporary work and the permanent serial is not reused.
- A later run can resume an existing serial.
- YouTube does **not** participate in hook selection.
- The final reel is always 16:9.
- Final reel audio is Spotify.
- Final reel lyrics are Spotify LRC.
- YouTube LRC/translated lyrics are not used.
- YouTube candidate URLs are printed in the terminal.
- Spotify and final-file links are printed as clickable `file:///...`/web URLs where applicable.
- Lyrics are centered and long lines wrap into a second line instead of leaving the video.
- Lyric text is written through FFmpeg `textfile` inputs to avoid apostrophe/filter-injection failures.
- The configured font is checked before rendering, avoiding unnecessary Fontconfig dependency on Windows.

## Manual reselection

`reselect.py` ignores automatic YouTube selection and always asks you to choose a YouTube candidate:

```powershell
python reselect.py --serial 0001
```

It reuses the Spotify hook/audio/LRC and only replaces the YouTube visual source, then re-synchronizes and re-renders.

## Credentials and security

Never commit `.env`. It is ignored by Git. The application does not print the values of Spotify credentials.

## Output

```text
songs/      permanent canonical Spotify-side song files
reels/      final 16:9 MP4 reels + metadata JSON
temp/       recoverable per-serial workspaces
state/      SQLite queue/reel/song databases
fonts/      lyric fonts
```


## Spotify playlist authorization (2026 Web API)

Spotify's February 2026 Web API changes require playlist-item access through a user-authorized token for playlists owned by the current user or playlists where the user is a collaborator. This project therefore uses Authorization Code + PKCE for playlist access instead of Client Credentials. The playlist endpoint is `/v1/playlists/{id}/items`, not the deprecated `/tracks` endpoint.

Set `SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback` in `.env` and add exactly that URI to the Redirect URIs for the Spotify developer application. On the first run, a browser authorization page opens; after approval, the refresh token is cached in `state/spotify_oauth.json`. Do not commit that file.


## YouTube search query keyword

The automatic YouTube search appends `youtube_search_keyword` from `config.json`. Change it whenever you want to alter the final search term. For example:

```json
"youtube_search_keyword": "official music video"
```

Set it to an empty string to omit the extra keyword.

## Manual YouTube reselection

`reselect.py` asks for the exact YouTube search query instead of deriving the query from Spotify metadata. The command accepts either `python reselect.py 1` or `python reselect.py --serial 1`.

## Lyric timing

Lyrics with the same/near-identical LRC timestamp are grouped into one centered multiline block instead of being rendered on top of one another. `lyrics_max_display_seconds` limits how long a lyric remains visible during long LRC gaps, and `lyrics_merge_timestamp_tolerance_seconds` controls timestamp grouping.
### Lyric spacing and fade controls

The final 16:9 reel renders Spotify LRC lyrics as centered multiline blocks. The following settings control their appearance in `config.json`:

- `lyrics_line_spacing`: extra pixel spacing between lines. Negative values reduce the font's natural line gap; the default is `-12`.
- `lyrics_fade_in_seconds`: fade-in duration for each lyric block. Set to `0` to disable fade-in.
- `lyrics_fade_out_seconds`: fade-out duration for each lyric block. Set to `0` to disable fade-out.

If a lyric interval is shorter than the requested fade duration, the renderer automatically shortens the fade so the fade-in and fade-out do not overlap.

