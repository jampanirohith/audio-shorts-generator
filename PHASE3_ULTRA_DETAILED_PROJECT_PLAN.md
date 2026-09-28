# PHASE 3 — ULTRA-DETAILED STANDALONE PROJECT PLAN

## Project Baseline

**Project:** Phase 3 — Manual-Hook Telugu Music Reel Generator  
**Current implementation baseline discussed:** V1.0.16  
**Document purpose:** Authoritative design/architecture/implementation specification capturing the complete Phase 3 scope, decisions, interfaces, pipeline, data contracts, failure handling, performance requirements, validation strategy, and the history of superseded approaches.

---

# 1. EXECUTIVE DEFINITION

Phase 3 is a **completely standalone Reel-generation project**.

It does **not** depend on Phase 1 or Phase 2 code, databases, runtime state, project directories, processes, APIs, cloud storage, or internal implementation details.

The only upstream contract is a manually populated file package placed into:

```text
phase3_project/
└── songs/
    └── final/
        ├── SongName.mp3
        ├── SongName.lrc
        └── SongName.json
```

For Phase 3, the file basename is the identity key:

```text
SongName.mp3
SongName.lrc
SongName.json
```

must correspond to the same basename.

Phase 3 treats `songs/final/` as **read-only input**. It never rewrites, moves, normalizes, renames, mutates, or otherwise modifies those source files.

Phase 3 creates all working data and generated outputs under its own project directories.

The intended workflow is:

```text
1. User places Phase 2 final package into songs/final/
2. User runs python main.py
3. Phase 3 automatically synchronizes hook_timeline.json with songs/final/
4. User enters/edits hook start/end values in hook_timeline.json
5. User runs python main.py again
6. Phase 3 uses those exact manual timelines
7. Phase 3 analyzes/render-processes everything automatically
8. Phase 3 generates the final Reel and provenance JSON
9. User manually uploads the Reel to Instagram or another platform
```

There is **no Instagram API integration** and no automatic publishing.

---

# 2. FINAL CURRENT REQUIREMENTS — AUTHORITATIVE

The following requirements supersede earlier experiments.

## 2.1 Hook selection

There is **no automatic hook selection** in the final design.

The user directly controls the hook timeline in:

```text
hook_timeline.json
```

The timeline is authoritative.

The final system must never:

- rank hooks,
- select a hook automatically,
- generate hook finalists,
- substitute another hook because of video matching,
- shorten or extend the user's selected timeline merely because a default duration is preferred.

The exact interval supplied by the user becomes the final Reel musical interval.

## 2.2 Reel duration

There is **no maximum Reel duration imposed by Phase 3**.

The duration is exactly:

```text
end - start
```

from `hook_timeline.json`.

Examples that are valid in principle:

```text
00:00.000 → 00:10.000   = 10 seconds
02:12.920 → 03:11.720   = 58.8 seconds
01:00.000 → 02:15.000   = 75 seconds
```

Any duration is acceptable provided:

- the start is non-negative,
- the end is greater than the start,
- the interval lies within the local source song duration,
- the YouTube visual segment can be mapped to the same interval.

## 2.3 YouTube synchronization

The YouTube synchronization model is intentionally simple.

The system does **not** search for each hook independently.

Instead:

1. Take the first 15 seconds of the local original song.
2. Scan the YouTube song audio from the beginning.
3. Find the point where those first 15 seconds best align using a combination of:
   - normalized energy shape,
   - high/low transitions / peak-valley behavior,
   - downsampled waveform correlation.
4. Store one global offset.
5. Apply that same offset to the manually entered hook timeline.

For example:

```text
Original first 15s      = YouTube 00:05.000
Global offset           = +5.000s
```

If the user's hook is:

```text
02:12.920 → 03:11.720
```

the corresponding YouTube interval becomes:

```text
02:17.920 → 03:16.720
```

No per-hook re-matching is performed.

No DTW, multi-anchor verification, complex residual thresholding, or hook-by-hook search is required.

## 2.4 Video framing

Smart Crop has been removed.

There is no face tracking, body tracking, pose tracking, identity tracking, subject switching, or dynamic crop selection in the final design.

The final visual treatment is a **static centered panel**:

- canvas: `1080 x 1920`
- aspect ratio: `9:16`
- source video is scaled so its displayed height is approximately **80% of the 9:16 canvas height**
- 80% of 1920 = 1536 pixels
- the video is centered vertically
- the video remains horizontally centered
- source is cropped as necessary rather than stretched
- no black bars as a design goal
- no frame-by-frame subject tracking

The implementation baseline uses NVIDIA NVENC first for video encoding, with a CPU `libx264` fallback when NVENC cannot be executed.

## 2.5 Audio

The final Reel audio is always sourced from the **local original song**.

YouTube audio is only used as a synchronization reference.

The final hook audio is produced from the exact manual hook interval of the local Demucs stems.

Demucs is required to be executed by Phase 3 when needed; input stems are not assumed to exist.

The intended stem set is:

```text
vocals
 drums
 bass
 other
```

The exact selected hook interval is cropped from each relevant stem.

The stems are then processed into a stereo 8D-style spatial mix:

- vocals: centered / stable intelligibility
- bass: mono-compatible and centered
- drums: center-weighted with subtle spatial movement
- other: primary left/right movement and spatial motion

The 8D process must preserve musical timing.

There is no pitch shifting and no speed change.

The resulting audio becomes the Reel audio.

## 2.6 Lyrics

Lyrics come from the **LRC file**.

Phase 3 does not perform lyric discovery or ASR.

The lyric display is **line by line**, not persistent multi-line karaoke and not the earlier proposed context-block system.

Behavior:

```text
LRC line starts
    ↓
line appears
    ↓
words inside that line are individually highlighted according to word timestamps
    ↓
next LRC line begins
    ↓
previous line disappears
```

The active lyric line is the line whose timestamp range is currently active.

Every word in the line should have timing information when available so the renderer can highlight the current word.

The currently active word receives the strongest emphasis.

Completed/future words can be visually subtler, but the complete current LRC line remains visible until the next line replaces it.

The lyric block is positioned centrally in the Reel rather than at the traditional bottom third.

The baseline typography target discussed is:

```text
Font family: Baloo Tammudu 2 ExtraBold
Font filename: BalooTammudu2-ExtraBold.ttf
```

Fallback fonts may be used only when the requested font is not available.

---

# 3. STANDALONE PROJECT BOUNDARY

## 3.1 Strict isolation from upstream phases

Phase 3 must never import upstream Phase 1/2 Python modules.

Phase 3 must not connect to an upstream database.

Phase 3 must not rely on upstream runtime state.

Phase 3 must not assume upstream working directories.

Phase 3 must not launch or control Phase 1/2 processes.

Phase 3 must not use upstream-generated temporary files as a hidden dependency.

The only valid upstream dependency is the manual file package in:

```text
songs/final/
```

## 3.2 Source immutability

All source files in `songs/final/` are read-only.

Phase 3 may:

- read them,
- hash them,
- probe them,
- copy them into internal caches if desired.

Phase 3 may not modify their contents.

If provenance is needed, hashes should be calculated without changing the source files.

---

# 4. PROJECT DIRECTORY LAYOUT

Recommended structure:

```text
phase3_project/
│
├── main.py
├── config.json
├── hook_timeline.json
├── BUILD_INFO.md
├── CHANGELOG.md
├── README.md
│
├── songs/
│   └── final/
│       ├── SongA.mp3
│       ├── SongA.lrc
│       └── SongA.json
│
├── reels/
│   └── generated/
│       ├── SongA_reel.mp4
│       └── SongA_reel.json
│
├── temp/
│   └── <song-basename>/
│       ├── input/
│       ├── stems/
│       ├── analysis/
│       ├── matching/
│       ├── video/
│       ├── audio/
│       │   ├── cropped_stems/
│       │   └── audio_8d_manifest.json
│       ├── lyrics/
│       ├── render/
│       ├── stage_final/
│       ├── validation/
│       └── provenance/
│
├── assets/
│   ├── fonts/
│   └── models/
│
├── src/
│   ├── config.py
│   ├── utils.py
│   ├── audio_io.py
│   ├── stem_isolator.py
│   ├── audio_analysis.py
│   ├── lyric_parser.py
│   ├── hook_timeline.py
│   ├── youtube_audio.py
│   ├── audio_match.py
│   ├── video_grabber.py
│   ├── video_renderer.py
│   ├── audio_8d.py
│   ├── lyrics_renderer.py
│   ├── assembler.py
│   ├── validator.py
│   ├── provenance.py
│   ├── database.py
│   └── pipeline.py
│
└── tests/
    ├── test_contract.py
    ├── test_hook_timeline.py
    ├── test_lyrics.py
    ├── test_audio_offset.py
    ├── test_video_trim.py
    ├── test_audio_8d.py
    ├── test_validation.py
    └── test_pipeline_smoke.py
```

Directory names may evolve in implementation, but the source/output boundary must remain.

---

# 5. PRIMARY USER-FACING FILE: `hook_timeline.json`

## 5.1 Purpose

This is the authoritative user-editable hook configuration.

The user can manually select any timeline without opening Python code.

## 5.2 Example

```json
{
  "schema_version": 1,
  "songs": [
    {
      "song_path": "songs/final/001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.mp3",
      "lrc_path": "songs/final/001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.lrc",
      "hook": {
        "start": "02:12.92",
        "end": "03:11.72"
      }
    }
  ]
}
```

This exact `MM:SS.xx` syntax is valid.

Examples of accepted time forms should include:

```text
02:12.92
02:12.920
00:05
01:02:03.500
132.920
```

The canonical internal representation should be integer milliseconds.

For:

```text
02:12.92
```

canonical value is:

```text
132920 ms
```

For:

```text
03:11.72
```

canonical value is:

```text
191720 ms
```

Duration:

```text
58800 ms
= 58.8 s
```

## 5.3 Automatic JSON synchronization at startup

`python main.py` must automatically synchronize `hook_timeline.json` before processing.

The sync operation:

1. scans `songs/final/` for MP3 files,
2. derives the basename,
3. looks for the matching LRC,
4. looks for the matching JSON,
5. preserves existing hook data,
6. adds missing songs,
7. adds missing LRC paths,
8. does not invent a hook timeline.

The explicit command remains available:

```powershell
python main.py --fillhookjson
```

but normal `python main.py` should automatically perform the same synchronization first.

## 5.4 Preservation rules

If an existing entry already has:

```json
"hook": {
  "start": "02:12.92",
  "end": "03:11.72"
}
```

automatic synchronization must not erase or change those values.

New songs should receive:

```json
"hook": {
  "start": "",
  "end": ""
}
```

The system must not silently choose a hook.

## 5.5 Validation rules

Every configured song must satisfy:

- MP3 exists
- LRC exists, unless explicit project policy allows warning-only behavior
- optional Phase 2 JSON exists
- start is parseable
- end is parseable
- start >= 0
- end > start
- end <= source-song duration

The process should clearly report all unconfigured songs rather than silently skip them.

---

# 6. INPUT CONTRACT

Each input package is identified by basename matching.

Example:

```text
songs/final/001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.mp3
songs/final/001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.lrc
songs/final/001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.json
```

The historical metadata paths inside the Phase 2 JSON are not trusted as current filesystem paths.

Actual current filesystem paths must be derived from:

```text
songs/final/<basename>.*
```

This is important because the sample Phase 2 JSON historically contained paths referring to older directory layouts.

---

# 7. INPUT JSON USAGE

Phase 2 JSON is treated as structured metadata and word-level lyric/timing information.

It is **not modified**.

Useful fields may include:

- song metadata
- artist metadata
- duration
- source provenance
- YouTube Music ID
- selected visual YouTube video ID
- Phase 2 word alignment
- word-level timings

Phase 3 should prefer the actual local file package for current paths and use JSON metadata for semantic information.

Important distinction:

```text
YouTube Music ID
```

and

```text
selected visual YouTube video ID
```

may be different.

The visual matching pipeline should use the selected visual video ID when one exists.

---

# 8. INITIALIZATION / DOCTOR STAGE

## 8.1 `python main.py --doctor`

Doctor should report:

- Python version
- FFmpeg availability
- FFprobe availability
- CUDA availability
- Demucs availability
- NVIDIA NVENC support in FFmpeg
- fonts
- requested Baloo Tammudu 2 font availability or downloader status
- required directories
- `songs/final/`
- `hook_timeline.json`
- LRC pairing status
- source MP3 pairing status
- write permissions for temp/output paths

## 8.2 No false mandatory dependencies

MediaPipe is not a required dependency of the current final design because Smart Crop was removed.

Face/pose tracking should therefore not be part of the required doctor gate.

---

# 9. PIPELINE STAGES

The final pipeline is analysis → decision/input validation → synchronization → render → validation → finalization.

A typical state model:

```text
INPUT_VERIFIED
    ↓
STEMS_READY
    ↓
AUDIO_ANALYZED
    ↓
LYRICS_READY
    ↓
HOOK_PLAN_READY
    ↓
YOUTUBE_AUDIO_READY
    ↓
VIDEO_MATCH_READY
    ↓
VIDEO_SEGMENT_READY
    ↓
AUDIO_8D_READY
    ↓
LYRICS_RENDER_READY
    ↓
VIDEO_RENDERED
    ↓
ASSEMBLED
    ↓
VALIDATED
    ↓
FINALIZED
```

Failure/review states should be explicit.

The system should be resumable where possible.

---

# 10. STAGE 1 — VERIFY INPUT PACKAGE

For each song entry:

1. confirm MP3 exists,
2. confirm LRC exists,
3. locate optional JSON,
4. probe MP3 duration/sample rate/channels/codec,
5. compute source hash,
6. validate hook timeline only if configured,
7. create per-song work directory.

### Important Windows behavior

FFprobe/FFmpeg output may contain Unicode/Telugu metadata.

Subprocess handling must explicitly use UTF-8 with replacement/error tolerance rather than relying on the Windows CP1252 default.

Conceptually:

```python
subprocess.run(
    ...,
    text=True,
    encoding="utf-8",
    errors="replace"
)
```

The probe code must handle:

- empty FFprobe output,
- invalid JSON,
- multiple streams,
- MP3 artwork streams.

The audio stream must be selected correctly even when FFprobe also reports a JPEG/MJPEG artwork stream.

---

# 11. STAGE 2 — DEMUCS STEM ISOLATION

Phase 3 runs Demucs itself.

Expected stems:

```text
vocals
 drums
 bass
 other
```

The stage should:

1. run Demucs on the local MP3,
2. use CUDA when available,
3. verify all expected stem files,
4. record Demucs model/version if possible,
5. save stem paths in provenance.

The final audio output must be derived from the local source song/stems, never from YouTube audio.

The stem stage is computationally expensive; cache results and resume if valid.

---

# 12. STAGE 3 — FULL-SONG AUDIO ANALYSIS

Although hook selection is now manual, the system still performs broad audio analysis for diagnostics, provenance, and downstream quality control.

Analyze:

- full mix
- vocals
- drums
- bass
- other

Potential measurements:

- RMS energy
- peak amplitude
- short-term energy envelope
- spectral centroid
- spectral rolloff
- spectral flux
- onset density
- chroma
- log-mel features
- energy contour
- silence/instrumental regions
- stem activity
- vocal activity
- arrangement density

This information is not allowed to override the manual hook timeline.

---

# 13. STAGE 4 — LRC PARSING

The LRC is canonical for lyric display.

The parser must handle ordinary line timestamps and the supplied word-timestamp structure.

Example style:

```text
[00:25.18]గెలుపు [00:25.98]తలుపులే [00:27.34]తీసే [00:29.52]ఆకాశమే
```

The parser should produce a structure conceptually like:

```json
{
  "start_ms": 25180,
  "end_ms": 29520,
  "text": "గెలుపు తలుపులే తీసే ఆకాశమే",
  "words": [
    {"text": "గెలుపు", "start_ms": 25180, "end_ms": 25980},
    {"text": "తలుపులే", "start_ms": 25980, "end_ms": 27340},
    {"text": "తీసే", "start_ms": 27340, "end_ms": 29520}
  ]
}
```

Exact handling can use the next word timestamp or next line timestamp as the end boundary.

If word timings are unavailable, the renderer should gracefully fall back to line-level display rather than requiring ASR.

---

# 14. LYRIC DISPLAY RULES

## 14.1 Line selection

At render time `t`, select the line active at `t`.

Only the current line is displayed.

When the next line begins, the previous line disappears.

## 14.2 Word highlighting

Within the active line:

- current word: strongest highlight
- earlier words: completed state / subtle
- later words: future state / subtle

The highlight progresses continuously according to the LRC word timing.

## 14.3 Position

Lyrics should be visually centered in the Reel, around the middle region rather than near the bottom edge.

Suggested baseline:

```text
x = 540
center-y around 960
acceptable vertical range roughly 800–1120
```

## 14.4 Typography

Primary:

```text
Baloo Tammudu 2 ExtraBold
```

Fallback may be used if unavailable.

Font loader should be able to:

1. search local system fonts,
2. check project font directory,
3. download the correct official font package if needed,
4. cache it locally.

The font binary itself does not have to be bundled inside the source ZIP if the implementation downloads it on first run.

---

# 15. STAGE 5 — MANUAL HOOK PLAN

For each configured entry:

```text
hook.start
hook.end
```

becomes:

```text
hook_start_ms
hook_end_ms
hook_duration_ms
```

Example:

```text
02:12.92 → 03:11.72
132920 → 191720
58800 ms
```

This is the final content interval.

No automatic adjustment is allowed.

---

# 16. STAGE 6 — DOWNLOAD / EXTRACT COMPLETE YOUTUBE AUDIO

The selected YouTube visual video is acquired so that its audio can be used as a timing reference.

The audio analysis goal is the song's opening, because the current synchronization method depends on the first 15 seconds of the local source.

The full relevant YouTube audio should be available for scanning.

The selected YouTube video can be shorter than the local source song; this is a known real-world condition.

The global offset stage must therefore calculate whether the configured hook is actually present in the available visual video.

If the mapped hook extends beyond available video duration, the pipeline should fail clearly rather than silently creating an incorrect video.

---

# 17. FINAL YOUTUBE OFFSET ALGORITHM

The final algorithm is deliberately simple.

## 17.1 Local reference

Extract:

```text
original audio [0s : 15s]
```

## 17.2 Features

Use low-rate, robust features:

- normalized waveform at reduced sample rate,
- RMS/energy envelope,
- peak/valley structure.

Normalize each representation so overall loudness differences do not dominate.

## 17.3 Search

Scan the YouTube audio from the start.

At each candidate time `t`, compare:

```text
YouTube[t : t+15s]
```

against:

```text
Original[0 : 15s]
```

Score components:

```text
energy correlation
waveform correlation
peak/valley similarity
```

Combine them into one score.

## 17.4 Earliest near-best policy

If multiple points are nearly equally good, prefer the earliest strong match.

This avoids accidentally selecting a later repeated chorus solely because it has similar energy.

## 17.5 Output

Store:

```text
match_method = "first_15s_anchor"
offset_ms
score
energy_score
peak_valley_score
waveform_score
```

## 17.6 Applying the offset

```text
video_start_ms = hook_start_ms + offset_ms
video_end_ms   = hook_end_ms   + offset_ms
```

No additional hook search.

---

# 18. OFFSET EXAMPLE

Suppose:

```text
original first 15 sec
matches YouTube starting at 1.8 sec
```

then:

```text
offset = +1800 ms
```

Manual hook:

```text
132920 → 191720 ms
```

maps to:

```text
134720 → 193520 ms
```

The local audio remains:

```text
132920 → 191720
```

The YouTube timeline is only used to choose the visual interval.

---

# 19. VIDEO GUARD BAND

A small guard band may be downloaded around the mapped YouTube interval to make FFmpeg extraction safer and preserve natural transitions.

Baseline discussed:

```text
±1.5 seconds
```

For example:

```text
mapped_start = 134720
mapped_end   = 193520
```

download approximately:

```text
133220 → 195020
```

Then exact trim must skip the leading guard.

This was an important implementation correction:

> the exact trim must not take the first `duration` milliseconds from the guarded file as if the guard did not exist.

The trim operation must explicitly receive `trim_start_ms = guard_before_ms`.

---

# 20. EXACT VIDEO TRIM

The final video section duration must equal:

```text
hook_end_ms - hook_start_ms
```

The trim implementation must:

1. seek to `guard_before_ms`,
2. extract exactly `hook_duration_ms`,
3. encode with NVENC if possible,
4. fall back to libx264 if NVENC fails,
5. probe the result,
6. verify duration error is within an accepted tolerance.

The `trim_start_ms` variable must be correctly propagated to both encoder paths.

A previous regression occurred where it was passed to `trim_exact()` but not `_encode_trim()`. The final design must include regression coverage for this.

---

# 21. VIDEO RENDERING — STATIC 80% PANEL

No Smart Crop.

No tracking.

No subject detection.

No identity persistence.

No face-based composition.

The video layout is deterministic.

## 21.1 Target canvas

```text
1080 x 1920
```

## 21.2 Panel size

80% of canvas height:

```text
1920 × 0.80 = 1536 px
```

## 21.3 Placement

The source is scaled to a displayed height of approximately 1536 px.

The resulting image is centered horizontally and vertically within the 1080×1920 canvas.

Horizontal overflow is cropped centrally when necessary.

Vertical overflow should not occur if scaling is based on panel height.

The final composition therefore produces a strong centered cinematic panel occupying about 80% of the Reel's height.

---

# 22. NVIDIA / FFmpeg ACCELERATION

NVIDIA should be used as much as practical in the expensive video encoding stages.

## 22.1 Demucs

If a CUDA-enabled PyTorch environment is available:

```text
Demucs → CUDA
```

## 22.2 Video encoding

Primary:

```text
h264_nvenc
```

Fallback:

```text
libx264
```

## 22.3 Compatibility

Do not assume every FFmpeg build exposes the same optional NVENC flags.

The pipeline should use conservative, widely supported NVENC parameters.

Do not require unsupported flags such as version-sensitive AQ/lookahead options merely because a particular FFmpeg build supports them.

The renderer should:

1. detect `h264_nvenc`,
2. attempt NVENC,
3. detect immediate FFmpeg failure,
4. fall back to CPU encoding cleanly.

The Python frame writer must check that the FFmpeg process is still alive before continuing to write to stdin.

Otherwise a failed encoder can misleadingly manifest as:

```text
OSError: [Errno 22] Invalid argument
```

when the actual cause was FFmpeg exiting because of an unsupported option.

---

# 23. FINAL 8D AUDIO PIPELINE

The local hook interval is cropped from every relevant Demucs stem.

Expected files:

```text
work/audio/cropped_stems/vocals_hook.wav
work/audio/cropped_stems/drums_hook.wav
work/audio/cropped_stems/bass_hook.wav
work/audio/cropped_stems/other_hook.wav
```

## 23.1 Stem timing

Every stem extraction must use exactly:

```text
hook_start_ms
hook_end_ms
```

There must be no independent stem timing drift.

## 23.2 Vocals

Vocals should remain centered to preserve lyric intelligibility.

A very small width may be permitted, but dramatic movement should not compromise clarity.

## 23.3 Bass

Bass should be mono/centered or strongly center-weighted for mono compatibility.

## 23.4 Drums

Drums may use subtle widening or movement while retaining a stable center impression.

## 23.5 Other

`other` is the primary carrier of smooth left/right panning motion.

## 23.6 Motion model

The 8D movement should be smooth rather than random frame-level bouncing.

Suitable movement:

```text
slow sinusoidal / LFO-style panning
gradual width changes
small phase-coherent movement
```

The exact movement rate may vary by implementation, but the motion must not change the musical timeline.

## 23.7 Audio preservation

Do not:

- pitch shift,
- time stretch,
- speed up,
- slow down.

## 23.8 Loudness

A final loudness/peak normalization stage should prevent clipping and maintain comfortable playback.

## 23.9 Audit manifest

Create:

```text
work/audio/audio_8d_manifest.json
```

with at least:

```json
{
  "source_song": "...",
  "hook_start_ms": 132920,
  "hook_end_ms": 191720,
  "duration_ms": 58800,
  "stems": {
    "vocals": "...",
    "drums": "...",
    "bass": "...",
    "other": "..."
  },
  "processing": {
    "vocals": "centered",
    "bass": "mono_center",
    "drums": "center_weighted_moving",
    "other": "primary_8d_motion"
  }
}
```

---

# 24. LYRIC RENDERING PIPELINE

## 24.1 Input

Primary lyric text source:

```text
songs/final/<basename>.lrc
```

Phase 2 JSON can be used for validation/reference but does not replace the LRC as requested display source.

## 24.2 Line lifecycle

For each LRC line:

```text
line_start
   ↓
line visible
   ↓
word highlights progress
   ↓
next line starts
   ↓
previous line removed
```

## 24.3 Word layout

The line should support Telugu shaping correctly.

Intelligent wrapping may be used when a line is too long for the central area, but the line remains conceptually one lyric line rather than a karaoke page containing multiple independent LRC lines.

## 24.4 Emphasis

Strongest visual emphasis should remain on the currently sung word.

Potential visual states:

```text
future word    = normal / subdued
current word   = strongest highlight
past word      = completed/subdued
```

The text itself should not jump unpredictably.

## 24.5 Rendering technology

ASS subtitle generation or direct frame text rendering may be used.

If ASS is used:

- correct UTF-8 handling is mandatory,
- font directory must be passed correctly,
- Windows path escaping must be safe,
- font paths should be represented as `Path` objects internally.

A previous crash came from treating a string as a `Path` and calling `.as_posix()` on it.

The implementation must normalize config paths with `Path(...)` before use.

---

# 25. AUDIO/VIDEO ASSEMBLY

The final assembly combines:

```text
video = exact YouTube visual segment
+
lyrics = generated lyric overlay
+
 audio = local 8D hook audio
```

The YouTube audio is not used as the final Reel audio.

The final container should contain:

```text
video codec: H.264
video size: 1080x1920
video fps: source/selected stable FPS, typically 29.97 or equivalent

audio codec: AAC
channels: stereo
```

The exact audio sample rate may vary depending on implementation but should be consistent and validated.

---

# 26. FINAL OUTPUT FILES

Primary outputs:

```text
reels/generated/<basename>_reel.mp4
reels/generated/<basename>_reel.json
```

The output JSON must be a new Phase 3 provenance file.

It must never modify the upstream Phase 2 JSON.

---

# 27. PROVENANCE JSON

Recommended structure:

```json
{
  "schema_version": 1,
  "pipeline_version": "1.0.16",
  "song": {
    "basename": "...",
    "mp3": "...",
    "lrc": "...",
    "phase2_json": "...",
    "mp3_sha256": "...",
    "lrc_sha256": "...",
    "json_sha256": "..."
  },
  "hook": {
    "mode": "manual_json",
    "start_ms": 132920,
    "end_ms": 191720,
    "duration_ms": 58800
  },
  "youtube_match": {
    "method": "first_15s_anchor",
    "video_id": "...",
    "offset_ms": 1800,
    "score": 0.3376,
    "energy_score": 0.4143,
    "peak_valley_score": 0.1403
  },
  "video": {
    "mapped_start_ms": 134720,
    "mapped_end_ms": 193520,
    "guard_before_ms": 1500,
    "guard_after_ms": 1500,
    "panel_percent_height": 80,
    "output_width": 1080,
    "output_height": 1920
  },
  "audio": {
    "source": "local_demucs_stems",
    "eight_d": true,
    "manifest": "..."
  },
  "lyrics": {
    "source": "lrc",
    "word_highlighting": true,
    "line_by_line": true,
    "font": "Baloo Tammudu 2 ExtraBold"
  },
  "validation": {
    "overall": true,
    "failed_checks": []
  },
  "output": {
    "mp4": "...",
    "sha256": "..."
  }
}
```

---

# 28. VALIDATION SYSTEM

Validation must be explicit and informative.

For a finished Reel, validate at minimum:

## 28.1 File existence

- final MP4 exists
- final JSON exists

## 28.2 Video dimensions

Expected:

```text
1080 × 1920
```

## 28.3 Aspect ratio

Expected:

```text
9:16
```

## 28.4 Duration

Expected:

```text
final duration ≈ hook_end - hook_start
```

No hard 30s or 40s limit.

## 28.5 Audio

Must be:

- present
- stereo
- non-zero duration
- playable

## 28.6 Codec

Expected video codec:

```text
h264
```

Expected audio codec:

```text
aac
```

## 28.7 Encoding/render checks

Ensure final assembly did not produce a zero-length or corrupt file.

## 28.8 Validation JSON

Write:

```text
temp/<basename>/validation/final_validation.json
```

with:

```json
{
  "overall": true,
  "checks": [...],
  "failed_checks": [],
  "probe": {...}
}
```

The validator must derive `overall` from current checks rather than trusting stale state.

An empty `checks=[]` should not automatically become a false failure when the direct required-output checks pass.

If a failure occurs, `failed_checks` must contain descriptive names/messages.

Do not emit only:

```text
Final validation failed
```

without the failed check details.

---

# 29. ERROR HANDLING PRINCIPLES

Errors must preserve the actual root cause.

## 29.1 FFprobe decoding

Do not allow Windows CP1252 decoding to create secondary JSON errors.

## 29.2 FFprobe output

If output is empty:

```text
FFPROBE_EMPTY_OUTPUT
```

If output is malformed:

```text
FFPROBE_JSON_INVALID
```

## 29.3 JSON serialization

Do not create circular references when saving matching results.

A previous error came from:

```text
best = candidates[0]
best['candidates'] = candidates
```

because `best` became recursively self-referential.

Correct behavior:

```python
best = dict(best)
best['candidates'] = [dict(c) for c in candidates]
```

or an equivalent detached structure.

## 29.4 FFmpeg stdin failures

If FFmpeg exits early, the Python writer must detect that condition rather than blindly writing to a dead pipe.

## 29.5 Missing hook configuration

Report:

```text
NOT CONFIGURED — fill hook.start and hook.end
```

Do not guess.

## 29.6 Missing LRC

Report the exact song and expected LRC path.

## 29.7 Missing visual availability

If global offset maps the hook outside the available YouTube video, fail clearly.

Do not silently change the user's hook timeline.

---

# 30. RESUMABILITY AND CACHING

The pipeline is intended to support resumability.

Stage artifacts should be stored per song.

Example:

```text
stems/
analysis/
matching/
video/
audio/
lyrics/
render/
stage_final/
validation/
```

Caching should be invalidated when any of these changes:

- source MP3 hash
- source LRC hash
- input JSON hash
- hook start
- hook end
- YouTube video ID
- synchronization method/version
- renderer version
- key config options

A previous failure showed why stale cached video sections are dangerous.

Cache keys must incorporate the requested timeline and visual-match parameters.

Never blindly reuse a cached section if it was produced for a different hook interval or video mapping.

---

# 31. DATABASE / STATE MACHINE

An internal database/state table may be used for resumability.

The database is **internal to Phase 3** and must not be shared with Phase 1/2.

Useful states:

```text
input_verified
stems_ready
audio_analyzed
lyrics_ready
hook_plan_ready
youtube_audio_ready
video_match_ready
video_segment_ready
audio_8d_ready
lyrics_render_ready
video_rendered
assembled
validated
finalized
failed
review_required
```

Each state should record:

- timestamp
- attempt count
- artifact paths
- error code
- error message
- software version

---

# 32. COMMAND-LINE INTERFACE

## 32.1 Normal processing

```powershell
python main.py
```

Normal behavior:

1. auto-sync `hook_timeline.json`,
2. load the hook plan,
3. process every configured song,
4. report unconfigured songs,
5. generate Reels for configured songs.

## 32.2 Process all explicit alias

Historical implementation supported:

```powershell
python main.py --process-all
```

This should remain supported where practical for compatibility.

## 32.3 Fill/sync hook JSON explicitly

```powershell
python main.py --fillhookjson
```

This only synchronizes song/LRC entries.

It does not choose hooks.

## 32.4 Doctor

```powershell
python main.py --doctor
```

## 32.5 Force rebuild

A force option may be retained:

```powershell
python main.py --force
```

or equivalent, to invalidate cached stages.

---

# 33. USER WORKFLOW — FINAL

## First run after adding songs

```powershell
python main.py
```

Phase 3 automatically creates/updates:

```text
hook_timeline.json
```

The user edits the file.

Example:

```json
{
  "song_path": "songs/final/001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.mp3",
  "lrc_path": "songs/final/001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.lrc",
  "hook": {
    "start": "02:12.92",
    "end": "03:11.72"
  }
}
```

Then:

```powershell
python main.py
```

Everything else is automatic.

---

# 34. SAMPLE SONG — KNOWN REAL-WORLD BEHAVIOR

The discussed sample song was:

```text
001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra
```

Observed source duration was approximately:

```text
317.592 seconds
```

The actual sample also demonstrated that the selected visual YouTube video can be much shorter than the local song.

That is why visual availability must be checked after applying the global offset.

The supplied timeline example is:

```text
02:12.92 → 03:11.72
```

which equals:

```text
132920 ms → 191720 ms
58.800 seconds
```

The recent execution logs confirmed this parsing is correct.

---

# 35. HISTORY OF SUPERSEDED HOOK SELECTION DESIGN

This section records the earlier ideas so they are not lost, but they are **not part of the current final implementation**.

Originally, Phase 3 was designed to automatically discover hooks through:

- full-song Demucs analysis,
- lyric memorability,
- repeated phrases,
- repeated section families,
- energy contours,
- vocal quality,
- arrangement richness,
- phrase completeness,
- timing quality,
- 10–15 diverse candidates,
- context expansion,
- downstream YouTube eligibility filtering.

Variable hook length was discussed, roughly 10–35 seconds core with possible 15–60 second final Reel.

A manual `--manualhook` override mode was also designed.

These mechanisms were subsequently removed in favor of the direct JSON timeline workflow.

They should not be accidentally reintroduced into the current pipeline.

---

# 36. HISTORY OF SUPERSEDED SMART CROP DESIGN

Earlier designs included:

- face detection,
- body/pose tracking,
- persistent track IDs,
- A/B identity hysteresis,
- multi-person selection,
- shot-aware crop,
- lyric collision avoidance,
- dynamic subject framing.

A later tracker implementation was tested but produced:

```json
{
  "primary_track_id": null,
  "samples": [],
  "tracking_confidence_mean": 0,
  "subject_switches": 0
}
```

The decision was then made to remove Smart Crop entirely.

The current design is the simpler static centered 80%-height panel.

No tracking code should be required for the final pipeline.

---

# 37. HISTORY OF SUPERSEDED YOUTUBE MATCHING DESIGNS

Several matching strategies were considered and then simplified.

Removed/obsolete approaches include:

- hook-by-hook query matching,
- DTW,
- multi-anchor verification,
- residual-error acceptance gates,
- complex global alignment logic,
- repeated peak-pattern hook matching.

A whole-track correlation implementation produced an obviously wrong example:

```text
-99.822 seconds
```

That strategy was discarded.

The final approach is the simpler 15-second anchor scan described earlier.

---

# 38. HISTORY OF DURATION LIMITS

Earlier requirements used approximately 30 seconds as a preferred target.

That was later changed to a 40-second maximum.

That was then removed entirely.

The current final requirement is:

> **No maximum Reel duration. Use exactly the start/end timeline entered by the user.**

This is authoritative.

---

# 39. HISTORY OF VIDEO PANEL SIZE

Earlier static video layout used approximately 70% of 9:16 height.

The user later changed it to:

```text
80%
```

Current authoritative value:

```text
80% of 1920 = 1536 px
```

---

# 40. HISTORY OF LYRICS DESIGN

Earlier plans proposed a persistent lyric context block with current-word highlighting and potentially two lines.

The user later clarified the desired behavior:

- one LRC line at a time,
- line disappears when next line appears,
- current word in the line highlighted.

Current authoritative design is therefore **line-by-line LRC display with word-by-word highlighting**.

---

# 41. HISTORY OF 8D AUDIO DESIGN

The final design evolved from a conceptual 8D stage into explicit stem-based processing.

Current requirements:

- crop exact hook from Demucs stems,
- process vocals/drums/bass/other separately,
- recombine into stereo,
- preserve timeline,
- no pitch/speed alteration.

The local song is always the final audio source.

---

# 42. WINDOWS-SPECIFIC LESSONS

Phase 3 is expected to run on Windows.

Known implementation pitfalls:

## 42.1 Encoding

Always explicitly handle subprocess output as UTF-8.

## 42.2 Path types

Normalize configuration paths to `Path` objects before calling:

```python
.as_posix()
```

Never assume a config field is already a `Path`.

## 42.3 FFmpeg subprocess pipes

Check subprocess liveness before writing frames.

## 42.4 File locks

Windows can retain file handles longer than expected.

Use context managers and close FFmpeg/decoder processes deterministically.

## 42.5 Unicode song names

Song names and metadata may contain Telugu and other non-ASCII text.

All JSON should be written using:

```python
ensure_ascii=False
encoding='utf-8'
```

---

# 43. SOURCE JSON VS PHASE 3 JSON

Two different JSON roles must remain distinct.

## Input JSON

```text
songs/final/Song.json
```

This belongs to the upstream Phase 2 package.

Phase 3 reads it but does not mutate it.

## Output JSON

```text
reels/generated/Song_reel.json
```

This belongs entirely to Phase 3.

It records the exact decision and transformation history.

Never reuse the input file for output provenance.

---

# 44. PROVENANCE REQUIREMENTS

Every Reel should be reproducible from recorded metadata.

Record:

- source MP3 SHA-256
- source LRC SHA-256
- source JSON SHA-256
- hook start/end
- hook duration
- YouTube video ID
- YouTube global offset
- synchronization score/components
- guard band
- actual video mapped start/end
- Demucs model
- stems paths
- 8D processing parameters
- lyric parser/render configuration
- font name
- panel size
- output resolution
- output FPS
- encoder used
- fallback status if applicable
- validation results
- output SHA-256
- pipeline version

---

# 45. TEST PLAN

The project should maintain regression coverage for all bugs encountered.

## 45.1 Contract tests

- MP3/LRC/JSON basename pairing
- actual sample metadata
- Unicode metadata

## 45.2 Windows UTF-8 test

Run a subprocess that emits Telugu plus Unicode symbols and confirm decoding succeeds.

## 45.3 FFprobe test

Confirm audio stream selection when cover art is present.

## 45.4 Circular JSON test

Confirm candidate match output serializes without circular-reference errors.

## 45.5 Timeline parser tests

Required:

```text
02:12.92
02:12.920
00:05
01:02:03.500
```

## 45.6 Hook duration test

Confirm:

```text
03:11.72 - 02:12.92 = 58.8 sec
```

## 45.7 JSON auto-sync test

Confirm:

- new MP3 added,
- matching LRC added,
- existing hook preserved.

## 45.8 LRC tests

Confirm word-level inline timestamp parsing for Telugu.

## 45.9 15-second anchor test

Use synthetic audio with known offset and confirm the recovered offset.

## 45.10 Trim guard test

Confirm:

```text
source = guarded clip
trim_start_ms = guard
output duration = requested hook duration
```

## 45.11 Renderer test

Confirm:

```text
1080x1920
80% panel
NVENC path when available
CPU fallback when NVENC unavailable
```

## 45.12 8D test

Confirm cropped stem files exist and final WAV is stereo.

## 45.13 Final validation test

Confirm valid output yields:

```text
overall = true
failed_checks = []
```

---

# 46. ACCEPTANCE CRITERIA

Phase 3 is considered complete when all of the following are true.

## Inputs

- standalone project
- no Phase 1/2 imports
- source folder read-only
- same-basename package handling

## Hook control

- automatic hook selection absent
- hook timeline JSON authoritative
- arbitrary duration allowed
- `MM:SS.xx` supported
- `python main.py` auto-updates JSON
- existing times preserved

## YouTube synchronization

- first 15 seconds of local song used as anchor
- YouTube scanned from start
- one global offset calculated
- manual hook shifted by offset
- no per-hook re-search

## Video

- exact requested hook duration
- guard band correctly handled
- centered static panel
- 80% of 9:16 height
- 1080×1920 final output
- NVENC-first
- CPU fallback

## Audio

- local source only
- Demucs executed by Phase 3
- exact hook crop from stems
- 8D stem-based processing
- stereo final audio
- no pitch/speed manipulation

## Lyrics

- LRC source
- line-by-line display
- line disappears when next line begins
- word-level highlighting
- Telugu-compatible font rendering
- centered lyric placement

## Validation

- final MP4 valid
- final JSON valid
- duration matches hook
- 1080×1920
- stereo audio
- `overall=true`
- empty `failed_checks`

---

# 47. PERFORMANCE REQUIREMENTS

## GPU

Use CUDA for Demucs where available.

Use NVENC for video encoding where available.

## CPU

CPU remains appropriate for:

- JSON parsing
- LRC parsing
- timeline validation
- feature extraction where small
- FFmpeg orchestration
- provenance

## Cache

Cache expensive stages:

- Demucs stems
- downloaded YouTube audio
- matched YouTube section
- 8D intermediate stems
- lyric render assets

Never compromise correctness for cache reuse.

---

# 48. LOGGING REQUIREMENTS

Logs should clearly show:

```text
Auto-updated hook timeline
Loaded hook timeline
HOOK PLAN
YouTube 15s anchor offset
VideoGrabber download status
VideoRenderer encoder
8D audio generation
Lyrics rendering
Assembly
Validation
Final output path
```

For failures, include:

- stage
- error code
- affected song
- source path
- relevant artifact path
- exact failed check

Example:

```text
ERROR OUTPUT_VALIDATION_FAILED: duration mismatch
song=...
expected=58800ms
actual=58512ms
artifact=...
```

---

# 49. OUTPUT ORGANIZATION

Generated Reels should never overwrite source packages.

Use:

```text
reels/generated/
```

Recommended naming:

```text
<basename>_reel.mp4
<basename>_reel.json
```

The basename must match the input song basename so the provenance is obvious.

---

# 50. FAILURE RECOVERY STRATEGY

When one song fails, `process_all` should continue to the next song when safe.

Each song gets an independent work directory.

The summary should report:

```text
processed
succeeded
failed
unconfigured
```

A failed song must retain its stage artifacts and error log so debugging does not require rerunning Demucs unnecessarily.

---

# 51. QUALITY PRINCIPLES

Phase 3 should prioritize:

1. user-entered timeline correctness,
2. local audio correctness,
3. visual synchronization correctness,
4. exact output duration,
5. lyric timing correctness,
6. stable video composition,
7. GPU acceleration where available,
8. reproducible provenance.

It should not introduce complicated heuristics merely to make the system appear more intelligent.

The user deliberately chose a simpler and more deterministic architecture.

---

# 52. IMPORTANT NON-NEGOTIABLES

The final implementation must **not** silently reintroduce any of these removed ideas:

```text
automatic hook selection
30-second limit
40-second limit
Smart Crop
face tracking
pose tracking
per-hook YouTube audio matching
DTW
complex anchor verification
YouTube audio as final Reel audio
ASR-based lyrics discovery
Instagram automatic publishing
mutation of songs/final source files
```

The intended current design is deterministic and user-controlled.

---

# 53. END-TO-END FINAL PIPELINE

The complete final pipeline is:

```text
                    ┌─────────────────────────────┐
                    │ songs/final/                │
                    │ MP3 + LRC + JSON            │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │ AUTO-SYNC hook_timeline.json│
                    │ add new songs + LRC paths   │
                    │ preserve existing hooks     │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │ LOAD MANUAL HOOK TIMELINE   │
                    │ start/end are authoritative │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │ VERIFY SOURCE + PROBE MP3   │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │ RUN DEMUCS ON LOCAL SONG     │
                    │ vocals / drums / bass / other│
                    └──────────────┬──────────────┘
                                   │
                   ┌───────────────┴───────────────┐
                   │                               │
                   ▼                               ▼
        ┌──────────────────────┐       ┌──────────────────────┐
        │ FULL AUDIO ANALYSIS  │       │ PARSE LRC             │
        │ diagnostics/features │       │ line + word timing    │
        └──────────┬───────────┘       └──────────┬───────────┘
                   │                               │
                   └───────────────┬───────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │ YOUTUBE AUDIO REFERENCE     │
                    │ take original first 15s      │
                    │ scan YT from 00:00           │
                    │ find simple strongest match  │
                    │ produce one global offset    │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │ APPLY OFFSET TO MANUAL HOOK │
                    │ video_start = hook + offset │
                    │ video_end   = hook + offset │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │ DOWNLOAD YOUTUBE VIDEO      │
                    │ ± guard band                │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │ EXACT TRIM                  │
                    │ skip guard                  │
                    │ exact hook duration         │
                    │ NVENC → CPU fallback        │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
        ┌──────────────────────┐      ┌─────────────────────────┐
        │ CROP EXACT DEMUCS    │      │ GENERATE LINE-BY-LINE   │
        │ HOOK STEMS           │      │ LYRIC OVERLAY FROM LRC  │
        └──────────┬───────────┘      │ current-word highlight  │
                   │                  └────────────┬────────────┘
                   ▼                               │
        ┌──────────────────────┐                   │
        │ GENERATE 8D AUDIO    │                   │
        │ vocals center        │                   │
        │ bass center          │                   │
        │ drums subtle motion  │                   │
        │ other main movement  │                   │
        └──────────┬───────────┘                   │
                   │                               │
                   └──────────────┬────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │ STATIC VIDEO RENDER         │
                    │ 1080×1920                   │
                    │ 80% height panel            │
                    │ centered                    │
                    │ NVENC-first                 │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │ ASSEMBLE                    │
                    │ local 8D audio + video      │
                    │ + lyric overlay             │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │ FINAL VALIDATION            │
                    │ duration / size / audio /   │
                    │ codec / integrity           │
                    └──────────────┬──────────────┘
                                   │
                              PASS │
                                   ▼
                    ┌─────────────────────────────┐
                    │ reels/generated/            │
                    │ Song_reel.mp4               │
                    │ Song_reel.json              │
                    └─────────────────────────────┘
```

---

# 54. FINAL IMPLEMENTATION CHECKLIST

Before calling the project complete, verify all of the following.

## Project boundary

- [ ] Phase 3 standalone
- [ ] no upstream imports
- [ ] no upstream DB dependency
- [ ] source folder read-only

## Input management

- [ ] basename matching
- [ ] automatic `hook_timeline.json` synchronization
- [ ] LRC paths recorded
- [ ] existing hooks preserved
- [ ] unconfigured songs reported

## Hook control

- [ ] manual-only
- [ ] no automatic selection
- [ ] no duration cap
- [ ] `MM:SS.xx` accepted
- [ ] exact duration derived from JSON

## Analysis

- [ ] Demucs CUDA support
- [ ] full-song audio analysis
- [ ] LRC parsing
- [ ] word timing parsing

## YouTube synchronization

- [ ] first 15 seconds anchor
- [ ] scan from YouTube start
- [ ] energy + peaks/valleys + waveform correlation
- [ ] one global offset
- [ ] earliest strong match preference
- [ ] mapped hook interval

## Video

- [ ] guard band
- [ ] exact trim start offset
- [ ] exact duration
- [ ] static centered rendering
- [ ] 80% panel height
- [ ] 1080×1920
- [ ] NVENC first
- [ ] CPU fallback

## Audio

- [ ] local song only
- [ ] crop exact hook stems
- [ ] 8D mixing
- [ ] vocal centered
- [ ] bass centered
- [ ] drums subtly spatial
- [ ] other carries movement
- [ ] no pitch/speed alteration

## Lyrics

- [ ] LRC is display source
- [ ] one line at a time
- [ ] word highlighting
- [ ] next line replaces previous
- [ ] centered placement
- [ ] Telugu font shaping

## Validation

- [ ] final MP4 exists
- [ ] final JSON exists
- [ ] 1080×1920
- [ ] 9:16
- [ ] duration matches JSON
- [ ] stereo audio
- [ ] valid H.264/AAC
- [ ] `overall=true`
- [ ] `failed_checks=[]`

## Provenance

- [ ] source hashes
- [ ] hook timeline
- [ ] YouTube offset
- [ ] video IDs
- [ ] Demucs/stem information
- [ ] 8D manifest
- [ ] lyric configuration
- [ ] renderer configuration
- [ ] validation results
- [ ] output hash

---

# 55. FINAL DECISION SUMMARY

The final Phase 3 architecture is intentionally **simple, deterministic, standalone, and manually controlled at the hook-selection layer**.

The user chooses the musical interval.

Phase 3 performs everything else:

```text
manual timeline
→ source validation
→ Demucs
→ analysis
→ first-15-second YouTube synchronization
→ global offset
→ exact visual extraction
→ static 80% centered visual
→ exact stem crop
→ 8D audio
→ LRC line-by-line lyrics with word highlighting
→ NVENC render
→ final assembly
→ validation
→ provenance
```

The two most important authoritative inputs are:

```text
songs/final/<basename>.mp3
hook_timeline.json
```

The authoritative manual hook entry is:

```json
"hook": {
  "start": "02:12.92",
  "end": "03:11.72"
}
```

The system must use that interval exactly, without a maximum-duration policy and without automatically replacing it with another hook.

The final Reel's audio comes from the local song's Demucs stems, not YouTube.

YouTube contributes only the visual timing reference through one simple first-15-second global offset.

The final video is a centered static 80%-height panel on a 1080×1920 canvas.

Lyrics are displayed one LRC line at a time with per-word highlighting.

The project remains completely independent from Phase 1 and Phase 2 implementation internals.

---

# 56. VERSION / CHANGE HISTORY REFERENCE

The implementation evolved through multiple builds while debugging real Windows runs. The meaningful progression was:

```text
V1.0.1  Windows UTF-8 / FFprobe reliability fix
V1.0.2  Circular JSON match-result fix
V1.0.3  Simplified YouTube hook matching
V1.0.4  Path fix + NVIDIA/NVENC rendering
V1.0.5  NVENC compatibility + broken-pipe protection
V1.0.6  Advanced Smart Crop experiment (later rolled back)
V1.0.7  Rollback + 40s experiment + stem 8D implementation
V1.0.8  Manual hook JSON architecture + Smart Crop removal + LRC line rendering
V1.0.9  --fillhookjson
V1.0.10 automatic hook JSON synchronization at startup
V1.0.11 no duration cap + simplified global offset
V1.0.12 exact guarded video trim / cache correction
V1.0.13 first-15-second YouTube anchor synchronization
V1.0.14 guard-aware trimming + better validation diagnostics
V1.0.15 trim_start propagation regression fix
V1.0.16 80% static panel + final validation correction
```

These version notes are historical. The **current design is defined by the requirements in Sections 2 through 55**, not by any older experimental behavior.

---

# 57. FINAL PROJECT STATEMENT

Phase 3 is a standalone, deterministic Telugu music Reel generator driven by manually selected hook timelines.

It accepts a local song package, automatically maintains a user-editable hook plan, calculates one simple visual synchronization offset from the first 15 seconds of the original song, extracts the exact visual interval from the selected YouTube video, creates the final Reel audio from exact Demucs stem crops with controlled 8D spatialization, renders LRC lyrics line by line with per-word highlighting, places the video as a centered 80%-height panel in a 1080×1920 canvas, uses NVIDIA acceleration where available, and produces a validated MP4 plus independent provenance JSON without touching the upstream input package.

The system is intentionally not an automatic hook recommender and intentionally not a smart-crop tracker. The user's hook timeline is the source of truth.
