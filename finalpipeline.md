# Audio Shorts Generator — Final Ultra-Detailed Step-by-Step Pipeline

## 0. Core goal

The pipeline processes songs from a Spotify playlist and creates validated **16:9 short-form music reels**.

Source-of-truth separation:

- **Spotify:** song/recording identity, ISRC, metadata, artwork, audio, LRC, and complete-song hook analysis.
- **YouTube:** visual/video source only.
- **Synchronization:** maps the Spotify-selected hook timeline onto the YouTube visual timeline.
- **Renderer:** combines YouTube visuals + Spotify audio + Spotify LRC + cinematic processing.

Final flow:

```text
Spotify playlist
 → Spotify track/metadata/ISRC
 → Spotify audio + artwork + LRC
 → complete-song advanced hook analysis
 → automatic best-hook selection
 → YouTube search
 → candidate ranking/display/selection
 → YouTube video download
 → temporary YouTube audio extraction
 → Spotify↔YouTube synchronization
 → map Spotify hook to YouTube timeline
 → extract/crop visual
 → Spotify hook audio
 → Spotify LRC relative timing
 → centered/wrapped lyrics
 → cinematic processing
 → 16:9 final reel
 → validate reel
 → create permanent canonical song
 → save permanent assets + databases
 → mark playlist item FINISHED
```

## 1. Configuration

Load and validate `config.json` before processing.

Configuration controls:

- Spotify playlist URL
- YouTube selection mode (`automatic` / `manual`)
- output directories
- temporary job directory
- permanent songs directory
- reels directory
- database paths
- preferred hook duration
- hook-analysis parameters
- synchronization parameters
- lyric rendering parameters
- font parameters
- cinematic/video settings
- error/continuation behavior
- supported non-secret LibreLyrics settings

Create all required directories before invoking external tools.

Configuration errors should be detected before expensive processing begins.

## 2. Credentials

Secrets belong in `.env`, not `config.json` or source code.

Use the configured names for:

```text
SPOTIFY_CLIENT_ID
SPOTIFY_CLIENT_SECRET
SPOTIFY_SP_DC
```

Never print credentials, write them to normal logs, or commit `.env`.

Validate required credentials at startup.

## 3. LibreLyrics

LibreLyrics supplies the Spotify-side LRC.

Its integration must match the **installed version**. Do not assume unsupported commands/API arguments.

Do not assume:

```text
librelyrics --config
python -m librelyrics
```

are valid.

Use the installed CLI/API and its actual configuration mechanism. The Spotify plugin requires `sp_dc`.

If LibreLyrics reports `No lyrics available`, treat that as a recoverable lyrics-unavailable condition. Continue with audio-only hook analysis when the rest of the job can proceed.

## 4. Spotify playlist loading

1. Connect to Spotify.
2. Read the configured playlist.
3. Synchronize playlist entries with the local database.
4. Preserve queue order.
5. Find the first unfinished entry.
6. Process sequentially.

Already-finished entries should not be unnecessarily reprocessed.

## 5. Playlist identity

Use:

```text
playlist_id + spotify_id
```

as the playlist-entry identity.

A temporary removal/re-addition must not create a duplicate entry.

Synchronize current:

- playlist order
- title
- URL
- last-seen information

while retaining permanent identity.

## 6. Permanent serials

Every processing job receives an atomic serial:

```text
0001
0002
0003
```

A consumed serial is **never reused**, including after:

- download failure
- LRC failure
- hook-analysis failure
- YouTube failure
- synchronization failure
- rendering failure
- validation failure
- restart/interruption

A failed playlist item may return to `YET_TO_START`, but its serial remains consumed.

## 7. Temporary job directory

Create:

```text
temp/<serial>/
```

It can contain:

- Spotify audio
- Spotify LRC
- metadata
- artwork
- YouTube MP4
- temporary YouTube audio
- hook-analysis data
- synchronization data
- render intermediates
- logs/error diagnostics

The workspace is isolated per serial.

## 8. Spotify metadata

Obtain and retain:

- Spotify track ID
- ISRC
- title
- artists
- album
- album artist where available
- duration
- Spotify URL
- artwork
- other useful metadata

Spotify is authoritative for recording identity.

## 9. ISRC duplicate handling

Use the Spotify recording's ISRC for song-level duplicate detection.

Keep playlist identity and recording identity separate.

If the current recording must replace an existing permanent recording, keep replacement simple:

```text
select current
 → delete previous associated permanent assets
 → remove/update previous database record
 → save current recording
```

Do not build a complicated merge mechanism.

## 10. Spotify audio download

Use the project's spotDL-based Spotify download.

Spotify audio is the musical master and is used for:

- complete-song hook analysis
- final reel audio
- synchronization reference
- permanent canonical song

Before invoking spotDL:

1. create the temporary directory;
2. create parents for archive/error files;
3. invoke spotDL in a controlled way.

Avoid duplicate Spotify-client initialization that causes:

```text
SpotifyError: A spotify client has already been initialized
```

Avoid nested Rich live displays that cause:

```text
LiveError: Only one live display may be active at once
```

Use controlled subprocess isolation where appropriate.

## 11. Spotify LRC

Acquire the original Spotify-side LRC through LibreLyrics.

When usable LRC exists, it is used for:

- lyric-aware hook analysis
- final reel lyrics
- permanent lyric asset

Do not automatically translate or replace it with YouTube/English/other translated lyrics.

If LRC is unavailable, continue with audio-only hook analysis and do not invent lyric timing.

## 12. LRC validation

Validate:

- file exists
- file is readable
- timestamps parse
- timestamps are usable/increasing
- lyric text is present
- timestamps are reasonably compatible with song duration

Malformed entries should be handled without corrupting the entire job.

## 13. Hook-analysis source

Hook analysis uses:

```text
Spotify audio
+
Spotify LRC when available
```

YouTube must not influence hook selection.

YouTube is deliberately processed later.

## 14. Analyze the entire song

Analyze the complete Spotify recording.

Do not only inspect:

- opening
- chorus
- loudest peak
- ending

Possible strong hooks include:

- second chorus
- late chorus
- bridge
- instrumental hook
- repeated refrain
- final climax
- memorable lyrical section

## 15. Candidate generation

Generate many overlapping candidates throughout the entire song.

Preferred duration:

```text
35–60 seconds
```

This is a preference, not a hard constraint.

Generate several durations around the preferred range:

- shorter candidates
- preferred-length candidates
- slightly longer candidates

A naturally excellent 32-second section can beat a mediocre 55-second section.

## 16. Musical energy

For each candidate evaluate:

- average energy
- sustained energy
- peaks
- energy trajectory
- energy variance
- dynamics

High energy can indicate a chorus/drop/climax, but energy alone must not select the winner.

## 17. Rhythmic features

Evaluate:

- onset strength
- onset density
- rhythmic activity
- beat density

Use these together with musical structure and energy.

## 18. Build-up and payoff

Reward useful structures such as:

```text
build-up → anticipation → payoff
```

Do not require this structure for every song.

## 19. Musical coherence

Reward candidates that sound like deliberate musical phrases.

Penalize:

- mid-phrase starts
- mid-phrase endings
- awkward transitions
- severe silence
- unrelated adjacent material

## 20. Repeated musical structure

Detect repeated musical sections.

For example:

```text
Verse → Chorus → Verse → Chorus
```

Repeated recognizable sections receive a strong boost because they are likely memorable and intentional.

## 21. Lyric analysis

When LRC exists, evaluate:

- lyric density
- repeated lines
- repeated phrases
- refrain frequency
- memorable lines
- lyrical climax
- phrase completeness
- lyric continuity
- lyric/music intensity alignment

Lyrics influence hook scoring but do not replace audio analysis.

## 22. Hook scoring hierarchy

The intended priority is:

```text
1. Musical quality
2. Lyric repetition/memorability when available
3. Musical repetition/recognizable structure
4. Music + lyric overlap
5. Boundary quality
6. Duration suitability
```

Audio remains the foundation.

## 23. Combined candidate score

Each candidate can combine:

```text
energy
+ sustained energy
+ peaks
+ onset activity
+ build-up
+ payoff
+ dynamics
+ beat density
+ musical coherence
+ musical repetition
+ structural repetition
+ lyric repetition
+ lyric memorability
+ lyrical climax
+ music/lyric overlap
+ start-boundary quality
+ end-boundary quality
+ engaging-lead-in quality
+ duration suitability
```

Weights should remain tunable. Features unavailable for a song should be omitted/neutralized rather than inventing data.

## 24. Candidate deduplication

After scoring:

```text
many candidates
 → rank
 → remove heavily overlapping/near-duplicate candidates
 → retain strong diverse candidates
```

This prevents the top results from being the same hook shifted by only a few seconds.

## 25. Boundary quality

Ideal boundaries consider:

```text
beat
+
musical phrase
+
lyric phrase
```

when lyrics exist.

Do not blindly snap to the nearest beat if that damages the musical or lyric phrase.

## 26. Engaging lead-in

A small lead-in may be added before the natural hook boundary when it improves the reel.

Conceptually:

```text
short lead-in → hook arrival
```

The lead-in must remain musically relevant and must not:

- include unrelated content
- remove the important hook
- break lyric timing
- create awkward pre-roll

## 27. End boundary

Prefer:

- musical phrase ending
- lyric phrase ending
- beat ending
- musical resolution

Avoid:

- mid-word cuts
- mid-lyric cuts
- obvious transition cuts
- abrupt/unresolved endings

## 28. Automatic hook selection

After:

1. candidate generation
2. feature extraction
3. scoring
4. deduplication
5. boundary adjustment
6. validation

select the highest-quality valid hook automatically.

Record:

- original boundaries
- adjusted reel boundaries
- duration
- score
- scoring components
- lyric availability
- relevant analysis metadata

## 29. Hook validation

Validate:

- duration
- valid audio region
- natural start
- natural end
- no severe silence
- no mid-word cut
- no broken musical phrase
- acceptable structure
- no materially better duplicate

If the best candidate fails validation, test the next candidate.

## 30. YouTube search timing

Only after the Spotify hook has been selected:

```text
Spotify selection
 → Spotify audio/LRC
 → complete-song hook analysis
 → best hook
 → YouTube search
```

This avoids unnecessary YouTube processing.

## 31. YouTube search

Search using clean Spotify metadata:

- song title
- primary artist
- useful album/movie information

Avoid noisy queries containing every unrelated metadata field.

## 32. YouTube ranking

Use tolerant ranking based on:

- title similarity
- artist similarity
- movie/album similarity
- official/trusted channel
- video-song relevance
- version compatibility
- duration similarity
- views/popularity

Strongly penalize obvious wrong content:

- reaction
- review
- interview
- karaoke
- unrelated compilation
- unrelated song
- inappropriate fan edit
- unrelated short/reupload

Do not reject a correct result because one metadata field differs.

## 33. YouTube candidates in terminal

Display candidates with:

```text
[1] Title
    Channel : ...
    Views   : ...
    URL     : https://www.youtube.com/watch?v=...

[2] Title
    Channel : ...
    Views   : ...
    URL     : ...

[3] ...
```

Also display:

- selected YouTube URL
- original playlist video/reference URL when applicable

This makes source selection visible and auditable.

## 34. YouTube selection modes

If configured:

```text
automatic
```

select the best acceptable ranked candidate.

If configured:

```text
manual
```

show candidates and let the user choose.

## 35. `reselect.py`

`reselect.py` is always manual regardless of automatic configuration.

It must:

1. search YouTube;
2. display candidates;
3. display metadata;
4. display URLs;
5. ask for a selection;
6. continue with the selected source.

## 36. YouTube download

After selection:

```text
YouTube video download: STARTING
```

Download with yt-dlp.

The terminal should show major events rather than excessive low-level progress.

On completion:

```text
YouTube video download: COMPLETE
```

## 37. YouTube visual-only rule

YouTube provides:

- visual frames
- visual timeline
- temporary synchronization audio

YouTube does not provide:

- final audio
- hook decision
- final lyric source

## 38. Temporary YouTube audio

Extract an analysis copy of YouTube audio.

It may be:

- mono
- downsampled
- lower-resolution

because it is only for synchronization.

## 39. Synchronization objective

Find:

```text
where the Spotify recording occurs inside the YouTube recording
```

Do not assume:

```text
Spotify 0s = YouTube 0s
```

## 40. Synchronization algorithm

Use cross-correlation of audio envelopes.

Conceptually:

```text
Spotify audio
 → mono
 → downsample
 → energy envelope

YouTube audio
 → mono
 → downsample
 → energy envelope

Spotify envelope
 ↕
cross-correlation
 ↕
YouTube envelope
 ↓
global offset
 ↓
confidence
 ↓
local hook verification
```

## 41. Envelope construction

For each audio source:

1. decode;
2. convert to mono;
3. downsample;
4. calculate short-time RMS/energy or equivalent;
5. smooth if useful;
6. normalize.

Normalization reduces the influence of absolute loudness differences.

## 42. Whole-song synchronization

Cross-correlate the normalized envelopes across the song.

The strongest reliable alignment gives the coarse global offset.

Do not assume both recordings start together.

## 43. Synchronization confidence

Record:

```text
Offset     : ...
Confidence : ...
```

Confidence should indicate how clearly the selected alignment beats alternatives.

A low-confidence result should be reported rather than silently producing potentially wrong visuals.

## 44. Repeated-section ambiguity

Repeated choruses can create multiple similar correlation peaks.

Therefore do not blindly choose an arbitrary correlation peak.

Use the global result together with the predicted hook region.

## 45. Local hook verification

After coarse synchronization:

```text
global offset
 → predicted YouTube hook region
 → local/higher-resolution comparison
 → final visual alignment
```

This improves reliability around the actual selected hook.

## 46. Map Spotify hook to YouTube

If:

```text
Spotify hook = 134.158s → 175.187s
offset = +6.500s
```

the corresponding YouTube visual region is approximately:

```text
140.658s → 181.687s
```

The exact implementation must maintain one consistent offset sign convention.

Spotify remains the master timeline.

## 47. Final audio

The final reel audio is the Spotify hook.

Remove/disable YouTube audio from the final output.

This guarantees that Spotify LRC timestamps and final audio remain synchronized.

## 48. Extract/crop visual

Use the synchronized YouTube timestamps to extract the visual section corresponding to the Spotify hook.

The visual duration must match the final audio/reel duration.

## 49. Final aspect ratio

The final output is:

```text
16:9
```

Do not convert it to 9:16.

Resolution may be configurable while preserving the 16:9 target.

## 50. Convert LRC timestamps to reel-relative timestamps

For every lyric timestamp:

```text
relative_time = lyric_time - final_reel_start
```

Example:

```text
Reel start = 134.158s
Lyric      = 137.200s
Relative   = 3.042s
```

Only lyric events belonging to the reel should be rendered.

## 51. Lyric segment construction

For each selected lyric:

- determine start;
- determine end using the next lyric/suitable reel boundary;
- clamp to reel duration;
- preserve Spotify LRC timing.

Do not invent synchronization.

## 52. Lyric placement

Lyrics must be:

- horizontally centered;
- vertically centered or in the intended central safe area;
- completely inside the video;
- readable against the video.

Center the **whole lyric block**, not only its first line.

## 53. Long lyric lines

Wrap long lyrics to additional lines.

The renderer must calculate:

- maximum width
- font metrics
- line breaks
- line spacing
- total block height
- centered position

Never allow lyrics to extend outside the frame.

## 54. Lyric typography

Make configurable:

- font file
- font size
- weight/style where supported
- stroke width
- shadow
- maximum width
- line spacing
- horizontal alignment
- vertical position

Use explicit `.ttf`/`.otf` files in the project's `fonts/` directory where practical.

## 55. Font validation

Before rendering, verify the configured font exists.

If not:

```text
ERROR: configured lyric font not found
```

Do not rely on the host's Fontconfig setup when an explicit font file can be supplied.

## 56. Unicode

The font must contain the glyphs required by the Spotify LRC.

Missing glyphs should be detected/reported where practical rather than silently producing boxes.

## 57. FFmpeg lyric escaping

All lyric text must be safely escaped before entering FFmpeg filters.

Pay particular attention to:

- apostrophes
- quotes
- colons
- brackets
- commas
- backslashes
- Unicode
- filter-sensitive characters

Never inject raw lyric text into a filter graph.

A lyric containing an apostrophe can otherwise produce:

```text
No such filter
```

Use robust text-file/drawtext handling or correct escaping.

## 58. Cinematic processing

Cinematic settings remain configurable.

Example:

```json
{
  "cinematic_enabled": true,
  "cinematic_brightness": 0.0,
  "cinematic_contrast": 1.1,
  "cinematic_saturation": 1.03,
  "cinematic_gamma": 1.02,
  "cinematic_sharpen": 0.3
}
```

Do not hard-code values intended to be configurable.

## 59. Rendering composition

Logical composition:

```text
YouTube visual
+
Spotify audio
+
Spotify LRC
+
cinematic processing
=
16:9 final reel
```

YouTube audio must not remain in the final file.

## 60. Rendering order

Logical order:

1. obtain synchronized YouTube visual;
2. extract/crop visual;
3. apply cinematic processing;
4. prepare Spotify hook audio;
5. prepare Spotify LRC lyric layer;
6. render centered/wrapped lyrics;
7. encode final 16:9 reel.

The implementation may combine operations for efficiency.

## 61. Final reel validation

Do not rely only on FFmpeg exit code.

Validate:

- output exists;
- file size is reasonable;
- file is readable;
- video stream exists;
- audio stream exists;
- duration is correct;
- audio duration is correct;
- video duration is correct;
- aspect ratio is 16:9;
- resolution is correct;
- final audio is present;
- YouTube audio is not accidentally retained;
- lyric rendering completed;
- output can be probed/opened.

Only a validated reel is eligible for completion.

## 62. Canonical song creation timing

Do **not** create the permanent canonical song immediately after download.

Required logical sequence:

```text
temporary Spotify assets
 → analysis
 → hook selection
 → YouTube selection
 → synchronization
 → reel render
 → reel validation
 → canonical song creation
 → permanent song storage
 → database updates
 → temporary cleanup
```

This keeps Spotify audio, artwork, metadata, and LRC available until the complete job succeeds.

## 63. Permanent canonical song

After successful reel validation, save the permanent Spotify-side song assets:

- audio
- metadata
- artwork
- LRC
- Spotify identifiers
- ISRC
- relevant hook/synchronization metadata

Store them in the configured songs directory.

## 64. Database responsibilities

### `playlist.db`

Tracks:

- playlist
- Spotify playlist entry
- Spotify track ID
- playlist order
- current metadata
- status
- permanent serial
- last-seen information
- failure information where implemented

### `songs.db`

Tracks permanent canonical songs:

- serial
- Spotify track ID
- ISRC
- metadata
- permanent audio path
- artwork path
- LRC path
- YouTube video ID where relevant
- hook metadata
- synchronization metadata

### `reel.db`

Tracks rendered reels:

- serial
- reel path
- hook start
- hook end
- duration
- hook score
- lyric source
- YouTube source
- synchronization offset
- synchronization confidence
- rendering information
- validation status

## 65. Completion order

After permanent files exist:

1. save/update `songs.db`;
2. save/update `reel.db`;
3. validate permanent files and database relationships;
4. clean temporary assets;
5. finally set:

```text
playlist.db → FINISHED
```

`FINISHED` is the final completion state.

## 66. Failure behavior

On any major failure:

- show the exact stage;
- show the real underlying exception;
- record useful diagnostics;
- never mark `FINISHED`;
- keep the serial permanently consumed;
- clean temporary assets according to policy;
- reset to `YET_TO_START` when configured.

Examples:

```text
ERROR: Spotify audio download failed
ERROR: Spotify LRC unavailable
ERROR: Hook analysis failed
ERROR: YouTube search failed
ERROR: YouTube download failed
ERROR: Synchronization failed
ERROR: Rendering failed
ERROR: Final validation failed
```

## 67. Continue-on-error

If:

```text
continue_on_error = true
```

then:

```text
error
 → display exact error
 → record failure
 → skip current track
 → next playlist track
```

If false:

```text
error
 → display exact error
 → stop queue
```

## 68. Manual Continue / Skip / Stop

Where manual intervention is requested, expose:

```text
[1] Continue
[2] Skip
[3] Stop
```

This avoids forcing a full restart.

## 69. Reuse completed stages

Do not destroy or repeat valid expensive work unnecessarily.

For example:

```text
Spotify audio READY
Spotify LRC READY
Hook READY
YouTube FAILED
```

should not require Spotify redownload if those artifacts remain valid.

Use stage-aware state and validate cached artifacts before reuse.

## 70. Caching

Cache successful results where safe:

- Spotify metadata
- Spotify track ID
- ISRC
- Spotify audio
- Spotify LRC
- artwork
- hook-analysis result
- YouTube selection
- YouTube metadata
- synchronization result

Avoid unnecessary repeated API/network calls.

## 71. Performance

Spotify-side processing should happen before YouTube processing.

This reduces:

- unnecessary YouTube bandwidth;
- unnecessary downloads;
- unnecessary video decoding;
- wasted work on failed songs.

Hook analysis should reuse extracted audio features rather than decoding the same audio separately for every candidate.

Synchronization should use:

```text
coarse downsampled whole-song envelope
+
local higher-resolution hook verification
```

rather than expensive full-resolution cross-correlation over everything.

## 72. Terminal output

Show major events, not every internal operation.

Recommended sequence:

```text
Spotify playlist loaded
Track selected
Spotify metadata
Spotify audio STARTING
Spotify audio COMPLETE
Spotify LRC FOUND / NOT AVAILABLE
Hook analysis STARTING
Best hook
Hook analysis COMPLETE
YouTube search STARTING
YouTube candidates + URLs
Selected YouTube
YouTube download STARTING
YouTube download COMPLETE
Synchronization STARTING
Offset
Confidence
Synchronization COMPLETE
Rendering STARTING
Rendering COMPLETE
Validation PASSED
Permanent song SAVED
Reel SAVED
Track FINISHED
Moving to next track
```

Do not expose secrets.

## 73. Example successful run

```text
============================================================
TRACK [1] : Urike Urike
============================================================

Spotify:
  Title  : Urike Urike
  Artist : ...
  ISRC   : ...
  URL    : https://open.spotify.com/track/...

Spotify audio: STARTING
Spotify audio: COMPLETE
Spotify LRC: FOUND

Hook analysis: STARTING
  Candidates analyzed: ...
  Best hook: 134.158s → 175.187s
  Duration: ...
  Score: ...
Hook analysis: COMPLETE

YouTube search: STARTING

YouTube candidates:
  [1] ...
      URL: https://www.youtube.com/watch?v=...
  [2] ...
      URL: ...
  [3] ...
      URL: ...

Selected YouTube:
  URL: ...

YouTube download: STARTING
YouTube download: COMPLETE

Synchronization: STARTING
  Offset     : +6.500s
  Confidence : 0.91
Synchronization: COMPLETE

Rendering: STARTING
Rendering: COMPLETE

Validation: PASSED

Permanent song: SAVED
Reel: SAVED

Track FINISHED.
Moving to next track...
```

## 74. Example missing-LRC run

```text
Spotify LRC: NOT AVAILABLE
Continuing with audio-only hook analysis.
```

No lyric timing is invented.

## 75. Example failure run

```text
Spotify audio download: STARTING

ERROR: Spotify audio download failed
<real underlying exception>

Track not marked FINISHED.
Serial remains permanently consumed.

continue_on_error = YES
Skipping current track.
Moving to next track...
```

## 76. Final source-of-truth model

```text
                    SPOTIFY
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       Metadata      Audio          LRC
          │            │             │
          └────────────┼─────────────┘
                       ▼
                Hook analysis
                       │
                       ▼
                  Best hook
                       │
                       ▼
                    YOUTUBE
                       │
                    Visual
                       │
                       ▼
               Synchronization
                       │
                       ▼
            Spotify hook → YouTube
                       │
                       ▼
                  Renderer
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       YouTube       Spotify      Spotify
       visual        audio          LRC
          └────────────┼────────────┘
                       ▼
                  16:9 reel
```

## 77. Final non-negotiable checklist

- Spotify playlist is the processing queue.
- `playlist_id + spotify_id` identifies a playlist entry.
- Playlist order is preserved.
- Serial allocation is atomic.
- Serial numbers are never reused.
- Spotify is the musical master.
- Spotify audio is used for hook analysis.
- Spotify audio is the final reel audio.
- Spotify LRC is the final lyric source.
- No automatic lyric translation is introduced.
- Missing LRC does not automatically destroy the job.
- Hook analysis covers the complete Spotify song.
- Candidate generation covers the complete song.
- Many candidate windows are scored.
- 35–60 seconds is preferred, not mandatory.
- Musical quality is the foundation of scoring.
- Repeated musical/lyrical sections receive a strong boost.
- Lyrics influence scoring when available.
- No LRC means audio-only hook analysis.
- Music/lyric overlap is rewarded.
- Boundaries consider beat + musical phrase + lyric phrase.
- A small engaging lead-in may be used.
- Hook ending should be natural.
- YouTube search occurs only after hook selection.
- YouTube is visual-only.
- YouTube audio is synchronization-only.
- YouTube candidates and URLs are displayed.
- Spotify URL is displayed.
- YouTube ranking is tolerant rather than excessively strict.
- `reselect.py` is always manual.
- Manual flow supports Continue / Skip / Stop where required.
- Synchronization uses whole-song energy-envelope cross-correlation.
- Synchronization does not assume equal start times.
- Synchronization uses coarse global alignment plus local hook verification.
- Synchronization reports offset and confidence.
- Low-confidence synchronization is reported.
- Spotify timestamps remain the master timeline.
- Final output is 16:9.
- Final audio is Spotify.
- Final lyrics are Spotify LRC.
- Lyrics are centered inside the frame.
- Long lyrics wrap to additional lines.
- The whole lyric block stays inside the frame.
- Font is configurable.
- Explicit `.ttf`/`.otf` fonts are preferred.
- Missing fonts produce clear configuration errors.
- Unicode glyph coverage is required.
- FFmpeg lyric text is safely escaped.
- Cinematic settings are configurable.
- Secrets are loaded from `.env`.
- Secrets are never printed.
- spotDL client initialization is controlled.
- Nested Rich live displays are avoided.
- spotDL archive/error parent directories exist before invocation.
- LibreLyrics integration matches the installed version.
- Unsupported LibreLyrics arguments are not invented.
- `python -m librelyrics` is not assumed to work.
- `librelyrics --config` is not assumed to exist.
- Valid completed stages are reused where possible.
- Permanent canonical song creation waits until reel rendering succeeds.
- Reel validation occurs before permanent completion.
- `songs.db` stores permanent song data.
- `reel.db` stores reel data.
- `playlist.db` stores queue state.
- Permanent files and database paths are validated.
- Failed jobs are never marked `FINISHED`.
- Real underlying errors are shown.
- `continue_on_error` controls skip-vs-stop behavior.
- A consumed serial is never reused.
- Temporary files are deleted only after the appropriate permanent records/files are safely established, or according to failure cleanup policy.
- `playlist.db → FINISHED` is the final completion operation.
