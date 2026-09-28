# PHASE 3 — AUTOMATED SHORT-FORM REEL GENERATION
## Complete Ultra-Detailed Production Project Plan — Final Consolidated Specification

**Document status:** Final consolidated engineering specification after complete design review and workflow lock

**Project:** Phase 3 only — standalone short-form Reel generation from a local song package

**Primary purpose:** Analyse each song independently, discover the strongest short-form musical/lyrical hook, locate the corresponding section inside the complete selected YouTube music-video audio, download only that video section, intelligently reframe it to 9:16, generate a timeline-preserving spatial/8D audio version from the user's own song, render word-level Telugu karaoke lyrics, and save the completed Reel together with a complete provenance JSON record.

**Input model:** A local folder containing exact-basename `MP3 + LRC + JSON` song packages.

**Output model:** `MP4 Reel + Reel JSON` per song.

**Publishing model:** Manual Instagram upload by the user. Phase 3 does not upload or publish to Instagram.

**External video source:** The YouTube video ID already present in the input JSON is used as the video source identifier. Phase 3 does not depend on Phase 1 software, Phase 1 databases, or Phase 1 runtime state.

**Language focus:** Telugu lyrics and Telugu song content, while keeping the implementation extensible to other languages.

**Audio source policy:** The final Reel audio always comes from the local source song. YouTube audio is downloaded only temporarily for matching the selected song segment to the corresponding video timeline. YouTube audio is never used as final Reel audio.

**Primary compute target:** RTX 5050 laptop. Demucs uses CUDA when available. Video tracking runs primarily on CPU to preserve GPU memory for audio separation. FFmpeg encoding may use hardware H.264 encoding when explicitly configured and available, otherwise CPU encoding is supported.

---

# 1. EXECUTIVE DEFINITION

Phase 3 is a completely standalone project.

The only runtime contract is a local `songs/final/` directory containing song packages such as:

```text
phase3_project/
└── songs/
    └── final/
        ├── Song A.mp3
        ├── Song A.lrc
        ├── Song A.json
        ├── Song B.mp3
        ├── Song B.lrc
        └── Song B.json
```

The package relationship is exact-basename based. `Song A.mp3` must use `Song A.lrc` and `Song A.json`.

The source package is read-only.

Phase 3 does not import, call, modify, or require Phase 1 or Phase 2 Python code, databases, modules, virtual environments, state machines, checkpoints, or runtime directories. The only relationship is the file contract.

This preserves the standalone file-level handoff model already used by the upstream project: a song package consists of same-basename audio, lyric, and JSON files, while the JSON contains the detailed machine-readable history and word-level timing data. fileciteturn0file1L17-L25 fileciteturn0file1L2309-L2329

The source JSON may contain a selected YouTube music-video record such as:

```json
"youtube_video": {
  "selected": true,
  "video_id": "...",
  "url": "...",
  "title": "..."
}
```

Phase 3 reads that information as input data; it does not know which upstream project created it. fileciteturn0file0L2504-L2518

The complete conceptual pipeline is:

```text
Local Song Package
        │
        ├── MP3
        ├── LRC
        └── JSON
        │
        ▼
[1] Input validation + hashing
        │
        ▼
[2] Full-song Demucs separation
        │
        ▼
[3] Full-song acoustic analysis
        │
        ▼
[4] Full-song lyric / repetition / phrase analysis
        │
        ▼
[5] Song structure and recurring-section discovery
        │
        ▼
[6] Hook-core candidate generation
        │
        ▼
[7] Hook candidate scoring + hard filtering
        │
        ▼
[8] Hook-family clustering + diversity selection
        │
        ▼
[9] 10–15 distinct finalist hooks
        │
        ▼
[10] Natural context expansion
        │       ├── lead-in search
        │       └── tail / ending search
        │
        ▼
[11] Final Reel-segment selection
        │
        ▼
[12] Extract clean source-song Reel audio
        │
        ▼
[13] Download complete YouTube video audio only
        │
        ▼
[14] Search complete YouTube audio for the selected source segment
        │
        ▼
[15] Multi-stage audio matching + confidence verification
        │
        ▼
[16] Determine exact matching video timestamps
        │
        ▼
[17] Download only the required video section + guard band
        │
        ▼
[18] Exact video trim
        │
        ├──────────────────────────┐
        ▼                          ▼
[19] Smart 9:16 crop          [20] Timeline-preserving 8D audio
        │                          │
        └──────────────┬───────────┘
                       ▼
                [21] Word karaoke
                       │
                       ▼
                [22] Final assembly
                       │
                       ▼
                [23] Cross-output validation
                       │
                       ▼
                [24] Save Reel MP4
                       │
                       ▼
                [25] Save Reel JSON
                       │
                       ▼
                [26] Hash + finalize state
                       │
                       ▼
                Manual Instagram upload
```

The original Phase 3 design already established the important ideas of regenerating Demucs in Phase 3, deferring video acquisition, using smart 9:16 cropping, using the song's stems for spatial processing, and preserving the input package. Those ideas remain, but the hook discovery, matching, state management, and output architecture are expanded substantially. fileciteturn0file2L23-L34

---

# 2. NON-NEGOTIABLE ARCHITECTURAL REQUIREMENTS

## 2.1 Phase 3 is standalone

Phase 3 must not:

- import Phase 1 code;
- import Phase 2 code;
- connect to Phase 1 SQLite;
- connect to Phase 2 SQLite;
- assume a sibling Phase 1 or Phase 2 project exists;
- read a Phase 1 database for the YouTube ID;
- read a Phase 2 database for word timings;
- depend on upstream Python package versions;
- depend on upstream runtime state.

The local package under `songs/final/` is the only upstream interface.

## 2.2 Input directory is strictly read-only

```text
songs/final/
```

must be treated as immutable input.

Phase 3 may read, hash, inspect, and copy these files into its own temporary working area, but it must never:

- overwrite an input MP3;
- rewrite an input LRC;
- rewrite an input JSON;
- rename input files;
- move input files;
- delete input files;
- write temp files beside input files;
- change input metadata or permissions unnecessarily.

This follows the upstream package philosophy where the final song package is a published file set and subsequent processing is expected to preserve its contents. fileciteturn0file1L59-L76

## 2.3 Exact basename matching

Given:

```text
SongName.mp3
```

Phase 3 requires:

```text
SongName.lrc
SongName.json
```

No fuzzy matching is permitted.

## 2.4 The MP3 is the canonical final-audio source

All final Reel audio must originate from the local MP3.

The YouTube audio download exists only for temporal matching and source-video localization.

The YouTube audio must never replace or become the final Reel audio.

## 2.5 Demucs is executed inside Phase 3

Phase 3 must not assume Demucs stems exist in the input folder.

Demucs runs on the complete local source MP3 during every fresh processing run that requires them.

The original Phase 3 specification already established this because upstream processing may remove stems after finalization. fileciteturn0file2L26-L34

## 2.6 Hook duration is content-driven

The Reel is not architecturally fixed to 30 seconds.

The selector discovers:

1. a strong hook core;
2. a natural lead-in;
3. an optional natural tail/end;
4. the final Reel segment.

The default search space should permit variable durations.

A practical default configuration is:

```text
Hook core:       10–35 seconds
Lead-in:          0.5–5 seconds
Tail:             0–5 seconds
Final Reel:       15–60 seconds by default
Preferred target: approximately 25–35 seconds when content quality is similar
```

These are search bounds, not hard architectural requirements. The final duration is selected from content quality.

## 2.7 Lead-in is explicitly part of hook quality

A 2–3 second lead-in is preferred when it improves musical flow.

The selector must be allowed to choose 0.5–5 seconds rather than blindly prepend exactly 3 seconds.

A lead-in may contain:

- instrumental pickup;
- chord change;
- drum buildup;
- vocal pickup;
- rising energy;
- transition into the lyric hook.

The lead-in is optional when immediate hook entry is stronger.

## 2.8 YouTube video is acquired in two steps

The pipeline must not download the complete high-resolution video up front.

Instead:

```text
YouTube ID
    ↓
complete video audio only
    ↓
match selected source-song Reel segment
    ↓
locate exact video timestamps
    ↓
download only required video section
```

## 2.9 No global-offset-only synchronization model

The core synchronization problem is not “find one global offset between two entire songs.”

The correct model is:

> Find the best matching occurrence of the selected source-song segment inside the complete YouTube video audio.

A derived offset can be calculated after a match is found, but the primary result is:

```text
video_match_start_ms
video_match_end_ms
match_confidence
```

## 2.10 Final video must be 9:16

Final output resolution:

```text
1080 × 1920
```

No black bars.

No stretching.

No distortion.

## 2.11 Smart crop must be stateful

The crop engine must track a subject through time rather than independently choosing a face every frame.

It should support:

- face detection;
- pose/body fallback;
- subject identity persistence;
- temporal smoothing;
- position prediction;
- bounded camera movement;
- safe-zone-aware composition.

## 2.12 Final audio timeline must remain synchronized

8D processing must not change the timeline relative to the original source clip.

No time-changing effect may be applied without explicitly propagating the transformation through video and lyrics.

The default Phase 3 audio engine therefore uses only timeline-preserving processing.

## 2.13 No fingerprint-evasion subsystem

Pitch/speed modification must not be implemented as a copyright or fingerprint-bypass mechanism.

Creative audio effects are permitted only for the intended spatial/audio aesthetic and must preserve synchronization.

## 2.14 No Instagram API

Phase 3 ends after creating and validating:

```text
SongName_reel.mp4
SongName_reel.json
```

The user manually uploads the Reel to Instagram.

Phase 3 contains no:

- Graph API credentials;
- cloud-staging dependency;
- upload endpoint;
- publication polling;
- media publishing state;
- automatic caption publishing;
- Instagram account integration.

## 2.15 Reel JSON is a separate Phase 3 output

The input `SongName.json` is never modified.

Phase 3 produces:

```text
reels/generated/SongName_reel.json
```

This JSON contains the complete Reel-generation provenance and result.

## 2.16 Manual hook override is an explicit rerun mode

The default pipeline always performs the complete automatic hook-analysis system.

A separate command allows the operator to supply an exact source-song timeline when the operator already knows which portion of the song should be used:

```bash
python main.py --manualhook SongName
```

The command prompts for:

```text
Start time [HH:MM:SS.mmm]:
End time   [HH:MM:SS.mmm]:
```

An equivalent non-interactive form is supported:

```bash
python main.py --manualhook SongName --start 00:02:14.200 --end 00:02:34.800
```

Manual mode does not replace or weaken the automatic hook engine. It only bypasses hook discovery/ranking for that run. Every downstream stage remains identical: source-audio extraction, YouTube audio matching, video-section acquisition, smart crop, 8D audio, centered Telugu karaoke, validation, and final JSON generation.

The manual source-song timeline is authoritative for that run and is recorded in the output JSON with `hook_selection.mode = "manual"`.

---

# 3. INPUT CONTRACT

## 3.1 Required files

Each input song package must contain:

```text
songs/final/<basename>.mp3
songs/final/<basename>.lrc
songs/final/<basename>.json
```

## 3.2 MP3 requirements

The MP3 must:

- exist;
- be readable;
- have a valid audio stream;
- have finite duration;
- have a usable sample rate;
- decode through FFmpeg/FFprobe;
- remain bit-for-bit unchanged during Phase 3 processing.

## 3.3 LRC requirements

The LRC must:

- exist;
- parse successfully;
- contain the lyric wording used for rendering;
- contain line timing;
- correspond to the song's duration.

## 3.4 JSON requirements

The JSON must:

- parse as valid JSON;
- contain the word-level timeline required by the lyric renderer;
- contain the selected YouTube video information needed for video acquisition;
- preserve its own input hash in Phase 3 provenance;
- remain untouched on disk.

The upstream word-level JSON representation is designed around `phase2.alignment.lines[].words[]`, with each word carrying `original`, `normalized`, `start_ms`, `end_ms`, `score`, and `source`. Phase 3 treats those fields as input data, not as an application dependency on Phase 2 code. fileciteturn0file1L2309-L2329

## 3.5 YouTube ID requirements

Phase 3 obtains the selected video identifier from the local JSON input, typically from:

```text
youtube_video.video_id
```

If no usable selected video ID exists, the song cannot proceed to the video stage.

## 3.6 Missing-file behavior

Missing MP3:

```text
INPUT_MP3_MISSING
```

Missing LRC:

```text
INPUT_LRC_MISSING
```

Missing JSON:

```text
INPUT_JSON_MISSING
```

Invalid JSON:

```text
INPUT_JSON_INVALID
```

Missing word-level timeline:

```text
WORD_TIMELINE_MISSING
```

Missing YouTube video ID:

```text
YOUTUBE_VIDEO_ID_MISSING
```

Default policy is to mark the song as failed/needs review rather than fabricate missing data.

---

# 4. INPUT FINGERPRINTING AND PROCESSING IDENTITY

For every input package calculate SHA-256:

```text
mp3_sha256
lrc_sha256
json_sha256
```

Also store:

```text
file sizes
source modification timestamps
pipeline_version
config_hash
model identifiers
model revisions
```

A processing identity is derived from at least:

```text
basename
mp3_sha256
lrc_sha256
json_sha256
pipeline_version
config_hash
demucs_model + revision
hook_algorithm_version
video_match_algorithm_version
crop_algorithm_version
audio_8d_algorithm_version
lyric_renderer_version
```

If the same identity already has a validated completed Reel package, the pipeline may skip the song unless forced.

If any identity component changes, the song becomes eligible for reprocessing.

---

# 5. PROJECT DIRECTORY STRUCTURE

```text
phase3_project/
│
├── main.py
├── config.json
├── requirements.lock
├── README.md
├── CHANGELOG.md
├── BUILD_INFO.md
├── .gitignore
│
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── db.py
│   ├── scanner.py
│   ├── package_validator.py
│   ├── hashing.py
│   ├── audio_io.py
│   ├── stem_isolator.py
│   ├── acoustic_analyzer.py
│   ├── lyric_reader.py
│   ├── lyric_analyzer.py
│   ├── phrase_repetition.py
│   ├── song_structure.py
│   ├── hook_candidates.py
│   ├── hook_scorer.py
│   ├── hook_diversity.py
│   ├── hook_context.py
│   ├── hook_selector.py
│   ├── youtube_info.py
│   ├── youtube_audio.py
│   ├── audio_match.py
│   ├── video_grabber.py
│   ├── subject_tracker.py
│   ├── smart_crop_engine.py
│   ├── video_renderer.py
│   ├── audio_8d.py
│   ├── lyric_renderer.py
│   ├── ass_generator.py
│   ├── assembler.py
│   ├── validator.py
│   ├── output_json.py
│   ├── recovery.py
│   ├── pipeline.py
│   └── utils.py
│
├── songs/
│   └── final/                  # USER-COPIED INPUT; READ ONLY
│       ├── SongName.mp3
│       ├── SongName.lrc
│       └── SongName.json
│
├── reels/
│   └── generated/              # FINAL PHASE 3 OUTPUT
│       ├── SongName_reel.mp4
│       └── SongName_reel.json
│
├── temp/
│   └── {song_key}/
│       ├── input_snapshot/
│       │   ├── source.mp3
│       │   ├── source.lrc
│       │   └── source.json
│       │
│       ├── stems/
│       │   ├── vocals.wav
│       │   ├── drums.wav
│       │   ├── bass.wav
│       │   └── other.wav
│       │
│       ├── analysis/
│       │   ├── acoustic_features.json
│       │   ├── lyric_analysis.json
│       │   ├── phrase_clusters.json
│       │   ├── song_structure.json
│       │   ├── hook_candidates.json
│       │   └── hook_rankings.json
│       │
│       ├── selected/
│       │   ├── hook_core.wav
│       │   ├── reel_source.wav
│       │   └── selected_segment.json
│       │
│       ├── youtube/
│       │   ├── metadata.json
│       │   └── full_video_audio.m4a
│       │
│       ├── matching/
│       │   ├── coarse_matches.json
│       │   ├── fine_matches.json
│       │   └── best_video_match.json
│       │
│       ├── video/
│       │   ├── downloaded_with_guard.mp4
│       │   ├── exact_segment.mp4
│       │   ├── tracking.json
│       │   └── video_9x16.mp4
│       │
│       ├── audio/
│       │   ├── reel_vocals.wav
│       │   ├── reel_drums.wav
│       │   ├── reel_bass.wav
│       │   ├── reel_other.wav
│       │   └── reel_8d.wav
│       │
│       ├── lyrics/
│       │   ├── lyrics.ass
│       │   └── lyric_render_plan.json
│       │
│       ├── stage_final/
│       │   ├── SongName_reel.mp4
│       │   └── SongName_reel.json
│       │
│       └── logs/
│           └── song.log
│
├── db/
│   └── phase3.db
│
└── logs/
    └── phase3.log
```

Temporary data may be deleted after successful finalization unless configured to retain analysis artifacts for debugging.

---

# 6. RUNTIME DEPENDENCIES

## 6.1 Python

Recommended:

```text
Python 3.11+
```

## 6.2 Python packages

Core:

```text
numpy
scipy
librosa
soundfile
torch
torchaudio
demucs
opencv-python
mediapipe
yt-dlp
requests
```

Likely support utilities:

```text
Pillow
mutagen
orjson (optional)
psutil
pytest
```

## 6.3 External binaries

Required:

```text
ffmpeg
ffprobe
```

Potentially required by yt-dlp depending on environment:

```text
supported JavaScript runtime
```

## 6.4 Runtime doctor

The project must provide:

```bash
python main.py --doctor
```

The doctor checks:

- Python version;
- FFmpeg;
- FFprobe;
- CUDA visibility;
- PyTorch CUDA support;
- Demucs availability;
- MediaPipe availability;
- yt-dlp availability;
- output directory writability;
- database writability;
- required config keys;
- required input directory.

---

# 7. CONFIGURATION

The configuration must expose tuning values without turning architectural rules into optional behavior.

Recommended structure:

```json
{
  "paths": {
    "input_dir": "songs/final",
    "output_dir": "reels/generated",
    "temp_dir": "temp",
    "db_path": "db/phase3.db",
    "logs_dir": "logs"
  },

  "input": {
    "recursive": false,
    "require_json": true,
    "require_word_timing": true,
    "require_youtube_video_id": true
  },

  "demucs": {
    "model": "htdemucs",
    "device": "cuda",
    "fallback_to_cpu": true,
    "sample_rate": 44100,
    "keep_stems_after_success": false
  },

  "hook_selection": {
    "candidate_step_ms": 1000,
    "core_min_ms": 10000,
    "core_max_ms": 35000,
    "final_min_ms": 15000,
    "final_max_ms": 60000,
    "preferred_lead_in_ms": 2500,
    "min_lead_in_ms": 500,
    "max_lead_in_ms": 5000,
    "preferred_tail_ms": 1500,
    "max_tail_ms": 5000,
    "finalist_count_min": 10,
    "finalist_count_max": 15,
    "same_family_overlap_ratio": 0.50,
    "same_family_lyric_similarity": 0.80,
    "preferred_core_types": [
      "CHORUS",
      "FINAL_CHORUS",
      "REFRAIN",
      "VOCAL_HIGHLIGHT",
      "BUILD"
    ],
    "weights": {
      "lyric_memorability": 0.25,
      "vocal_quality": 0.20,
      "repetition_strength": 0.15,
      "musical_energy": 0.10,
      "arrangement_richness": 0.10,
      "energy_contour": 0.10,
      "phrase_completeness": 0.05,
      "timing_quality": 0.05
    },
    "context_weights": {
      "lead_in_buildup": 0.35,
      "hook_entry_cleanliness": 0.25,
      "ending_quality": 0.20,
      "lyric_continuity": 0.10,
      "musical_continuity": 0.10
    }
  },

  "video_match": {
    "coarse_sample_rate": 16000,
    "coarse_frame_hz": 10,
    "top_candidates": 5,
    "anchor_count": 5,
    "anchor_duration_ms": 5000,
    "fine_search_radius_ms": 3000,
    "min_confidence": 0.75,
    "max_anchor_residual_ms": 100,
    "use_chroma": true,
    "use_log_mel": true,
    "use_energy_envelope": true,
    "use_waveform_fine_alignment": true,
    "allow_small_tempo_variation": true,
    "tempo_search_percent": 1.5,
    "guard_before_ms": 1500,
    "guard_after_ms": 1500
  },

  "smart_crop": {
    "output_width": 1080,
    "output_height": 1920,
    "face_confidence_threshold": 0.5,
    "pose_confidence_threshold": 0.5,
    "lost_subject_fallback_ms": 1500,
    "hard_center_fallback_ms": 5000,
    "smoothing_sigma": 5,
    "max_pan_speed_px_per_second": 900,
    "max_pan_acceleration_px_per_second2": 1800,
    "target_face_y": 700,
    "target_body_y": 850,
    "lyrics_safe_top": 1230,
    "lyrics_safe_bottom": 1510,
    "horizontal_safe_left": 70,
    "horizontal_safe_right": 1010
  },

  "audio_8d": {
    "target_lufs": -14.0,
    "true_peak_db": -1.0,
    "vocal_pan": 0.0,
    "bass_pan": 0.0,
    "drums_center_weight": 0.85,
    "drums_stereo_width": 0.15,
    "other_lfo_width_verse": 0.40,
    "other_lfo_width_chorus": 0.80,
    "other_lfo_frequency_verse_hz": 0.05,
    "other_lfo_frequency_chorus_hz": 0.10,
    "chorus_reverb_mix": 0.15,
    "chorus_reverb_increase": 0.20,
    "haas_delay_ms": 15,
    "haas_gain_db": -12.0,
    "fade_in_ms": 150,
    "fade_out_ms": 250,
    "preserve_timeline": true
  },

  "lyrics": {
    "enabled": true,
    "use_word_level_json": true,
    "use_lrc_for_text_validation": true,
    "font_size": 54,
    "font_bold": true,
    "shadow": 3,
    "max_lines": 2,
    "max_words_per_visual_line": 8,
    "safe_top": 1230,
    "safe_bottom": 1510,
    "active_word_mode": "karaoke"
  },

  "video": {
    "yt_dlp_binary": "yt-dlp",
    "download_timeout_seconds": 600,
    "metadata_timeout_seconds": 120,
    "video_format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "audio_format": "bestaudio/best"
  },

  "render": {
    "video_codec": "h264_nvenc",
    "video_codec_fallback": "libx264",
    "preset": "fast",
    "crf": 18,
    "audio_codec": "aac",
    "audio_bitrate": "192k",
    "faststart": true
  },

  "recovery": {
    "max_attempts_per_stage": 3,
    "retry_backoff_seconds": 2,
    "keep_failed_temp": true,
    "keep_success_temp": false
  }
}
```

No `instagram`, `cloud_storage`, or publishing section exists in the final architecture.

---

# 8. BATCH SCANNER AND PACKAGE VALIDATION

## 8.1 Scan

Default scan:

```text
songs/final/*.mp3
```

For each MP3:

1. derive basename;
2. locate exact `.lrc`;
3. locate exact `.json`;
4. validate package;
5. calculate hashes;
6. compare against database state;
7. schedule processing if required.

## 8.2 Duplicate basename collision

There must not be two input packages that resolve to the same basename.

Collision:

```text
INPUT_BASENAME_COLLISION
```

## 8.3 Package consistency checks

Validate:

```text
MP3 exists
LRC exists
JSON exists
MP3 decodes
LRC parses
JSON parses
word timeline exists
YouTube video ID exists
```

Also verify:

```text
word timestamps fall within source duration
LRC and JSON lyric ordering are consistent
```

---

# 9. FULL-SONG AUDIO PREPARATION

## 9.1 Canonical source audio

Decode the MP3 into a processing representation without altering the source file.

Recommended analysis representation:

```text
mono
16 kHz or configurable analysis rate
float32
```

Keep a full-quality representation where needed for Demucs and final audio rendering.

## 9.2 Duration

Record:

```text
source_duration_ms
sample_rate
channels
```

These become part of Reel JSON provenance.

---

# 10. DEMUCS STEM SEPARATION

## 10.1 Run once per processing identity

Run Demucs on the complete source song.

Output:

```text
vocals.wav
drums.wav
bass.wav
other.wav
```

## 10.2 GPU policy

Preferred:

```text
CUDA
```

Fallback:

```text
CPU
```

If CUDA OOM occurs:

1. clear CUDA cache;
2. retry with reduced resource usage if configured;
3. fallback to CPU;
4. record fallback in JSON.

## 10.3 Stem validation

Every stem must:

- exist;
- decode;
- have expected duration within tolerance;
- have finite numeric samples.

## 10.4 Why Demucs is central to hook selection

Demucs supplies independent evidence for:

```text
vocal presence
vocal prominence
drum activity
bass support
instrumental richness
arrangement changes
energy buildup
```

The stems are not merely generated for the later 8D engine; they are a primary signal source for hook discovery.

---

# 11. FULL-SONG ACOUSTIC FEATURE EXTRACTION

Generate time-aligned features across the whole song.

## 11.1 Vocal features

Calculate:

- RMS energy;
- peak energy;
- active-vocal ratio;
- vocal-to-mix ratio;
- vocal-to-instrument ratio;
- dynamic variation;
- sustained-vocal duration;
- vocal onset activity;
- local vocal maxima.

## 11.2 Drum features

Calculate:

- onset strength;
- onset density;
- percussive RMS;
- beat activity;
- kick/snare proxy activity if extractable;
- rhythmic change.

## 11.3 Bass features

Calculate:

- RMS;
- onset activity;
- low-frequency energy;
- energy transitions;
- bass-to-mix ratio.

## 11.4 Other-stem features

Calculate:

- harmonic energy;
- spectral energy;
- instrumental density;
- spectral flux;
- arrangement changes.

## 11.5 Full-mix features

Calculate:

- RMS envelope;
- loudness;
- spectral centroid;
- spectral flux;
- onset envelope;
- local contrast;
- silence/low-energy regions;
- energy slope;
- energy peak locations.

## 11.6 Feature normalization

Raw values must not be combined directly.

Each feature is normalized relative to the song, preferably by percentile/rank or robust min-max based on the candidate population.

Example:

```text
vocal_energy_percentile
lyric_density_percentile
beat_energy_percentile
```

This prevents a raw word count or RMS value from dominating another feature purely because of scale.

---

# 12. FULL-SONG LYRIC ANALYSIS

The lyric analyzer reads the line-level LRC and the word-level JSON timeline.

## 12.1 Data model

For each lyric word record, retain:

```text
original
normalized
start_ms
end_ms
score
source
line_index
word_index
```

The upstream JSON structure is explicitly designed to make the word-level timeline self-contained. fileciteturn0file1L2309-L2329

## 12.2 Derived lyric metrics

Calculate:

- words per second;
- words per line;
- line durations;
- inter-line gaps;
- word-gap durations;
- lyric-free sections;
- phrase length;
- phrase completeness;
- repeated phrases;
- repeated lines;
- repeated n-grams;
- local repetition;
- phrase recurrence across song;
- occurrence count.

## 12.3 Repetition analysis

Search for repeated meaningful sequences of approximately 2–5 words.

Also compare entire lyric lines.

Single-word repetition receives a low repetition contribution unless the word is part of a larger repeated structure.

## 12.4 Phrase clusters

Create clusters of similar phrases.

Each cluster records:

```text
cluster_id
canonical_phrase
variants
occurrence_count
occurrence_times
similarity_score
```

## 12.5 Chorus/refrain evidence

A section becomes strong chorus/refrain evidence when:

- similar phrases recur multiple times;
- the audio structure also repeats;
- the vocal activity is substantial;
- the section is not predominantly instrumental.

## 12.6 Local repetition

Reward a candidate when the selected interval contains repeated meaningful language.

Example:

```text
A B C A B C
```

should score higher than an equally dense sequence of unique words when all other factors are similar.

---

# 13. SONG STRUCTURE DISCOVERY

The structure detector is not required to perfectly label music theory sections.

Its purpose is to identify useful computational regions.

Possible labels:

```text
INTRO
VERSE
PRE_CHORUS
CHORUS
REFRAIN
BRIDGE
BUILD
DROP
FINAL_CHORUS
OUTRO
INSTRUMENTAL
VOCAL_HIGHLIGHT
OTHER
```

## 13.1 Evidence sources

Use:

- repeated lyric phrase timing;
- acoustic similarity;
- vocal energy;
- onset structure;
- arrangement changes;
- energy transitions;
- lyric-free gaps.

## 13.2 Repeated-section matching

If similar content occurs at:

```text
00:45–01:10
02:05–02:30
03:20–03:45
```

identify these as one recurring section family.

The strongest occurrence is not automatically the first.

---

# 14. ADVANCED HOOK CORE DISCOVERY

This replaces the simple “best 30-second window” model.

The fundamental question is:

> Where is the most memorable short-form musical and lyrical moment in the song?

## 14.1 Candidate sources

Generate hook-core candidates from multiple evidence families.

### A. Repeated lyric phrases

For every high-value repeated phrase:

- center a candidate around the phrase;
- include enough words before/after it to form a coherent unit;
- generate several nearby duration variants.

### B. Repeated lyric lines

For repeated lines:

- generate candidate around each occurrence;
- compare acoustic strength of occurrences.

### C. Chorus/refrain sections

Generate candidates around identified chorus/refrain occurrences.

### D. Vocal peaks

Generate candidates around strong vocal-energy peaks, even when repetition is weak.

### E. Musical peaks

Generate candidates around strong drum/onset/arrangement peaks.

### F. Build → payoff transitions

Generate candidates that capture:

```text
setup → build → payoff
```

rather than only the peak itself.

### G. Vocal entrances

Generate candidates beginning slightly before a memorable vocal phrase.

## 14.2 Variable core durations

Core durations should be content-driven.

Use candidate ranges such as:

```text
10 s
12 s
14 s
16 s
18 s
20 s
22 s
24 s
26 s
28 s
30 s
32 s
35 s
```

The exact list may be continuous in implementation; the above values illustrate the intended search space.

## 14.3 Phrase-boundary optimization

Do not force candidate boundaries to arbitrary one-second grid points when lyric structure provides better boundaries.

Test nearby timelines and favor:

- phrase beginnings;
- phrase endings;
- musical phrase endings;
- beat-aligned starts;
- natural transitions.

Avoid:

- word splits;
- unfinished lyric lines when avoidable;
- cutting sustained notes;
- ending in an unstable musical transition.

---

# 15. HOOK CORE SCORING

Each candidate receives a complete feature vector.

Recommended top-level weights:

```text
Lyric Memorability             25%
Vocal Quality                  20%
Phrase Repetition              15%
Musical / Rhythmic Energy      10%
Arrangement Richness            10%
Energy Contour                  10%
Phrase Completeness              5%
Timing Quality                   5%
```

## 15.1 Lyric Memorability

Composite:

```text
phrase recurrence               25%
repeated-line strength          20%
lyric density                   15%
local repetition                15%
phrase completeness             15%
lyric continuity                10%
```

## 15.2 Vocal Quality

Composite:

```text
vocal energy                    35%
vocal prominence                25%
vocal continuity                20%
vocal clarity / separation      20%
```

## 15.3 Phrase Repetition

Measure:

- repeated 2–5 word n-grams;
- repeated lines;
- recurrence count;
- phrase similarity;
- presence of the refrain within the candidate.

## 15.4 Musical / Rhythmic Energy

Composite:

```text
drum/onset activity             40%
bass support                     20%
other-stem energy                20%
overall dynamic movement          20%
```

## 15.5 Arrangement Richness

Reward useful combinations such as:

```text
vocal + drums + bass + harmonic layer
```

and arrangement changes that create perceived impact.

Do not simply maximize instrumental loudness.

## 15.6 Energy Contour

Reward useful shapes such as:

```text
build → impact
pickup → chorus
vocal entrance → rise → payoff
```

A flat high-energy region can still score well, but it does not automatically beat a stronger setup/payoff shape.

## 15.7 Phrase Completeness

Reward candidates that preserve complete semantic/musical phrases.

## 15.8 Timing Quality

Reward candidates with:

- strong word-level timing confidence;
- clean phrase boundaries;
- low alignment uncertainty;
- no problematic timing gaps.

---

# 16. HARD HOOK CANDIDATE FILTERS

Candidates are rejected or strongly penalized when they contain:

- excessive silence;
- overwhelmingly instrumental content when a lyric-driven hook is expected;
- insufficient vocal activity;
- too few usable lyric words;
- unresolved word timing;
- severe clipping of lyric phrases;
- unstable boundaries;
- excessive low-quality/interpolated timing;
- unusable extremely early/late positions without adequate context.

Instrumental content is not automatically forbidden.

A short instrumental lead-in or musical payoff can be beneficial.

---

# 17. HOOK FAMILY CLUSTERING

Raw sliding candidates will often represent the same underlying moment.

Example:

```text
01:42–02:10
01:43–02:11
01:44–02:12
01:45–02:13
```

These are one hook family, not four different hooks.

## 17.1 Same-family rules

Two candidates may belong to the same family when:

```text
timeline overlap >= configured threshold
```

or:

```text
lyric similarity >= configured threshold
```

## 17.2 Family representative

Keep the highest-quality candidate from each family.

## 17.3 Occurrence diversity

Prefer finalists distributed across different locations in the song.

---

# 18. 10–15 DISTINCT HOOK FINALISTS

After candidate generation, filtering, and family deduplication, produce approximately:

```text
10–15 distinct finalists
```

The finalists should be genuinely different in one or more of:

- timeline region;
- lyric phrase;
- chorus/refrain occurrence;
- musical character;
- setup/payoff structure.

For example:

```text
#1 final chorus       31.4s
#2 chorus occurrence  27.8s
#3 refrain            22.9s
#4 vocal highlight    19.7s
#5 build + chorus     34.2s
#6 repeated phrase    25.5s
#7 verse payoff       23.1s
...
```

The candidate durations are allowed to differ.

---

# 19. HOOK CONTEXT EXPANSION

Each hook core is expanded into possible Reel segments.

## 19.1 Lead-in search

For every hook core:

```text
0.5 s
1.0 s
1.5 s
2.0 s
2.5 s
3.0 s
3.5 s
4.0 s
5.0 s
```

or equivalent continuous search.

The preferred lead-in is approximately 2–3 seconds, but this is not mandatory.

## 19.2 Lead-in scoring

Evaluate:

- energy rise;
- drum pickup;
- chord/arrangement change;
- vocal pickup;
- transition smoothness;
- distance to hook onset;
- whether the viewer hears a meaningful setup.

## 19.3 Lead-in rejection

Reject or reduce a lead-in when it adds:

- silence;
- unrelated verse material;
- excessive low-energy dead time;
- awkward partial lyric fragments;
- disruptive transitions.

## 19.4 Tail search

Search after the hook for:

```text
0–5 seconds
```

Reward:

- complete phrase;
- sustained note resolution;
- musical cadence;
- repeat/payoff;
- natural ending.

## 19.5 Context score

Recommended:

```text
Lead-in buildup             35%
Hook-entry cleanliness      25%
Ending/payoff quality       20%
Lyric continuity            10%
Musical continuity          10%
```

---

# 20. FINAL REEL SEGMENT SCORING

The final selected Reel segment should combine:

```text
75% hook-core quality
25% context quality
```

This prevents context from overpowering the actual hook.

Example:

```text
Hook A:
core = 0.96
context = 0.70
final = 0.895

Hook B:
core = 0.91
context = 0.93
final = 0.915
```

This lets a slightly weaker core win when its complete presentation is significantly better.

---

# 21. SELECTED HOOK OUTPUT

Store the selected hook as:

```json
{
  "core_start_ms": 85000,
  "core_end_ms": 109500,
  "core_duration_ms": 24500,
  "lead_in_ms": 2600,
  "tail_ms": 1800,
  "reel_start_ms": 82400,
  "reel_end_ms": 111300,
  "reel_duration_ms": 28900,
  "type": "FINAL_CHORUS",
  "hook_score": 0.941,
  "context_score": 0.907,
  "final_score": 0.933
}
```

The numbers are illustrative.

---

# 22. MANUAL HOOK MODE

Manual hook mode is a controlled override of the automatic hook selector. It is intended for reruns where the operator wants an exact source-song timeline without changing any other Phase 3 behavior.

## 22.1 Interactive command

```bash
python main.py --manualhook SongName
```

Example interaction:

```text
============================================================
MANUAL HOOK SELECTION
============================================================

Song: SongName

Enter exact source-song hook timeline.
Start time [HH:MM:SS.mmm]:
> 00:02:14.200

End time [HH:MM:SS.mmm]:
> 00:02:34.800

Manual hook: 00:02:14.200 -> 00:02:34.800
Duration: 20.600 seconds

Use this timeline? [Y/n]:
>
```

## 22.2 Non-interactive command

```bash
python main.py --manualhook SongName --start 00:02:14.200 --end 00:02:34.800
```

## 22.3 Validation

The manual timeline must:

- parse exactly;
- have `start_ms >= 0`;
- have `end_ms > start_ms`;
- remain within the source-song duration;
- contain enough audio for the selected downstream video match;
- produce a positive Reel duration.

The manual mode must not silently clamp an invalid operator-entered time. Invalid input should produce a clear error and require correction.

## 22.4 Downstream behavior

After manual selection:

```text
manual source timeline
        ↓
exact source-song segment extraction
        ↓
complete YouTube audio download
        ↓
query-against-complete-video-audio matching
        ↓
exact video segment acquisition
        ↓
smart crop
        ↓
8D processing from local source audio
        ↓
centered Telugu word-level karaoke
        ↓
final Reel + JSON
```

No hook candidate generation is repeated for the manual run. Existing prior automatic analysis artifacts may be retained for inspection but are not used to override the manually supplied timeline.

## 22.5 JSON provenance

Example:

```json
"hook_selection": {
  "mode": "manual",
  "manual": {
    "start_ms": 134200,
    "end_ms": 154800,
    "duration_ms": 20600
  }
}
```

# 23. SOURCE AUDIO SEGMENT EXTRACTION

Once the final Reel segment is selected:

1. extract the exact interval from the original source MP3;
2. store it in a processing WAV;
3. preserve the exact source timeline;
4. do not apply 8D yet;
5. do not apply speed change;
6. do not apply pitch change.

This clean source clip becomes the matching query for the YouTube audio stage.

This is critical:

```text
SOURCE SONG SEGMENT
          │
          ├──► YouTube matching query
          │
          └──► 8D audio processing
```

The same source timeline drives both paths.

---

# 23. YOUTUBE SOURCE IDENTIFICATION

Read the selected YouTube video ID from the input JSON.

Do not search YouTube for a different video inside Phase 3.

Do not hardcode the video ID.

Optional metadata validation may run before download:

- verify the ID resolves;
- verify the video remains accessible;
- verify the returned title roughly corresponds to the selected input JSON record;
- verify an audio stream exists.

If the input video is unavailable:

```text
YOUTUBE_VIDEO_UNAVAILABLE
```

The song is marked failed/needs review.

---

# 24. COMPLETE YOUTUBE AUDIO DOWNLOAD

Download only the complete audio stream.

Purpose:

> Search the complete video song for the exact location of the selected source-song Reel segment.

The full YouTube audio is temporary.

It must not become part of the final Reel audio.

Store metadata such as:

```text
video_id
video_url
video_title
audio_format
audio_sample_rate
audio_duration_ms
file_size
sha256
```

---

# 25. AUDIO MATCHING PROBLEM DEFINITION

The matcher receives:

```text
Query:
    exact selected segment from our source MP3

Reference:
    complete YouTube video audio
```

Goal:

```text
Find best matching start position in reference.
```

Output:

```text
video_match_start_ms
video_match_end_ms
confidence
method
residual_error
anchor_consistency
```

This is query-by-example audio localization, not global-song offset estimation.

---

# 26. MULTI-STAGE VIDEO AUDIO MATCHER

The matcher uses coarse-to-fine processing.

## 26.1 Stage A — normalization

For query and reference:

- convert to mono;
- resample to analysis sample rate;
- remove extreme DC offset;
- robustly normalize level;
- generate required analysis representations.

## 26.2 Stage B — coarse representations

Generate:

### Log-mel representation

Captures broad spectral structure.

### Chroma representation

Captures harmonic progression and is more robust to mastering differences.

### Energy envelope

Captures rhythmic/dynamic shape.

### Optional onset representation

Captures rhythmic events.

## 26.3 Stage C — whole-reference search

Search the entire YouTube audio for likely positions.

Candidate generation may use:

- sliding feature windows;
- normalized correlation;
- multi-feature weighted similarity;
- top-N candidate retention.

Keep the top approximately 5 candidate positions.

## 26.4 Stage D — fine alignment

For each top candidate, search locally around the candidate using:

- higher-resolution log-mel correlation;
- waveform/envelope normalized cross-correlation;
- optional small tempo-variation search;
- optional chroma alignment / DTW.

The purpose is to refine to millisecond-level start timing rather than rely on the coarse representation.

## 26.5 Stage E — multi-anchor verification

Split the selected Reel segment into several anchors, for example:

```text
Anchor 1: lead-in / opening
Anchor 2: early hook
Anchor 3: center
Anchor 4: late hook
Anchor 5: ending / tail
```

Search each independently around the chosen reference location.

A strong match should produce:

```text
all anchors cluster around one continuous timeline
```

A weak match looks like:

```text
anchor 1 → 120.2 s
anchor 2 → 120.9 s
anchor 3 → 201.6 s
anchor 4 → 301.2 s
```

which must be rejected.

## 26.6 Stage F — final confidence

Compute a composite match confidence from:

- coarse feature similarity;
- fine waveform similarity;
- chroma similarity;
- energy-envelope similarity;
- anchor consistency;
- residual timing error;
- optional tempo consistency.

---

# 27. MATCH FAILURE POLICY

Never fall back silently to zero offset.

The original simple fallback behavior is replaced by an explicit failure/review state.

If confidence is below threshold:

```text
VIDEO_MATCH_LOW_CONFIDENCE
```

Do not download an arbitrary video section.

The song remains incomplete until the operator chooses to retry with different matcher settings or inspect it manually.

---

# 28. MATCH RESULT

Example:

```json
{
  "query_start_ms": 82400,
  "query_end_ms": 111300,
  "video_match_start_ms": 102178,
  "video_match_end_ms": 131078,
  "confidence": 0.94,
  "method": "multi_feature_query_localization",
  "coarse_similarity": 0.93,
  "fine_similarity": 0.96,
  "anchor_consistency_ms": 18,
  "max_anchor_residual_ms": 31,
  "tempo_adjustment_percent": 0.0
}
```

---

# 29. VIDEO SECTION DOWNLOAD

Once the video match is accepted, download only the required section.

Use a guard band around the exact interval:

```text
start = match_start - guard_before
end   = match_end + guard_after
```

Default guard:

```text
1.5 seconds before
1.5 seconds after
```

The guard allows safe exact trimming even when the source format uses keyframes that do not line up with the desired timestamps.

The pipeline must not download the full high-resolution video merely to obtain this segment.

---

# 30. EXACT VIDEO TRIM

After section download:

1. decode the downloaded segment;
2. trim to the exact selected Reel duration;
3. start at zero;
4. verify duration against the source-song Reel segment.

Final video duration must equal the source audio duration within configured tolerance.

---

# 31. SMART 9:16 CROP ENGINE

The objective is:

> Convert the source video to 1080×1920 while preserving the most important visual subject and providing space for lyrics.

The crop engine is stateful.

## 31.1 Tracking priority

Primary:

```text
face
```

Fallback:

```text
body/pose
```

Fallback:

```text
predicted last position
```

Final fallback:

```text
safe center crop
```

## 31.2 Multi-person subject selection

The crop engine must support multiple people in the same shot. It must not choose a face independently on every frame.

When multiple people are detected, create candidate identities using:

- face detection confidence;
- face size;
- body/pose association;
- persistence across frames;
- temporal visibility;
- position stability;
- proximity to the current track;
- subject prominence in the shot;
- consistency of appearance/geometry.

The system must explicitly decide between:

```text
focus person A
focus person B
keep persons A+B in frame
use a wider composition
transition from A to B
```

The crop should prefer a stable composition over a rapidly changing highest-confidence face.

## 31.3 Subject identity

Maintain persistent `track_id` values through the duration of each shot. A subject track must contain:

```text
track_id
face_bbox
body_bbox
center_x
center_y
scale
confidence
velocity
visibility
track_age
last_seen_ms
```

Frame-to-frame associations may use:

- centroid distance;
- bounding-box overlap / IoU;
- relative size;
- pose landmarks;
- appearance embedding when available;
- previous predicted position;
- shot-local continuity.

Identity assignment must use hysteresis so the crop does not oscillate:

```text
A -> A -> A -> A -> B
```

is preferred over:

```text
A -> B -> A -> B -> A
```

A hard shot boundary resets or reinitializes identity association. Identities must not be blindly propagated across unrelated shots.

## 31.4 Subject relevance and composition

A subject's relevance score should consider:

- stable visibility;
- screen prominence;
- size;
- centrality;
- persistence;
- whether the shot composition naturally emphasizes that subject;
- whether the subject conflicts with the lyric region.

For multi-person shots, the engine should prefer a joint crop when two or more people form a meaningful composition and can fit without making faces too small.

## 31.5 Tracking state

For every frame or sampled frame store:

```text
frame_index
time_ms
subject_x
subject_y
subject_width
subject_height
confidence
detection_type
track_id
```

## 31.6 Prediction

Use temporal prediction so temporary detection loss does not immediately cause crop jumps.

Recommended mechanisms:

- exponential smoothing;
- bounded velocity;
- optional Kalman-style prediction.

## 31.7 Smoothing

Use Gaussian or equivalent low-pass smoothing as one stage, but combine it with movement constraints.

Gaussian smoothing alone is insufficient because it can still produce undesirable edge motion and can introduce lag.

Use:

```text
raw position
    ↓
confidence-aware smoothing
    ↓
velocity limit
    ↓
acceleration limit
    ↓
boundary clamp
```

## 31.8 9:16 crop geometry

The engine must scale the source enough to fully cover:

```text
1080 × 1920
```

without distortion.

The crop window is then positioned dynamically.

For a typical 16:9 source:

- preserve aspect ratio;
- scale until height or width fully covers the target;
- crop excess horizontal/vertical area;
- never introduce black bars.

## 31.9 Subject vertical placement

Faces should normally occupy an upper-middle region so lyrics have room below.

Target position is configurable.

Example:

```text
face center around y ≈ 700 px
```

not a hard universal constant.

## 31.10 Lyric-aware crop

The crop engine must know the lyric safe region.

When a large face can be placed slightly higher without compromising framing, prefer that position.

The visual subject and lyric region should be optimized jointly.

## 31.11 No-subject handling

If no reliable face/body is detected:

1. use predicted subject position;
2. if tracking is lost for the configured interval, blend toward center;
3. if there is long-term loss, use a stable center or composition-biased crop.

Do not abruptly jump to center on one failed frame.

---

# 32. VIDEO RENDERING

Render the cropped video to:

```text
1080x1920
```

Use FFmpeg for encoding.

OpenCV may provide frame-level crop coordinates, but final encoding should be handled by FFmpeg or a controlled video encoder.

Preferred encoder:

```text
h264_nvenc
```

when supported.

Fallback:

```text
libx264
```

Use `+faststart` for final MP4 packaging.

---

# 33. FINAL AUDIO ARCHITECTURE

The final audio is generated entirely from the local source-song segment.

```text
OUR SOURCE REEL SEGMENT
        │
        ▼
      DEMUCS
        │
        ├── vocals
        ├── drums
        ├── bass
        └── other
        │
        ▼
  8D spatial processing
        │
        ▼
   timeline-preserving
   final Reel audio
```

YouTube audio is not part of this branch.

---

# 34. 8D AUDIO ENGINE

The goal is a tasteful spatial effect rather than extreme motion.

## 34.1 Vocals

Vocals:

- stay center;
- remain intelligible;
- may receive a subtle stereo-width treatment;
- may receive controlled reverb;
- must not be aggressively panned.

A subtle Haas-style width layer may be used:

```text
15 ms
approximately -12 dB delayed side
```

This is an aesthetic effect, not a time-changing effect.

## 34.2 Bass

Bass:

- stays center;
- is primarily mono;
- avoids phase-heavy stereo motion;
- preserves low-end stability.

## 34.3 Drums

Drums:

- remain center-weighted;
- preserve kick/snare focus;
- permit modest stereo width in high-frequency/percussive components.

## 34.4 Other

The `other` stem receives the strongest spatial motion.

Use an LFO-based stereo pan.

Example:

```text
chorus:
    width = 80%
    frequency = 0.10 Hz

non-chorus:
    width = 40%
    frequency = 0.05 Hz
```

These are configurable starting points.

## 34.5 Phrase-aware modulation

The audio engine should receive hook structure from the selected candidate.

If the selected segment is repetition-heavy / chorus-like:

- slightly widen the `other` stem;
- increase controlled reverb;
- optionally increase motion depth.

If it is a verse-like section:

- use more restrained motion;
- preserve vocal clarity.

## 34.6 Timeline preservation

All default effects must preserve:

```text
source sample count
source timing
source duration
```

Any filter with latency must be compensated.

Any reverb tail must either:

- be rendered and then trimmed exactly; or
- be designed within the final time boundary.

Final audio duration must match final video duration.

---

# 35. LOUDNESS AND FINAL AUDIO VALIDATION

After mixing:

1. apply controlled summing;
2. prevent clipping;
3. use a limiter;
4. normalize toward configured target loudness;
5. validate true peak;
6. validate left/right balance;
7. verify no unexpected DC offset.

Starting targets:

```text
LUFS ≈ -14
True peak ≈ -1 dBTP
```

These are processing defaults, not platform guarantees.

The output must remain pleasant on:

- phone speakers;
- headphones;
- small Bluetooth speakers.

---

# 36. LYRIC SOURCE AND CANONICAL TIMELINE

The word-level JSON is the machine-readable lyric timing source.

The LRC provides lyric text and an independent textual/timing validation layer.

The renderer should not use MP3 embedded lyrics as its source of truth.

## 36.1 Word extraction

Read:

```text
phase2.alignment.lines[].words[]
```

or the equivalent word-level structure established by the input JSON.

For every word use:

```text
original text
start_ms
end_ms
score
source
```

## 36.2 Clip selection

Keep words whose timing intersects:

```text
reel_start_ms → reel_end_ms
```

Convert to local Reel time:

```text
local_start = word_start - reel_start
local_end   = word_end   - reel_start
```

Clamp to:

```text
0 → reel_duration
```

## 36.3 Lead-in behavior

If the Reel begins before the first lyric word:

- do not force a subtitle during the lead-in;
- allow the visual/music setup to breathe;
- start lyric rendering at the true lyric start.

---

# 37. TELUGU WORD-LEVEL KARAOKE LYRIC RENDERING

The final Reel uses true word-level karaoke presentation, but it is **not** a one-line-at-a-time subtitle system.

The lyric block remains visually present as a continuous phrase/context block while the currently sung word is highlighted according to the canonical word timestamps.

## 37.1 Canonical lyric source

Use the word-level JSON timeline as the timing source. Each word is expected to provide:

```text
original
normalized
start_ms
end_ms
score
source
```

The LRC is used as a wording/line-structure consistency reference, not as the fine timing authority.

## 37.2 Visual behavior

The renderer must show a readable Telugu lyric block such as:

```text
నీ చూపుల్లో నా లోకం
నీ మాటల్లో నా గానం
నువ్వే నా ప్రాణం
```

The block remains visible while the current word moves through the timing sequence.

Visual states:

```text
UPCOMING WORD
muted/light state

CURRENT WORD
strong highlight

COMPLETED WORD
normal or completed-highlight state
```

The current word may use a restrained scale, brightness, or color transition. Do not use large bouncing animation. The song/video remain the primary visual focus.

## 37.3 Continuous context

The renderer must not implement:

```text
line 1 appears
line 1 disappears
line 2 appears
line 2 disappears
```

Instead, maintain a small contextual lyric window. As the sung position advances, the phrase block can update or scroll smoothly when necessary. The currently sung word must remain obvious within the context.

## 37.4 Telugu typography

Primary recommended font:

```text
Noto Sans Telugu SemiBold/Bold
```

Secondary optional visual theme:

```text
Baloo Tammudu 2
```

The actual font file/version used for a render must be recorded in the Reel JSON. The renderer must not depend on an arbitrary machine-installed font.

Priorities:

1. Telugu glyph correctness;
2. readability at 1080x1920;
3. visual beauty;
4. weight consistency;
5. predictable line wrapping.

## 37.5 Position — centered in the Reel

The lyric block is centered in the Reel by default.

The design target is approximately the visual center of the 1080x1920 frame, not a bottom subtitle position. The exact center anchor must be computed from the final rendered block dimensions.

Default principle:

```text
frame center
      ↓
lyric block center
```

Do not use the original lower-middle `Y = 1600` concept as the default placement.

A small controlled displacement is allowed only when severe collision with a tracked subject makes the center placement visually unacceptable. The displacement should be the smallest necessary correction and must remain within the configured lyric composition region.

## 37.6 Subject-aware lyric placement

The crop engine and lyric renderer share composition information.

For each frame or subtitle event:

```text
tracked subject boxes
        +
lyric bounding box
        ↓
collision score
```

If there is no meaningful collision, keep the lyric block centered.

If there is a severe collision, the system may:

1. make a small vertical adjustment;
2. slightly adjust crop framing;
3. reduce the lyric block size within configured bounds;
4. use a wider subject composition when possible.

The system must not automatically push all lyrics to the bottom just because a face exists.

## 37.7 Line grouping

Group words using source lyric lines/phrase boundaries first, then wrap using actual rendered width.

Prefer up to two visual lines for normal presentation, while allowing a short third line only when explicitly configured and when the visual result remains clean.

Word wrapping must be based on measured rendered width, not character count. Telugu glyph clusters make character-count wrapping unreliable.

## 37.8 Word highlight timing

The current word becomes highlighted at `start_ms` and leaves the current state at `end_ms`.

The renderer may interpolate visual highlight properties over a small configured transition interval, but the underlying synchronization remains exactly tied to the canonical timestamps.

## 37.9 Karaoke visual palette

Use a high-contrast but restrained design. Suggested defaults:

```text
base text: near-white
current word: configurable accent color
completed words: full/soft white
outline/shadow: dark neutral
```

Color is a theme choice and must not reduce Telugu readability.

## 37.10 Lyric collision and safe-area validation

Before final rendering, calculate lyric bounding boxes and validate:

```text
bounding_box_left >= configured_safe_left
bounding_box_right <= configured_safe_right
bounding_box_top >= configured_safe_top
bounding_box_bottom <= configured_safe_bottom
```

The center placement remains the primary objective; safe-region and collision checks prevent visibly bad compositions.

## 37.11 Karaoke acceptance criteria

A final Reel must demonstrate:

- correct Telugu glyph rendering;
- centered lyric presentation;
- persistent contextual lyric block;
- current word clearly highlighted;
- correct word timing;
- clean wrapping;
- no clipping;
- no severe subject overlap;
- no lyric after Reel end.

# 38. FINAL ASSEMBLY

Inputs:

```text
video_9x16.mp4
reel_8d.wav
lyrics.ass
```

Output:

```text
stage_final/SongName_reel.mp4
```

The final MP4 should contain:

- H.264 video;
- AAC audio;
- burned-in lyrics;
- exact Reel duration;
- fast-start MP4 metadata.

Conceptually:

```text
Video
  +
our 8D audio
  +
ASS karaoke burn-in
  ↓
final Reel MP4
```

The Reel does not depend on the YouTube audio after matching.

---

# 39. CROSS-OUTPUT VALIDATION

Validation is mandatory before finalization.

## 39.1 MP4 validation

Check:

- file exists;
- decodes successfully;
- video stream exists;
- audio stream exists;
- width = 1080;
- height = 1920;
- aspect ratio = 9:16;
- duration finite;
- audio/video durations agree;
- no unexpected black bars if detectable;
- no zero-byte or corrupt output.

## 39.2 Audio validation

Check:

- sample rate;
- channel count;
- duration;
- loudness;
- true peak;
- no clipping;
- no NaN/infinite values;
- no unexpected timeline shift.

## 39.3 Lyric validation

Check:

- all lyric timestamps lie within Reel duration;
- word order is non-decreasing;
- no word has `end <= start`;
- expected word count vs rendered word count;
- subtitle bounding boxes remain in safe region;
- no subtitle extends beyond end of Reel.

## 39.4 Synchronization validation

Validate:

```text
source-song Reel segment duration
==
video segment duration
==
8D audio duration
==
subtitle timeline ceiling
```

within small configured tolerances.

## 39.5 Source integrity validation

Recalculate input hashes and verify:

```text
current input hash == pre-run input hash
```

If the source changed during processing:

```text
INPUT_CHANGED_DURING_RUN
```

and the result must not be accepted automatically.

---

# 40. FINAL OUTPUT PACKAGE

For each successful song:

```text
reels/generated/
├── SongName_reel.mp4
└── SongName_reel.json
```

Exactly these two user-facing files are required.

Temporary files remain under `temp/` and may be deleted according to policy.

---

# 41. PHASE 3 REEL JSON

The output JSON is the complete provenance record for the Reel.

It is a new file.

It never replaces the input song JSON.

Recommended top-level structure:

```json
{
  "schema_version": 1,
  "phase3_pipeline_version": "1.0.0",
  "status": "finished",
  "quality_status": "good",

  "source": {},
  "processing": {},
  "song": {},
  "hook_selection": {},
  "video_source": {},
  "video_match": {},
  "video_render": {},
  "audio_8d": {},
  "lyrics": {},
  "output": {},
  "validation": {},
  "errors": []
}
```

---

# 42. SOURCE JSON SECTION

Record:

```json
"source": {
  "basename": "SongName",
  "mp3_filename": "SongName.mp3",
  "lrc_filename": "SongName.lrc",
  "json_filename": "SongName.json",
  "mp3_sha256": "...",
  "lrc_sha256": "...",
  "json_sha256": "...",
  "input_duration_ms": 318000
}
```

Do not duplicate the entire source JSON by default.

Store the input hash so the Reel can be traced back exactly.

---

# 43. PROCESSING SECTION

Record:

```json
"processing": {
  "run_id": "uuid",
  "pipeline_version": "1.0.0",
  "config_hash": "...",
  "demucs": {
    "model": "htdemucs",
    "device": "cuda",
    "fallback_to_cpu": false
  },
  "hook_algorithm_version": "2.0.0",
  "video_match_algorithm_version": "2.0.0",
  "crop_algorithm_version": "2.0.0",
  "audio_8d_algorithm_version": "2.0.0",
  "lyric_renderer_version": "2.0.0"
}
```

---

# 44. HOOK JSON SECTION

Store the entire finalist list so the selection is inspectable.

```json
"hook_selection": {
  "mode": "automatic",
  "candidate_count_raw": 184,
  "candidate_count_after_filter": 72,
  "hook_family_count": 19,
  "finalist_count": 12,
  "selected": {
    "core_start_ms": 85000,
    "core_end_ms": 109500,
    "reel_start_ms": 82400,
    "reel_end_ms": 111300,
    "reel_duration_ms": 28900,
    "type": "FINAL_CHORUS",
    "core_score": 0.941,
    "context_score": 0.907,
    "final_score": 0.933
  },
  "candidates": []
}
```

Each finalist should contain its feature breakdown.

---

# 45. VIDEO SOURCE JSON SECTION

Record:

```json
"video_source": {
  "youtube_video_id": "...",
  "youtube_url": "...",
  "title": "...",
  "audio_sha256": "...",
  "audio_duration_ms": 298000
}
```

---

# 46. VIDEO MATCH JSON SECTION

Record:

```json
"video_match": {
  "query_start_ms": 82400,
  "query_end_ms": 111300,
  "video_match_start_ms": 102178,
  "video_match_end_ms": 131078,
  "confidence": 0.94,
  "coarse_similarity": 0.93,
  "fine_similarity": 0.96,
  "anchor_consistency_ms": 18,
  "max_anchor_residual_ms": 31,
  "tempo_adjustment_percent": 0.0,
  "accepted": true
}
```

---

# 47. VIDEO RENDER JSON SECTION

Record:

```json
"video_render": {
  "resolution": "1080x1920",
  "source_segment_start_ms": 102178,
  "source_segment_end_ms": 131078,
  "guard_before_ms": 1500,
  "guard_after_ms": 1500,
  "crop_method": "face_pose_temporal",
  "tracker": "mediapipe",
  "subject_switches": 0,
  "tracking_confidence_mean": 0.91,
  "tracking_confidence_p10": 0.77,
  "fallback_duration_ms": 0
}
```

---

# 48. AUDIO JSON SECTION

Record:

```json
"audio_8d": {
  "source": "local_song",
  "format": "8d_spatial_4stem",
  "duration_ms": 28900,
  "target_lufs": -14.0,
  "true_peak_db": -1.0,
  "vocal_centered": true,
  "bass_mono_centered": true,
  "other_lfo_width": 0.8,
  "other_lfo_frequency_hz": 0.1,
  "timeline_preserved": true
}
```

No fingerprint-bypass field exists in the final schema.

---

# 49. LYRICS JSON SECTION

Record:

```json
"lyrics": {
  "enabled": true,
  "word_count_source": 92,
  "word_count_rendered": 92,
  "first_word_local_ms": 2610,
  "last_word_local_ms": 28140,
  "safe_zone_validated": true,
  "renderer": "ass_word_karaoke"
}
```

---

# 50. OUTPUT JSON SECTION

Record:

```json
"output": {
  "reel_mp4": "reels/generated/SongName_reel.mp4",
  "reel_json": "reels/generated/SongName_reel.json",
  "reel_mp4_sha256": "...",
  "reel_json_sha256": "...",
  "file_size_bytes": 12345678,
  "duration_ms": 28900
}
```

---

# 51. VALIDATION JSON SECTION

Record individual validation gates:

```json
"validation": {
  "input_integrity": true,
  "hook_selection": true,
  "video_match": true,
  "video_dimensions": true,
  "video_duration": true,
  "audio_duration": true,
  "audio_loudness": true,
  "lyrics_timing": true,
  "lyrics_safe_zone": true,
  "final_mp4_decode": true,
  "cross_output_consistency": true,
  "overall": true
}
```

---

# 52. DATABASE DESIGN

The SQLite database is an internal processing-state database only.

It does not replace the output JSON.

It exists to make the batch resumable and idempotent.

## 52.1 `jobs`

```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    song_basename TEXT NOT NULL UNIQUE,
    mp3_sha256 TEXT NOT NULL,
    lrc_sha256 TEXT NOT NULL,
    json_sha256 TEXT NOT NULL,
    processing_identity TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    stage TEXT,
    quality_status TEXT,
    hook_selection_mode TEXT NOT NULL DEFAULT 'automatic',
    manual_hook_start_ms INTEGER,
    manual_hook_end_ms INTEGER,
    error_code TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
```

## 52.2 `hook_candidates`

```sql
CREATE TABLE hook_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    family_id INTEGER,
    rank INTEGER,
    core_start_ms INTEGER NOT NULL,
    core_end_ms INTEGER NOT NULL,
    reel_start_ms INTEGER,
    reel_end_ms INTEGER,
    core_score REAL,
    context_score REAL,
    final_score REAL,
    type TEXT,
    feature_json TEXT NOT NULL,
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);
```

## 52.3 `video_matches`

```sql
CREATE TABLE video_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    youtube_video_id TEXT NOT NULL,
    query_start_ms INTEGER NOT NULL,
    query_end_ms INTEGER NOT NULL,
    match_start_ms INTEGER,
    match_end_ms INTEGER,
    confidence REAL,
    coarse_similarity REAL,
    fine_similarity REAL,
    anchor_residual_ms REAL,
    accepted INTEGER NOT NULL DEFAULT 0,
    result_json TEXT,
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);
```

## 52.4 `artifacts`

```sql
CREATE TABLE artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    artifact_type TEXT NOT NULL,
    path TEXT NOT NULL,
    sha256 TEXT,
    size_bytes INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);
```

---

# 53. PIPELINE STATE MACHINE

Recommended states:

```text
pending
  ↓
input_verified
  ↓
stems_ready
  ↓
song_analysis_ready
  ↓
hook_candidates_ready
  ↓
hook_finalists_ready
  ↓
hook_selected
  ↓
query_audio_ready
  ↓
youtube_audio_ready
  ↓
video_match_ready
  ↓
video_segment_ready
  ↓
video_rendered
  ↓
audio_rendered
  ↓
lyrics_rendered
  ↓
assembled
  ↓
validated
  ↓
finalized
```

Failure state:

```text
failed
```

Review state:

```text
needs_review
```

The database must remember the last successful stage so the pipeline can resume without repeating expensive work unnecessarily.

---

# 54. RESUMABILITY RULES

Examples:

### Demucs succeeded, hook scoring failed

Resume from hook scoring.

### Hook selected, YouTube audio download failed

Resume from YouTube audio download.

### Video match succeeded, rendering failed

Resume from video rendering.

### Final MP4 exists, JSON write failed

Validate MP4, rebuild JSON, finalize package.

### Final package exists, DB state is incomplete

Use reconciliation to repair database state.

---

# 55. ATOMIC FINALIZATION

All final outputs should first be written to:

```text
stage_final/
```

Then:

1. validate Reel MP4;
2. validate Reel JSON;
3. calculate final hashes;
4. validate cross-file consistency;
5. verify input hashes did not change;
6. atomically promote outputs into:

```text
reels/generated/
```

Only after promotion succeeds should DB status become `finalized`.

---

# 56. IDEMPOTENCY

A completed result may be reused when:

```text
input hashes match
processing identity matches
output hashes validate
```

Otherwise reprocessing is permitted.

A `--force` flag can invalidate an otherwise valid result.

---

# 57. ERROR CODES

Recommended stable error codes:

```text
INPUT_MP3_MISSING
INPUT_LRC_MISSING
INPUT_JSON_MISSING
INPUT_JSON_INVALID
INPUT_BASENAME_COLLISION
INPUT_PACKAGE_INCOMPLETE
INPUT_CHANGED_DURING_RUN
WORD_TIMELINE_MISSING
YOUTUBE_VIDEO_ID_MISSING
YOUTUBE_VIDEO_UNAVAILABLE
DEMUCS_FAILED
DEMUCS_OOM
HOOK_NO_CANDIDATES
HOOK_INSUFFICIENT_FINALISTS
HOOK_SELECTION_FAILED
YOUTUBE_AUDIO_DOWNLOAD_FAILED
VIDEO_MATCH_LOW_CONFIDENCE
VIDEO_MATCH_INCONSISTENT
VIDEO_SECTION_DOWNLOAD_FAILED
VIDEO_TRIM_FAILED
TRACKING_FAILED
VIDEO_RENDER_FAILED
AUDIO_RENDER_FAILED
LYRIC_RENDER_FAILED
ASSEMBLY_FAILED
OUTPUT_VALIDATION_FAILED
FINALIZATION_FAILED
STATE_RECONCILIATION_REQUIRED
```

---

# 58. ERROR HANDLING AND RECOVERY

## 58.1 Demucs OOM

Retry:

1. clear CUDA cache;
2. retry if configured;
3. fallback CPU;
4. record actual device used.

## 58.2 YouTube audio failure

Retry with configured attempts.

If it remains unavailable:

```text
YOUTUBE_AUDIO_DOWNLOAD_FAILED
```

Do not proceed with an unverified video timeline.

## 58.3 Match failure

Do not guess.

Mark:

```text
needs_review
```

and preserve matching diagnostics.

## 58.4 Tracking loss

Use prediction/smoothing before falling back to center.

## 58.5 FFmpeg failure

Preserve command, stderr, and inputs in temp logs.

## 58.6 Finalization failure

Keep staged outputs for recovery.

Never declare `finalized` until both output files validate.

---

# 59. LOGGING

Per-song logs should record:

- run ID;
- stage transitions;
- input hashes;
- model/device choices;
- Demucs duration;
- candidate counts;
- selected hook scores;
- video match candidates;
- chosen video match;
- tracking statistics;
- audio loudness statistics;
- lyric render statistics;
- final validation;
- errors and retries.

Do not log secrets because this project has no external publishing credentials.

---

# 60. ABSOLUTE DO-NOT-DO LIST

1. NEVER modify `songs/final/`.
2. NEVER require Phase 1 Python code.
3. NEVER require Phase 2 Python code.
4. NEVER access upstream project databases.
5. NEVER treat YouTube audio as final Reel audio.
6. NEVER download the complete high-resolution video before locating the matching segment.
7. NEVER choose the Reel solely as a fixed 30-second window.
8. NEVER choose a hook solely from raw loudness.
9. NEVER ignore lyric repetition or phrase recurrence.
10. NEVER output 10–15 finalists that are merely one-second shifts of the same hook.
11. NEVER replace automatic hook analysis with a manual prompt in the normal run.
12. NEVER treat the manual hook timeline as a suggestion; when manual mode is selected it is authoritative.
13. NEVER render Telugu lyrics as a bottom-anchored subtitle block by default.
14. NEVER switch between tracked people frame-by-frame without temporal identity logic.
15. NEVER silently use an arbitrary `0 ms` video offset after a failed match.
16. NEVER accept a low-confidence video match as valid.
17. NEVER stretch or distort the source video to achieve 9:16.
18. NEVER allow the crop subject to jump between unrelated faces every frame.
19. NEVER pan vocals aggressively.
20. NEVER pan bass aggressively.
21. NEVER change audio speed merely to alter platform fingerprinting.
22. NEVER change audio timing without synchronizing video and lyrics to the same transformation.
23. NEVER place lyrics in the extreme bottom edge of the composition.
24. NEVER overwrite a valid final Reel during an unfinished rerun.
25. NEVER mark a job `finalized` before output validation.
26. NEVER call any Instagram publishing API.

---

# 61. ABSOLUTE MUST-DO LIST

1. MUST treat `songs/final/` as the complete runtime input contract.
2. MUST calculate input hashes before processing.
3. MUST run Demucs on the full source song for fresh processing.
4. MUST use Demucs stems as explicit evidence in hook selection.
5. MUST analyse the entire song before selecting the final hook.
6. MUST analyse lyric repetition and recurring phrases.
7. MUST generate multiple hook candidates across the song.
8. MUST reduce candidates into approximately 10–15 genuinely distinct finalists.
9. MUST allow variable hook/core duration.
10. MUST consider a natural 2–3 second lead-in when it improves the hook.
11. MUST allow shorter or longer lead-ins when acoustic context demands it.
12. MUST consider a natural ending/tail.
13. MUST choose a final content-driven Reel timeline.
14. MUST support `python main.py --manualhook SongName`.
15. MUST allow manual start/end timestamps to bypass only hook selection, not downstream automation.
16. MUST record whether hook selection was automatic or manual in Reel JSON.
17. MUST use multi-person identity tracking for smart crop.
18. MUST center Telugu karaoke in the Reel by default.
19. MUST highlight the currently sung word inside a persistent contextual lyric block.
20. MUST extract the selected query audio from the original source song.
21. MUST download the complete YouTube video audio only.
22. MUST search the complete YouTube audio for the selected source segment.
23. MUST verify the match with multiple evidence channels and anchor consistency.
24. MUST reject low-confidence or inconsistent matches.
25. MUST download only the needed video section plus a small guard band.
26. MUST exact-trim the video to the final selected timeline.
27. MUST use stateful smart crop tracking.
28. MUST keep final video at 1080×1920.
29. MUST generate final audio only from the local source song.
30. MUST preserve final audio timeline relative to video and lyrics.
31. MUST render word-level karaoke using the input word timing.
32. MUST validate lyric center placement, collision, and configured composition bounds.
33. MUST validate audio/video duration consistency.
34. MUST validate final MP4 decode.
35. MUST save a separate Reel JSON beside the MP4.
36. MUST include hashes and provenance in the Reel JSON.
37. MUST leave input files unchanged.
38. MUST support resume/recovery through SQLite state.
39. MUST stop after final Reel generation; Instagram upload is manual.

# 62. CLI DESIGN

Recommended commands:

```bash
python main.py --doctor
python main.py --scan
python main.py --process-all
python main.py --process "SongName"
python main.py --resume
python main.py --force "SongName"
python main.py --validate "SongName"
python main.py --inspect-hooks "SongName"
python main.py --inspect-match "SongName"
python main.py --repair-state
python main.py --clean-temp
```

## 62.1 Manual hook override

Interactive:

```bash
python main.py --manualhook "SongName"
```

Non-interactive:

```bash
python main.py --manualhook "SongName" --start 00:02:14.200 --end 00:02:34.800
```

`--manualhook` must be mutually compatible only with the downstream processing flow. It must not invoke automatic hook selection. If no explicit start/end are supplied, prompt for them.

## 62.2 Inspect hook candidates

```bash
python main.py --inspect-hooks "SongName"
```

This displays the automatic candidate families and 10–15 final candidates without rerendering the Reel.

## 62.3 Validate a finished Reel

```bash
python main.py --validate "SongName"
```

Validation is read-only against the finalized output and source package.

# 63. TESTING STRATEGY

The project must have unit, integration, fixture, and end-to-end tests.

## 63.1 Unit tests

Test:

- basename matching;
- JSON validation;
- LRC parsing;
- word timeline extraction;
- repetition detection;
- phrase clustering;
- candidate generation;
- candidate family clustering;
- score normalization;
- hook scoring;
- lead-in scoring;
- tail scoring;
- match feature generation;
- crop coordinate clamping;
- tracking smoothing;
- subtitle timing conversion;
- JSON generation.

## 63.2 Integration tests

Test:

- Demucs invocation;
- FFmpeg extraction;
- yt-dlp audio-only download;
- section download;
- audio matching;
- MediaPipe tracking;
- final FFmpeg assembly.

## 63.3 Failure tests

Simulate:

- missing file;
- invalid JSON;
- missing word timing;
- missing YouTube ID;
- Demucs OOM;
- yt-dlp failure;
- low-confidence audio match;
- inconsistent anchor matches;
- face detection loss;
- FFmpeg failure;
- final JSON write failure;
- output promotion failure.

---

# 64. HOOK ACCEPTANCE TESTS

A test song should verify that:

1. the selector analyses the full duration;
2. more than 30-second windows are possible;
3. repeated chorus phrases receive higher repetition scores;
4. strong vocal sections are rewarded;
5. instrumental-only sections do not automatically win;
6. build→payoff sections can beat flat energy sections;
7. 10–15 distinct finalists are produced when enough valid candidates exist;
8. shifted copies of the same timeline are clustered;
9. final selected duration is content-driven;
10. a 2–3 second lead-in is chosen when it improves the context;
11. an immediate start is allowed when that is better;
12. the final ending avoids unnecessary lyric/musical truncation.

---

# 65. VIDEO MATCH ACCEPTANCE TESTS

A test video/audio pair should verify:

1. complete YouTube audio is downloaded;
2. source query is generated from the local song;
3. multiple candidate matches are generated;
4. the correct occurrence is selected;
5. anchors agree on one continuous region;
6. low-confidence matches are rejected;
7. exact video timestamps correspond to the selected source segment;
8. only the required video section is downloaded.

---

# 66. SMART-CROP ACCEPTANCE TESTS

Verify:

- face stays visible;
- face does not jitter;
- multiple people do not cause unstable switching;
- temporary detection loss does not cause sudden crop jumps;
- subject remains in upper-middle composition;
- lyrics do not overlap important face area unnecessarily;
- boundaries are clamped;
- output is exactly 1080×1920;
- no black bars;
- no distortion.

---

# 67. AUDIO ACCEPTANCE TESTS

Verify:

- final audio is derived from the local song;
- YouTube audio is absent from final audio processing;
- vocals remain centered;
- bass remains centered/mono;
- spatial movement is primarily on `other` and controlled drum content;
- 8D effect is audible but not extreme;
- timeline remains unchanged;
- loudness target is reached within tolerance;
- no clipping;
- no unexpected silence or drift.

---

# 68. LYRIC ACCEPTANCE TESTS

Verify:

- every rendered word uses the expected source timing;
- lyric starts when the selected source lyric starts;
- words are highlighted in the correct order;
- two-line wrapping is readable;
- Telugu glyphs render correctly;
- subtitles remain in safe region;
- no word persists beyond its timing interval;
- no subtitle appears after Reel end.

---

# 69. FINAL PACKAGE ACCEPTANCE TEST

The final package is accepted only when:

```text
SongName_reel.mp4 exists
SongName_reel.json exists
MP4 decodes
JSON parses
MP4 is 1080×1920
MP4 contains video
MP4 contains audio
Audio duration ≈ video duration
Lyrics duration <= Reel duration
Input hashes unchanged
Output hashes recorded
Validation.status = good
DB status = finalized
```

---

# 70. MANUAL REVIEW PACKAGE

For a batch-quality workflow, the system should make manual review easy.

A generated Reel JSON should contain enough data for an operator to understand:

- why this hook was selected;
- what other 10–15 candidates existed;
- what the selected YouTube segment was;
- why the audio match was accepted;
- how the subject was tracked;
- what audio processing was applied;
- what lyric range was rendered.

A future inspection tool may present:

```text
selected hook
candidate ranking
match confidence
video timestamps
output path
validation state
```

without rerunning the pipeline.

---

# 71. PERFORMANCE STRATEGY

## 71.1 GPU use

GPU:

```text
Demucs
```

Prefer CPU for:

```text
MediaPipe tracking
feature extraction where practical
JSON processing
subtitle generation
```

## 71.2 Cache reusable analysis

Within one processing identity, cache:

- Demucs stems;
- acoustic features;
- lyric analysis;
- hook candidate list;
- YouTube audio;
- match candidates.

Do not redo expensive stages when downstream stages fail.

## 71.3 Temporary storage

Large WAV files can be deleted as soon as their dependent stage has completed and been checkpointed.

Example:

```text
hook selection complete
→ keep analysis summaries
→ stem files can remain only if needed for 8D
```

Since 8D also uses the selected segment stems, retain the four source stems until audio finalization, then delete unless configured otherwise.

---

# 72. DETERMINISM AND REPRODUCIBILITY

Whenever possible:

- pin model versions;
- pin package versions;
- record config hash;
- record algorithm versions;
- use deterministic feature calculations;
- record random seeds when any randomized component exists.

Two runs with identical input and processing identity should normally produce the same hook ranking and same final timeline unless a nondeterministic external source changes.

---

# 73. OUTPUT NAMING

For source basename:

```text
001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra
```

output:

```text
001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra_reel.mp4
001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra_reel.json
```

Do not alter the input filename.

---

# 74. FUTURE EXTENSION POINTS

The architecture should permit later additions without changing the input/output contract.

Possible future additions:

- multiple Reel candidates per song;
- visual scene-change scoring;
- OCR-aware visual lyric matching;
- explicit person identity models;
- better audio fingerprinting;
- learned hook-quality models;
- alternate subtitle styles;
- manual candidate approval UI;
- automatic thumbnail selection.

These are optional future features and are not prerequisites for the first production implementation.

---

# 75. FINAL ARCHITECTURAL SUMMARY

The final Phase 3 system is best understood as seven cooperating engines.

## Engine 1 — Song Intelligence

```text
MP3 + LRC + JSON
       ↓
Demucs + acoustic analysis + lyric analysis
       ↓
full-song structure and repetition map
```

## Engine 2 — Hook Intelligence

```text
full-song map
       ↓
hook-core candidates
       ↓
scoring
       ↓
family clustering
       ↓
10–15 distinct finalists
       ↓
lead-in + tail optimization
       ↓
final Reel timeline
```

## Engine 3 — Video Matching

```text
selected source-song Reel segment
       ↓
full YouTube video audio
       ↓
coarse whole-song search
       ↓
fine local matching
       ↓
multi-anchor verification
       ↓
exact matching video timestamps
```

## Engine 4 — Visual Reframing

```text
matching video section
       ↓
face/body subject tracking
       ↓
stateful crop path
       ↓
lyric-aware composition
       ↓
1080×1920
```

## Engine 5 — Audio + Lyric Composition

```text
our source Reel segment
       ↓
Demucs stems
       ↓
8D spatial processing
       ↓
word-level karaoke
       ↓
final audio/video/subtitle synchronization
```

## Engine 6 — Karaoke Composition

```text
word-level timing
       ↓
centered Telugu lyric block
       ↓
current-word highlight
       ↓
subject-aware collision control
```

## Engine 7 — Provenance + Recovery

```text
input hashes
+ processing identity
+ candidate rankings
+ video match evidence
+ render statistics
+ validation results
       ↓
SongName_reel.json
```

---

# 76. FINAL END-TO-END REFERENCE FLOW

```text
songs/final/Song.mp3
songs/final/Song.lrc
songs/final/Song.json
             │
             ▼
      PACKAGE VALIDATION
             │
             ▼
       INPUT HASHING
             │
             ▼
      FULL-SONG DEMUCS
             │
      ┌──────┴────────┐
      ▼               ▼
ACOUSTIC MAP      LYRIC MAP
      │               │
      └──────┬────────┘
             ▼
      SONG STRUCTURE MAP
             │
             ▼
    HOOK CORE GENERATION
             │
             ├── repeated phrases
             ├── repeated lines
             ├── chorus/refrain
             ├── vocal peaks
             ├── musical peaks
             └── build/payoff
             │
             ▼
       HOOK SCORING
             │
             ▼
     HOOK FAMILY CLUSTERING
             │
             ▼
       10–15 FINALISTS
             │
             ▼
     CONTEXT EXPANSION
       ├── lead-in
       └── tail
             │
             ▼
     FINAL REEL TIMELINE
             │
             ▼
      SOURCE AUDIO QUERY
             │
             ▼
   YOUTUBE AUDIO-ONLY DOWNLOAD
             │
             ▼
  WHOLE-VIDEO AUDIO MATCHING
       ├── coarse search
       ├── fine alignment
       ├── multi-anchor validation
       └── confidence scoring
             │
             ▼
    VIDEO MATCH TIMESTAMPS
             │
             ▼
     SECTION DOWNLOAD + GUARD
             │
             ▼
       EXACT VIDEO TRIM
             │
      ┌──────┴─────────┐
      ▼                ▼
 SMART 9:16 CROP     8D AUDIO
      │                │
      │          OUR SOURCE AUDIO
      │                │
      └──────┬─────────┘
             ▼
       WORD KARAOKE
             │
             ▼
     FINAL MP4 ASSEMBLY
             │
             ▼
       FULL VALIDATION
             │
             ▼
     OUTPUT MP4 + JSON
             │
             ▼
       MANUAL UPLOAD
```

---

# 77. FINAL DESIGN PRINCIPLES

The implementation must follow these principles throughout:

### Principle 1 — Content before duration

The Reel is selected around the best musical/lyrical moment, not around a fixed 30-second container.

### Principle 2 — Hook core before context

Find what is genuinely memorable first. Then add only the context that makes it feel better.

### Principle 3 — Lyrics matter

A hook is not merely an energy peak. Repetition, phrase memorability, refrain recurrence, lyrical completeness, and timing quality are first-class signals.

### Principle 4 — Demucs is analytical evidence

Vocals, drums, bass, and other stems are used to understand what makes a section strong, not merely to generate the eventual 8D effect.

### Principle 5 — Many candidates before one decision

Generate many possibilities, reduce them into 10–15 genuinely distinct finalists, inspect their evidence, then choose the final timeline.

### Principle 6 — Source audio is sacred

The local song is the canonical final audio. YouTube audio exists only to locate the matching visual timeline.

### Principle 7 — Match the selected segment, not the whole song offset

The system finds the selected Reel segment inside the complete YouTube audio rather than assuming one global offset is always correct.

### Principle 8 — Visuals should follow the subject

Smart crop is a temporal tracking problem, not a one-frame crop problem.

### Principle 9 — Effects must preserve sync

The 8D engine is an audio presentation layer. It must not break audio/video/lyrics alignment.

### Principle 10 — Preserve provenance

Every decision must be reconstructable from the Reel JSON and processing database.

### Principle 11 — Fail safely

Low-confidence video matching, corrupt input, unstable tracking, and invalid output must become explicit failure/review states rather than guessed results.

### Principle 12 — Phase 3 ends at a validated Reel

The user performs Instagram publishing manually. Phase 3 has no publishing API dependency.

---

# 78. FINAL DEFINITION OF DONE

Phase 3 is complete for a song when:

```text
1. Input package verified.
2. Input hashes recorded.
3. Demucs separation completed.
4. Full-song acoustic analysis completed.
5. Full-song lyric/repetition analysis completed.
6. Song structure/recurrence map completed.
7. Hook candidates generated.
8. Candidate scoring completed.
9. Candidate families deduplicated.
10. Approximately 10–15 distinct finalists generated.
11. Final hook core selected.
12. Natural lead-in evaluated.
13. Natural tail evaluated.
14. Final Reel timeline selected.
15. Clean source-song query extracted.
16. Complete YouTube video audio downloaded.
17. Query located within complete video audio.
18. Match confidence verified.
19. Exact matching video section downloaded.
20. Exact video trim produced.
21. Subject tracking completed.
22. 9:16 crop rendered at 1080×1920.
23. Source-song stems processed for 8D.
24. Final audio loudness and phase validated.
25. Word-level karaoke rendered.
26. Final MP4 assembled.
27. Cross-file synchronization validated.
28. Input integrity rechecked.
29. Final MP4 hashed.
30. Final Reel JSON written and validated.
31. Final MP4 + JSON atomically promoted.
32. SQLite state committed as finalized.
33. Temporary artifacts cleaned according to policy.
```

At that point the final user-facing result is:

```text
reels/generated/SongName_reel.mp4
reels/generated/SongName_reel.json
```

and the original files under `songs/final/` remain unchanged.
