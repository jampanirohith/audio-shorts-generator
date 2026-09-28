# UNIFIED YOUTUBE MUSIC PLAYLIST → WORD-LEVEL TELUGU LYRICS → AUTOMATED REEL
## Ultra-Detailed / Ultra-Complete Integrated Production Project Plan

**Document status:** Proposed unified authoritative architecture derived from the three supplied phase specifications and the integration decisions discussed afterward.

**Integration scope:** Phase 1 + Phase 2 + Phase 3 as one operational project, with one playlist-to-song-to-word-timeline-to-Reel lifecycle.

**Primary user workflow:**

```text
YouTube Music Playlist
        ↓
Song acquisition + enrichment
        ↓
Canonical retained song package
        ↓
Synchronized lyric validation
        ↓
Word-level Telugu alignment
        ↓
Canonical word timeline
        ↓
Full-song musical/lyrical intelligence
        ↓
Hook discovery + finalist generation
        ↓
Final Reel segment selection
        ↓
YouTube visual-timeline matching
        ↓
Exact video-section acquisition
        ↓
Stateful 9:16 reframing
        ↓
Timeline-preserving spatial/8D audio
        ↓
Word-level Telugu karaoke
        ↓
Final MP4 + provenance JSON
        ↓
Validation + finalization
        ↓
Next song
```

---

# 0. PURPOSE OF THIS DOCUMENT

This document turns the three previously separate project specifications into one large production system without discarding the original responsibilities, constraints, provenance model, validation philosophy, recovery behavior, or source-file safety rules.

The three source specifications remain preserved verbatim at the end of this document so that no original requirement is lost. The first part of this document is the integrated architecture: it explains how the three systems become one pipeline, where the original boundaries remain useful, which conflicts need explicit resolution, which artifacts become shared, which data becomes canonical, and what the final implementation should build.

The integrated project is intentionally **not** a literal codebase merge. It is a unified application with one orchestrator and shared data contracts, while retaining modular engines for playlist ingestion, enrichment, word-level alignment, song intelligence, hook selection, video matching, crop/rendering, audio processing, karaoke, validation, provenance, and recovery.

---

# 1. SOURCE SPECIFICATIONS INCORPORATED

The integrated plan is grounded in these three supplied documents:

1. **Phase 1 — YouTube Music Playlist Downloader & Enricher**
   - Playlist ingestion and permanent serial identity.
   - YT Music source acquisition.
   - Metadata normalization.
   - Optional Spotify enrichment.
   - ISRC-only duplicate identity and transactional duplicate replacement.
   - YouTube music-video discovery.
   - LRCLIB synchronized lyric retrieval.
   - Artwork selection.
   - MP3 metadata embedding.
   - Detailed sidecar JSON provenance.
   - SQLite persistence, validation, hashing, recovery, CLI, logging, Windows workflow, tests, migration, and release requirements.

2. **Phase 2 — Standalone Word-Level Telugu Lyric Syncing**
   - Exact-basename MP3/LRC/JSON package contract.
   - Full preservation of source audio, metadata, and JSON.
   - Demucs vocal isolation.
   - VAD/energy evidence.
   - Reversible Telugu normalization.
   - LRC anchor model.
   - Anchor-aware chunking with overlaps.
   - Meta MMS Telugu adapter.
   - CTC reference-driven forced alignment.
   - Token-to-word span construction.
   - Chunk retry and dual-audio fallback strategy.
   - Overlap deduplication and global merge.
   - Anchor drift and instrumental-section analysis.
   - Canonical word/line records.
   - Word-level LRC export.
   - Surgical SYLT embedding while preserving pre-existing ID3 frames.
   - Cumulative JSON namespace, quality metrics, validation, state machine, database, recovery, tests, acceptance gates, deterministic processing, and release criteria.

3. **Phase 3 — Automated Short-Form Reel Generation**
   - Standalone local package input contract.
   - Full-song Demucs and acoustic/lyrical analysis.
   - Repetition and structure discovery.
   - Hook-core generation and scoring.
   - Hook-family clustering.
   - 10–15 genuinely distinct finalists.
   - Lead-in and tail context expansion.
   - Manual hook override mode.
   - Local source-song audio as canonical Reel audio.
   - YouTube audio-only acquisition for temporal localization.
   - Multi-stage audio matching and multi-anchor verification.
   - Exact video-section acquisition.
   - Stateful subject tracking and smart 9:16 crop.
   - Timeline-preserving 8D/spatial audio.
   - Word-level centered Telugu karaoke.
   - Final assembly.
   - Cross-output validation.
   - Reel JSON provenance.
   - Resumability, idempotency, logging, error codes, testing, performance, determinism, and final definition of done.

---

# 2. NORMATIVE STATUS OF REQUIREMENTS

Each requirement in this unified document belongs to one of three categories:

### 2.1 Inherited — normative source requirement

The behavior is directly inherited from one or more of the three phase documents and should be retained unless explicitly superseded by a section in this unified plan.

### 2.2 Integration decision — new unified rule

The behavior did not exist as one rule across all three standalone projects and is introduced to make them operate as one system. These rules are identified explicitly so they are not mistaken for requirements stated verbatim in an individual phase document.

### 2.3 Implementation recommendation — engineering refinement

The requirement is a design recommendation that improves integration, operational reliability, or performance without changing the intent of the source specifications.

When there is a genuine conflict, this unified plan resolves it explicitly rather than silently changing one phase.

---

# 3. PRIMARY INTEGRATION DECISIONS

## 3.1 One application, modular engines

The system is one application and one operational workflow, but the internal modules remain separated by responsibility.

```text
main.py
   ↓
src/pipeline.py
   ├── playlist ingestion
   ├── source acquisition
   ├── enrichment
   ├── duplicate handling
   ├── word-level alignment
   ├── song intelligence
   ├── hook selection
   ├── video matching
   ├── rendering
   ├── validation
   ├── finalization
   └── recovery
```

This avoids tight coupling between formerly standalone code while eliminating the need for three independent runners.

## 3.2 One master database

**Integration decision:** use one operational SQLite database, `db/project.db`, rather than three independent runtime databases.

The unified database preserves the logical data models of Phase 1, Phase 2, and Phase 3 but connects them through shared `song_id` / retained-song identity.

The original Phase 1 concepts of playlist occurrence identity and retained-song identity remain separate.

The unified database therefore answers both:

```text
Which playlist occurrence was this?
```

and:

```text
What retained song package and Reel artifacts belong to it?
```

Logical entities include:

```text
playlist_entries
songs
processing_runs
processing_events
alignment_chunks
word_alignments
instrumental_sections
hook_candidates
hook_families
video_matches
artifacts
```

## 3.3 One song worker at a time

**Integration decision:** the default production workflow processes one playlist occurrence / retained song completely through the expensive stages before moving to the next item.

```text
Song 001
  → acquire
  → enrich
  → word-sync
  → analyze
  → hook
  → video match
  → render
  → validate
  → finalize
  ↓
Song 002
```

Parallelism can later be introduced for lightweight network or CPU stages, but the default design preserves GPU/RAM headroom and simplifies recovery, deterministic state transitions, and debugging.

## 3.4 One shared Demucs result per processing identity

The standalone specifications each describe Demucs inside their own stage. In the unified project, **Demucs runs once per song processing identity and the resulting stems are shared**.

```text
full source song
      ↓
    Demucs
      ↓
 ┌────┼────────┬────────┐
 ▼    ▼        ▼        ▼
vocal drums    bass    other
 │      │        │        │
 ├──────┴────────┴────────┤
 │                        │
 ▼                        ▼
Phase 2 alignment     Phase 3 intelligence/8D
```

This is an integration optimization, not a change in the algorithms described by the source specifications.

## 3.5 Phase boundary by file contract

The cleanest unified boundary is:

```text
Phase 1 retained package
        ↓
Phase 2 word-level package
        ↓
Phase 3 Reel generator
```

The final word-level song package is therefore the **canonical Phase 3 input**.

## 3.6 No synchronized LRC means no Reel

Phase 1 may legitimately retain a song with no synchronized lyrics. Phase 3 requires a word-level timeline.

Therefore:

```text
No synchronized LRCLIB lyric
        ↓
retain song
        ↓
Reel status = BLOCKED_NO_SYNC_LYRICS
        ↓
continue playlist processing
```

No fabricated timing is introduced merely to unblock the Reel stage.

## 3.7 Missing selected YouTube music video means no Reel

Phase 1 can complete the song without finding a usable music video. Phase 3 requires a selected video ID.

Therefore:

```text
No selected YouTube video
        ↓
retain song
        ↓
Reel status = BLOCKED_NO_YOUTUBE_VIDEO
        ↓
continue playlist processing
```

## 3.8 Phase 3 never modifies the word-level song package

```text
songs/final/Song.mp3
songs/final/Song.lrc
songs/final/Song.json
```

are treated as immutable Phase 3 inputs.

Phase 3 produces only:

```text
reels/generated/Song_reel.mp4
reels/generated/Song_reel.json
```

## 3.9 One canonical word timeline

All downstream lyric behavior must use one canonical word-level timing model.

```text
CTC alignment
     ↓
CANONICAL WORD TIMELINE
     ├── final word-level LRC
     ├── Phase 2 SYLT
     ├── Phase 2 JSON
     ├── Phase 3 hook timing
     └── Phase 3 karaoke
```

No downstream stage may independently regenerate word timings.

## 3.10 Source audio is canonical final Reel audio

The final Reel audio always comes from the local song package. YouTube audio is a temporary localization reference only.

## 3.11 No global-offset-only synchronization

The video matcher must find the selected source-song segment inside the complete YouTube video audio.

Primary result:

```text
video_match_start_ms
video_match_end_ms
match_confidence
```

A global offset may be calculated for diagnostics, but it is not the core synchronization model.

## 3.12 Hook duration remains content-driven

The system does not impose a fixed 30-second Reel. Practical search bounds remain variable, with a preferred target around 25–35 seconds when content quality is similar.

## 3.13 No fingerprint-evasion subsystem

No pitch/speed modification is added to bypass copyright systems. Creative spatial/audio processing is allowed only as part of the intended Reel sound design and must preserve timeline synchronization.

## 3.14 No Instagram API

The unified project stops at a validated Reel package. Instagram publishing remains manual.

---

# 4. COMPLETE MASTER PIPELINE

## 4.1 High-level pipeline

```text
[00] STARTUP / DOCTOR / CONFIG VALIDATION
        ↓
[01] PLAYLIST INGESTION
        ↓
[02] PERMANENT SERIAL ASSIGNMENT / REUSE
        ↓
[03] SELECT NEXT PROCESSABLE OCCURRENCE
        ↓
[04] CREATE SONG WORKSPACE
        ↓
[05] SOURCE ACQUISITION FROM YT MUSIC
        ↓
[06] SOURCE VALIDATION + HASHING
        ↓
[07] RAW → NORMALIZED → MP3 METADATA MODEL
        ↓
[08] OPTIONAL SPOTIFY ENRICHMENT
        ↓
[09] CANONICAL ISRC DETERMINATION
        ↓
[10] ISRC-ONLY DUPLICATE GATE
        ↓
[11] YOUTUBE MUSIC-VIDEO DISCOVERY
        ↓
[12] LRCLIB SYNCHRONIZED LYRICS
        ↓
[13] ARTWORK SELECTION
        ↓
[14] BUILD / VALIDATE PHASE 1 SONG PACKAGE
        ↓
[15] SHARED DEMUCS SEPARATION
        ↓
[16] VOCAL ACTIVITY / ENERGY MAP
        ↓
[17] LRC PARSE + REVERSIBLE TELUGU NORMALIZATION
        ↓
[18] LRC ANCHOR MODEL
        ↓
[19] REFERENCE-AWARE CHUNKING
        ↓
[20] MMS INITIALIZATION
        ↓
[21] MMS FRAME-LEVEL EMISSIONS
        ↓
[22] CTC REFERENCE FORCED ALIGNMENT
        ↓
[23] TOKEN → WORD SPANS
        ↓
[24] CHUNK QUALITY + RETRIES
        ↓
[25] DUAL-AUDIO FALLBACK WHERE NEEDED
        ↓
[26] OVERLAP DEDUPLICATION
        ↓
[27] GLOBAL WORD/LINES MERGE
        ↓
[28] ANCHOR DRIFT + INSTRUMENTAL ANALYSIS
        ↓
[29] PHASE 2 QUALITY GATE
        ↓
[30] CANONICAL WORD TIMELINE
        ↓
[31] WORD-LEVEL LRC + SURGICAL SYLT + PHASE 2 JSON
        ↓
[32] FULL-SONG ACOUSTIC FEATURE EXTRACTION
        ↓
[33] LYRIC / REPETITION / PHRASE ANALYSIS
        ↓
[34] SONG STRUCTURE DISCOVERY
        ↓
[35] HOOK CORE CANDIDATE GENERATION
        ↓
[36] HOOK CORE SCORING
        ↓
[37] HARD HOOK FILTERS
        ↓
[38] HOOK-FAMILY CLUSTERING
        ↓
[39] 10–15 DISTINCT FINALISTS
        ↓
[40] LEAD-IN SEARCH
        ↓
[41] TAIL SEARCH
        ↓
[42] FINAL REEL SEGMENT SCORING
        ↓
[43] SELECT FINAL REEL SOURCE TIMELINE
        ↓
[44] EXTRACT CLEAN SOURCE-SONG QUERY AUDIO
        ↓
[45] DOWNLOAD COMPLETE YOUTUBE VIDEO AUDIO ONLY
        ↓
[46] AUDIO NORMALIZATION / REPRESENTATIONS
        ↓
[47] COARSE WHOLE-REFERENCE SEARCH
        ↓
[48] FINE LOCAL ALIGNMENT
        ↓
[49] MULTI-ANCHOR VERIFICATION
        ↓
[50] FINAL MATCH CONFIDENCE
        ↓
[51] DOWNLOAD ONLY REQUIRED VIDEO SECTION + GUARD
        ↓
[52] EXACT VIDEO TRIM
        ↓
[53] STATEFUL SUBJECT TRACKING
        ↓
[54] SMART 9:16 CROP PATH
        ↓
[55] LOCAL SOURCE AUDIO → 8D/SPATIAL AUDIO
        ↓
[56] WORD-LEVEL TELUGU KARAOKE COMPOSITION
        ↓
[57] VIDEO + AUDIO + KARAOKE ASSEMBLY
        ↓
[58] CROSS-OUTPUT VALIDATION
        ↓
[59] FINAL REEL JSON
        ↓
[60] OUTPUT HASHING
        ↓
[61] ATOMIC ARTIFACT PROMOTION
        ↓
[62] DATABASE COMMIT / STATE FINALIZATION
        ↓
[63] CLEAN TEMPORARIES
        ↓
[64] SONG COMPLETE
        ↓
[65] NEXT SONG
```

---

# 5. DIRECTORY CONTRACT

## 5.1 Unified project tree

```text
unified_song_to_reel_project/
│
├── main.py
├── config.json
├── requirements.lock
├── requirements-dev.txt
├── README.md
├── CHANGELOG.md
├── BUILD_INFO.md
├── .gitignore
│
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── db.py
│   ├── hashing.py
│   ├── scanner.py
│   ├── package_validator.py
│   ├── playlist_ingest.py
│   ├── downloader.py
│   ├── metadata.py
│   ├── spotify.py
│   ├── duplicate_checker.py
│   ├── youtube_finder.py
│   ├── youtube_info.py
│   ├── lrclib.py
│   ├── artwork.py
│   ├── embedder.py
│   ├── audio_io.py
│   ├── demucs.py
│   ├── activity_detector.py
│   ├── lrc_reader.py
│   ├── telugu_normalizer.py
│   ├── tokenizer.py
│   ├── chunker.py
│   ├── mms_model.py
│   ├── ctc_aligner.py
│   ├── word_builder.py
│   ├── alignment_merger.py
│   ├── lyric_validator.py
│   ├── lrc_generator.py
│   ├── phase2_json.py
│   ├── acoustic_analyzer.py
│   ├── lyric_analyzer.py
│   ├── phrase_repetition.py
│   ├── song_structure.py
│   ├── hook_candidates.py
│   ├── hook_scorer.py
│   ├── hook_diversity.py
│   ├── hook_context.py
│   ├── hook_selector.py
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
│   ├── logging_utils.py
│   ├── models.py
│   └── pipeline.py
│
├── songs/
│   ├── synced_lyrics/       # Phase 1 retained package; immutable after Phase 1 commit
│   ├── no_synced_lyrics/    # retained songs that cannot enter word-sync/Reel stage
│   └── final/               # Phase 2 word-level package; immutable Phase 3 input
│
├── reels/
│   └── generated/
│       ├── Song_reel.mp4
│       └── Song_reel.json
│
├── temp/
│   └── <song_key>/
│       ├── input_snapshot/
│       ├── phase1/
│       ├── shared_audio/
│       ├── phase2/
│       ├── intelligence/
│       ├── matching/
│       ├── video/
│       ├── render/
│       ├── stage_final/
│       └── logs/
│
├── models/
│   └── mms/
│
├── db/
│   └── project.db
│
├── logs/
│   └── project.log
│
├── scripts/
│   ├── init_db.py
│   ├── clean_runtime.py
│   ├── inspect_song.py
│   ├── inspect_hook.py
│   ├── validate_reel.py
│   └── reembed_existing.py
│
└── tests/
    ├── unit/
    ├── integration/
    ├── failure/
    └── fixtures/
```

## 5.2 Immutable directories

The following are treated as immutable inputs after their stage completes:

```text
songs/synced_lyrics/
songs/final/
```

The original incoming package is also read-only whenever it exists as an external source directory.

No temporary file should be written beside a protected input artifact.

---

# 6. SONG IDENTITY MODEL

## 6.1 Playlist occurrence identity

Every occurrence in the playlist gets a permanent integer serial number.

Properties inherited from Phase 1:

- playlist order is authoritative;
- serial numbers never change;
- serial numbers are never reused;
- repeated playlist occurrences remain distinct;
- the serial is the stable playlist-occurrence identity.

## 6.2 Retained-song identity

A retained song remains logically distinct from the playlist occurrence.

When an ISRC exists, ISRC is the sole duplicate identifier for retained-song duplicate detection.

No title/artist/duration/audio-hash/fuzzy/composite heuristic may silently replace ISRC-only duplicate logic.

## 6.3 Processing identity

A processing run identity contains at minimum:

```text
playlist_serial or retained song ID
basename
mp3_sha256
lrc_sha256
json_sha256
pipeline_version
config_hash
Demucs model + revision
MMS model + revision
normalizer_version
hook_algorithm_version
video_match_algorithm_version
crop_algorithm_version
8D algorithm version
lyric renderer version
```

A validated output may be skipped when the same processing identity already produced a valid result.

---

# 7. UNIFIED DATABASE DESIGN

## 7.1 Design goal

The database is the operational state store. Files remain the durable artifact layer.

The database must never become the only copy of the actual song package, word timeline, or final Reel.

## 7.2 `playlist_entries`

Retain the Phase 1 logical table and its semantics:

```sql
CREATE TABLE playlist_entries (
    serial_number INTEGER PRIMARY KEY,
    playlist_position INTEGER NOT NULL,
    ytm_playlist_id TEXT,
    ytm_video_id TEXT,
    ytm_url TEXT,
    title TEXT NOT NULL,
    artist TEXT NOT NULL,
    album TEXT,
    duration INTEGER,
    ytm_playlist_item_json TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

For the integrated state machine, the `status` field may either remain Phase-1-compatible and be complemented by `processing_runs`, or be expanded through a schema version migration. The preferred design is to keep the legacy-compatible occurrence state and store detailed stage state separately.

Indexes:

```sql
CREATE INDEX idx_playlist_status_position
ON playlist_entries(status, playlist_position, serial_number);

CREATE INDEX idx_playlist_video_id
ON playlist_entries(ytm_video_id);
```

## 7.3 `songs`

Retain the complete Phase 1 normalized song record and source/provenance columns. The integrated build should not throw away the existing detailed Phase 1 schema merely because a normalized relational design might otherwise look cleaner.

Add stable integration identifiers where needed:

```text
song_id
playlist_serial_number
phase1_package_status
phase2_status
reel_status
```

The full Phase 1 song schema remains preserved in the source appendix.

## 7.4 `processing_runs`

```sql
CREATE TABLE processing_runs (
    run_id TEXT PRIMARY KEY,
    song_id INTEGER NOT NULL,
    stage TEXT NOT NULL,
    state TEXT NOT NULL,
    quality_status TEXT,
    pipeline_version TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    attempt INTEGER NOT NULL DEFAULT 1,
    error_code TEXT,
    error_message TEXT,
    metrics_json TEXT,
    FOREIGN KEY(song_id) REFERENCES songs(song_id)
);
```

## 7.5 `processing_events`

Append-only operational events:

```sql
CREATE TABLE processing_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL,
    stage TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT,
    message TEXT
);
```

## 7.6 `alignment_chunks`

Logical fields:

```text
run_id
chunk_index
start_ms
end_ms
anchor_start_ms
anchor_end_ms
context_start_ms
context_end_ms
line_indices_json
attempt_count
audio_source
model_revision
status
quality_score
error_code
output_json_path
```

## 7.7 `word_alignments`

Logical fields:

```text
song_id
line_index
word_index
original
normalized
start_ms
end_ms
score
source
interpolated
chunk_index
alignment_token_start
alignment_token_end
```

The canonical word timeline is derived from this structure.

## 7.8 `instrumental_sections`

Fields:

```text
song_id
start_ms
end_ms
section_type
confidence
source_evidence_json
```

## 7.9 `hook_candidates`

Fields should capture every important scoring component rather than storing only one opaque total:

```text
song_id
candidate_id
start_ms
end_ms
duration_ms
core_start_ms
core_end_ms
source_family
lyric_score
vocal_score
repetition_score
energy_score
arrangement_score
contour_score
phrase_completeness_score
timing_score
hard_filter_status
hard_filter_reasons
raw_score
normalized_score
rank_before_clustering
family_id
```

## 7.10 `hook_families`

Fields:

```text
family_id
song_id
representative_candidate_id
member_count
lyric_signature
musical_signature
occurrence_signature
family_score
diversity_metadata_json
```

## 7.11 `video_matches`

Fields:

```text
song_id
candidate_id
youtube_video_id
query_start_ms
query_end_ms
video_match_start_ms
video_match_end_ms
coarse_score
fine_score
anchor_scores_json
confidence
algorithm_version
accepted
failure_reason
```

## 7.12 `artifacts`

Every materialized file should be registered:

```text
artifact_id
song_id
run_id
artifact_type
path
size
sha256
created_at
status
metadata_json
```

Artifact types include:

```text
phase1_mp3
phase1_lrc
phase1_json
demucs_vocals
demucs_drums
demucs_bass
demucs_other
phase2_lrc
phase2_mp3
phase2_json
youtube_audio
youtube_video_segment
cropped_video
audio_8d
karaoke_ass
reel_mp4
reel_json
```

---

# 8. MASTER STATE MACHINE

## 8.1 Playlist occurrence states

Keep Phase 1 occurrence-compatible values:

```text
pending
completed
duplicate
error
```

## 8.2 Unified song-stage states

Use detailed state in `processing_runs`:

```text
QUEUED
ACQUIRING
SOURCE_VALIDATED
ENRICHED
DUPLICATE_CHECK
DUPLICATE_REVIEW
SONG_PACKAGE_STAGED
SONG_PACKAGE_FINALIZED
BLOCKED_NO_SYNC_LYRICS
BLOCKED_NO_YOUTUBE_VIDEO
ISOLATING
SHARED_AUDIO_READY
ALIGNING
ALIGNMENT_REVIEW
WORDLEVEL_READY
ANALYZING
HOOK_CANDIDATES_READY
HOOK_FINALISTS_READY
HOOK_SELECTED
QUERY_AUDIO_READY
YOUTUBE_AUDIO_READY
MATCHING
VIDEO_MATCH_READY
VIDEO_SECTION_READY
VIDEO_RENDERED
AUDIO_RENDERED
LYRICS_RENDERED
ASSEMBLING
VALIDATING
READY_TO_FINALIZE
FINALIZING
FINALIZED
NEEDS_REVIEW
FAILED
```

## 8.3 Quality status

Independent of state:

```text
unknown
good
partial
needs_review
failed
```

## 8.4 State transition principle

A failure in one song must not corrupt the playlist queue.

The worker records failure state, preserves diagnostic artifacts, and moves to the next eligible playlist entry unless the failure requires explicit operator intervention.

---

# 9. CONFIGURATION MASTER PLAN

The unified `config.json` should preserve all important Phase 1 and Phase 3 settings and introduce namespaced Phase 2 settings.

A representative top-level structure is:

```json
{
  "project": {
    "name": "unified_song_to_reel",
    "pipeline_version": "1.0.0",
    "language": "te",
    "language_iso3": "tel"
  },
  "ytmusic": {
    "playlist_id": "YOUR_PLAYLIST_ID",
    "auth_file": null
  },
  "paths": {
    "songs_synced": "songs/synced_lyrics",
    "songs_no_synced": "songs/no_synced_lyrics",
    "songs_final": "songs/final",
    "reels": "reels/generated",
    "temp": "temp",
    "database": "db/project.db",
    "logs": "logs"
  },
  "download": {
    "audio_format": "mp3",
    "audio_quality": "0",
    "write_info_json": true,
    "write_thumbnail": true,
    "convert_thumbnail": "jpg",
    "write_all_thumbnails": true
  },
  "youtube_video_search": {
    "results_to_fetch": 10,
    "skip_title_keyword": "lyrics"
  },
  "spotify": {
    "enabled": false,
    "client_id": "",
    "client_secret": "",
    "use_env": true,
    "market": "IN",
    "search_limit": 10,
    "duration_tolerance_seconds": 2,
    "timeout_seconds": 30,
    "max_retries": 3,
    "fail_on_error": false,
    "artwork": {
      "enabled": true,
      "timeout_seconds": 30,
      "fail_on_error": false
    }
  },
  "lyrics": {
    "enabled": true,
    "timeout_seconds": 30,
    "max_retries": 3,
    "request_delay_seconds": 0.5,
    "endpoint": "/api/get",
    "download_only_synced": true,
    "embed_synced": true,
    "embed_plain_fallback": true
  },
  "phase2": {
    "language": "te",
    "model": "facebook/mms-1b-all",
    "normalizer_version": "1.0",
    "alignment_sample_rate": 16000,
    "chunk_target_seconds": 12,
    "chunk_min_seconds": 4,
    "chunk_max_seconds": 20,
    "overlap_seconds": 2,
    "anchor_search_seconds": 2.5,
    "max_chunk_retries": 3,
    "dual_audio_fallback": true
  },
  "phase3": {
    "hook_core_min_seconds": 10,
    "hook_core_max_seconds": 35,
    "lead_in_min_seconds": 0.5,
    "lead_in_max_seconds": 5,
    "tail_max_seconds": 5,
    "preferred_reel_min_seconds": 15,
    "preferred_reel_max_seconds": 60,
    "preferred_duration_min_seconds": 25,
    "preferred_duration_max_seconds": 35,
    "final_width": 1080,
    "final_height": 1920,
    "youtube_audio_guard_seconds": 1.5,
    "hook_finalist_target": 10,
    "hook_finalist_max": 15,
    "manual_hook_enabled": true
  },
  "audio_8d": {
    "enabled": true,
    "preserve_timeline": true
  },
  "retry": {
    "max_attempts": 3,
    "backoff_seconds": 2
  },
  "runtime": {
    "yt_dlp_binary": "yt-dlp",
    "cookies_file": "cookies.txt",
    "ffmpeg_location": null,
    "js_runtime": "auto",
    "js_runtime_path": null,
    "socket_timeout_seconds": 30,
    "download_timeout_seconds": 3600,
    "youtube_search_timeout_seconds": 120,
    "youtube_metadata_timeout_seconds": 120
  },
  "artwork": {
    "og_image_enabled": true,
    "og_image_timeout_seconds": 30,
    "force_square": true,
    "max_dimension": 1200,
    "jpeg_quality": 98
  },
  "filesystem": {
    "max_filename_length": 180
  },
  "duplicate_detection": {
    "enabled": true,
    "identifier": "isrc",
    "on_duplicate": "prompt"
  }
}
```

Configuration must remain an operational layer, not a way to silently disable architectural invariants such as ISRC-only duplicate detection, synchronized lyrics as the Phase 3 prerequisite, source-audio authority, input immutability, and timeline preservation.

---

# 10. RUNTIME DEPENDENCIES

## 10.1 Python

The source specifications target Python 3.11+.

## 10.2 Functional packages inherited from Phase 1/2/3 responsibilities

At minimum the project requires the relevant portions of:

```text
yt music API client support
 yt-dlp
mutagen
requests
Pillow
PyTorch
Transformers / MMS support
Demucs
Silero VAD or equivalent configured detector
MediaPipe or the configured subject-tracking stack
FFmpeg
FFprobe
```

The exact pinned package versions belong in `requirements.lock` and must be recorded in `BUILD_INFO.md`.

## 10.3 External binaries

Required:

```text
FFmpeg
FFprobe
supported JavaScript runtime where yt-dlp requires it
```

## 10.4 Runtime doctor

`python main.py --doctor` checks:

- Python version;
- FFmpeg;
- FFprobe;
- yt-dlp;
- YT Music authentication if configured;
- JavaScript runtime if needed;
- GPU availability;
- CUDA/PyTorch compatibility;
- Demucs model availability;
- MMS model availability;
- writable temp/output/database paths;
- configuration validity.

---

# 11. PLAYLIST INGESTION — DETAILED INTEGRATED SPECIFICATION

## 11.1 Read configuration

Load and validate configuration before creating network clients or database transactions.

## 11.2 Initialize YT Music client

Use the configured authentication file when supplied.

## 11.3 Retrieve complete playlist

Returned YT Music order is authoritative.

Do not alphabetically sort or re-rank the playlist.

## 11.4 Preserve unavailable entries

When an item has no usable `videoId` or is marked unavailable:

```text
retain serial
retain playlist position
status = error or pending according to retry policy
```

It must not crash the entire playlist ingestion.

## 11.5 Existing entries

Existing serial identities remain stable.

A later ingestion must not silently renumber earlier playlist occurrences.

## 11.6 New entries

Assign new permanent serials only to new playlist occurrences.

## 11.7 Ingestion summary

At the end of ingestion, print/store:

```text
playlist size
new entries
existing entries
unavailable entries
pending entries
completed entries
duplicates
errors
```

---

# 12. PER-SONG WORKSPACE

For serial `001`:

```text
 temp/001_<song_key>/
```

Suggested hierarchy:

```text
input_snapshot/
    source.mp3
    source.lrc
    source.json

phase1/
    master.mp3
    master.info.json
    metadata.json
    artwork/
    candidate_video.json
    lrclib_response.json
    staged/

shared_audio/
    source_16k.wav
    vocals.wav
    drums.wav
    bass.wav
    other.wav
    activity.json
    energy.json

phase2/
    chunks/
    chunk_results/
    alignment.json
    validation.json
    word_level.lrc
    staged/

intelligence/
    acoustic_features.json
    lyric_analysis.json
    phrase_clusters.json
    song_structure.json
    hook_candidates.json
    hook_rankings.json
    hook_families.json
    finalists.json
    selected_segment.json

matching/
    query.wav
    youtube_audio.m4a
    coarse_matches.json
    fine_matches.json
    anchor_verification.json
    match_result.json

video/
    guarded_section.mp4
    exact_section.mp4
    tracking.json
    crop_path.json
    cropped_9x16.mp4

render/
    reel_audio.wav
    karaoke.ass
    assembled.mp4
    validation.json

stage_final/
    phase2 package files
    reel files

logs/
    song.log
```

---

# 13. PHASE 1 SOURCE ACQUISITION

## 13.1 One complete initial yt-dlp acquisition

Acquire once for:

```text
master.mp3
master.info.json
thumbnails
```

Do not use `--add-metadata` as the initial acquisition strategy.

The reason is that final metadata is written intentionally by the application and detailed provenance is placed in JSON rather than being dumped into the MP3.

## 13.2 Source validation

Check:

- file exists;
- file is readable;
- valid audio stream;
- finite duration;
- sample rate available;
- codec/container available;
- FFmpeg/FFprobe decode succeeds;
- source remains unchanged afterward.

## 13.3 Hash immediately

Compute SHA-256 for:

```text
master.mp3
master.info.json
selected source inputs
```

Input package hashes are the authoritative content identities.

---

# 14. METADATA NORMALIZATION

Maintain three conceptual layers.

## Layer A — Raw metadata

Preserve detailed YT Music/yt-dlp metadata.

## Layer B — Normalized application metadata

Normalize title, artist, album, album artist, release/date fields, duration, genre, composer, publisher, copyright, language, BPM, compilation, identifiers, and source references.

## Layer C — Final MP3 metadata

Write a compact player-facing ID3 set.

Do not copy every raw field into the MP3.

The detailed data belongs in the JSON sidecar.

---

# 15. SPOTIFY ENRICHMENT

Spotify remains optional.

Rules inherited from Phase 1:

- Client Credentials authentication.
- Credentials may come from configuration or environment variables.
- Search query is exactly title + album.
- Returned order is preserved.
- First candidate inside duration tolerance is selected.
- No application-side ranking beyond returned order and duration compatibility.
- Spotify can provide catalog metadata and artwork.
- Spotify ISRC is preferred when valid.
- Source ISRC may be used if Spotify does not provide one.
- Spotify artwork bytes are preserved unchanged.
- Failure is configurable and does not automatically fail the entire song by default.

All request/response provenance required by Phase 1 is retained in the song JSON.

---

# 16. ISRC CANONICALIZATION AND DUPLICATE CONTROL

Normalize ISRC by:

```text
remove spaces
remove hyphens
uppercase alphanumeric content
validate expected standard form
```

Invalid ISRC is treated as missing.

When missing/invalid:

```text
no duplicate lookup
```

When a duplicate is found:

### Keep previous

- existing retained song unchanged;
- existing MP3/LRC/JSON unchanged;
- temporary current acquisition discarded;
- current playlist occurrence marked duplicate;
- no new retained-song row created.

### Keep current

- new package must be fully built and validated first;
- old physical artifacts must not be destroyed early;
- database transition occurs transactionally;
- old playlist serial returns to pending as defined by Phase 1;
- current serial becomes completed;
- old physical artifacts are cleaned only after successful commit.

Serial identity never changes.

---

# 17. YOUTUBE MUSIC-VIDEO DISCOVERY

Use the source metadata-derived query:

```text
{title} {album} official video song
```

Fetch the configured number of results.

Skip a result only when its title contains the configured exclusion word `lyrics` case-insensitively.

Select the first remaining result.

Do not add a ranking system to this Phase 1 discovery step.

Save:

```text
video_id
url
title
selected=true
search_query
result_index
fetched_count
selected-result metadata
```

The selected video ID becomes the authoritative Phase 3 visual source identifier.

---

# 18. LRCLIB SYNCHRONIZED LYRIC ACQUISITION

Allowed endpoint:

```text
GET /api/get
```

Do not use `/api/search`.

Accept synchronized lyrics only.

Plain-only lyric responses do not qualify as a synchronized `.lrc` package.

The downloaded LRC is stored alongside the retained MP3.

The MP3 receives synchronized lyric embedding plus compatibility plain-text projection according to Phase 1's metadata behavior.

---

# 19. PHASE 1 ARTWORK

## 19.1 Provider precedence

When Spotify artwork is enabled, successfully matched, and valid, Spotify is preferred.

The largest Spotify image is used and preserved byte-for-byte.

## 19.2 YT Music fallback

Consider useful yt-dlp thumbnail variants and optional OpenGraph image.

When normalizing a YT Music fallback:

- validate image;
- prefer square candidate;
- normalize non-square fallback to square when configured;
- use configured maximum dimension and JPEG quality.

Embed final cover as APIC.

---

# 20. PHASE 1 MP3 METADATA CONTRACT

The MP3 intentionally contains concise player-facing metadata, including where available:

```text
Title
Track artist
Album artist
Album
Release date
Track number
Disc number
Genre
Composer
Publisher/label
Copyright
Language
BPM
Compilation
Actual duration
Canonical ISRC
YT Music source video ID/URL
Selected YouTube video ID/URL/title
Spotify IDs/URL/ISRC when matched
Front cover artwork
Synchronized lyrics
Small durable application metadata using TXXX/UFID/WXXX
```

Do not put large raw API blobs, source descriptions, or verbose debugging/provenance into the main MP3 metadata.

---

# 21. PHASE 1 SIDEcar JSON

Every finalized song package has a detailed same-basename JSON sidecar.

It can contain:

- normalized metadata;
- playlist identity;
- YT Music playlist item JSON;
- yt-dlp source `info.json`;
- Spotify search/match data;
- Spotify track and album data;
- artwork provenance;
- selected YouTube search data;
- selected YouTube information JSON;
- LRCLIB response/matching data;
- synchronized lyric text;
- artwork hashes;
- MP3 hash/size;
- LRC status/path;
- duplicate decision;
- build/schema versions.

Phase 2 adds its `phase2` namespace.

Phase 3 never edits this source song JSON in place; it creates its own Reel JSON.

---

# 22. PHASE 1 FINALIZATION ORDER

The safe order is:

```text
build staging MP3
↓
write metadata
↓
embed artwork
↓
embed synchronized lyrics
↓
write sidecar JSON
↓
validate MP3
↓
hash MP3/LRC/JSON
↓
atomic promotion to retained output
↓
transactional DB commit
↓
cleanup temp
```

A failed validation never becomes a completed retained artifact.

---

# 23. PHASE 2 INPUT GATE

The word-level alignment stage starts only when all required inputs exist:

```text
Song.mp3
Song.lrc
Song.json
```

The LRC must be synchronized and parseable.

The JSON must contain the Phase 1 cumulative provenance and the selected YouTube video record required downstream.

The source MP3/LRC/JSON are read-only.

---

# 24. PHASE 2 JSON PRESERVATION

Load the complete JSON object.

Do not reconstruct a new reduced JSON from a fixed schema.

All unknown top-level keys must survive unchanged.

Phase 2 owns one top-level namespace:

```json
"phase2": { ... }
```

Recommended internal structure:

```json
"phase2": {
  "current": { ... },
  "history": [ ... ]
}
```

The exact history retention can be configured, but the current run must always be reconstructable.

---

# 25. SHARED DEMUCS AUDIO PREPARATION

Convert the source song to the alignment sample rate as needed.

Run Demucs once per processing identity.

Expected stems:

```text
vocals.wav
drums.wav
bass.wav
other.wav
```

Validate each stem before use.

The vocal stem feeds Phase 2 acoustic alignment evidence.

All stems remain available for Phase 3 hook analysis and final 8D rendering until the last dependent stage finishes.

On RTX 5050 laptop targets:

- prefer CUDA for Demucs when available;
- track VRAM;
- implement OOM fallback/retry;
- keep video tracking primarily on CPU to preserve GPU memory for audio tasks.

---

# 26. VOCAL ACTIVITY AND ENERGY MAP

Compute:

```text
VAD/activity map
RMS/energy map
vocal activity evidence
energy minima/maxima
lyric-free regions
```

Treat VAD as evidence rather than a perfect classifier of singing.

Use combined evidence from:

- LRC gaps;
- blank timestamp markers;
- VAD;
- energy;
- aligned word coverage.

---

# 27. TELUGU NORMALIZATION

Create reversible normalization.

Preserve:

```text
original text
normalized text
mapping between them
```

Normalization may simplify punctuation/whitespace or other alignment-unfriendly details but must not silently change the user-facing lyric wording.

The alignment text is not automatically the display text.

---

# 28. LRC ANCHOR MODEL

Treat source LRC timing as coarse scaffolding.

For each lyric line store:

```text
source_lrc_start_ms
line index
original text
word inventory
anchor search region
```

An initial search window around the LRC anchor may begin near ±2.5 seconds and expand adaptively when acoustic evidence requires it.

Do not force alignment to an inaccurate LRC timestamp merely to minimize anchor drift.

---

# 29. REFERENCE-AWARE CHUNKING

Chunk around:

- LRC boundaries;
- lyric density;
- long blank lyric gaps;
- VAD boundaries;
- energy minima;
- anchor locations;
- model context requirements.

Target approximately:

```text
12 seconds target
4 seconds soft minimum
20 seconds soft maximum
```

with overlapping context.

Chunk priorities should favor lyric-dense regions and important anchor boundaries.

The system must record chunk provenance and timing.

---

# 30. SAMPLE-SONG GAP BEHAVIOR

The supplied sample includes two significant lyric-free areas approximately:

```text
01:37.29 → 02:12.94
03:11.72 → 04:12.82
```

These must influence:

- chunk boundaries;
- alignment search regions;
- instrumental inference;
- validation;
- downstream song structure analysis.

The aligner must not invent lyric words throughout such regions simply because a model is capable of producing acoustic hypotheses there.

---

# 31. MMS MODEL INITIALIZATION

Primary alignment model:

```text
facebook/mms-1b-all
```

with the configured Telugu adapter.

The model revision must be recorded.

Model files are cached in:

```text
models/mms/
```

Model load should occur once per worker process where practical.

Record runtime device:

```text
cuda
or
cpu
```

---

# 32. MMS IS ACOUSTIC EVIDENCE, NOT THE TRANSCRIPT

The alignment pipeline must remain:

```text
provided LRC reference transcript
        ↓
normalized reference
        ↓
MMS frame-level acoustic emissions
        ↓
CTC forced alignment
        ↓
known-word spans
```

It must not become:

```text
MMS/Whisper ASR transcript
        ↓
replace supplied lyrics
```

The source lyric wording remains the reference.

---

# 33. CTC FORCED ALIGNMENT

For each chunk:

1. obtain normalized reference tokens;
2. obtain frame-level MMS emissions;
3. construct a CTC alignment trellis;
4. find the best reference-consistent path;
5. convert path positions to timestamps;
6. map token spans to words;
7. compute alignment confidence;
8. return local spans in chunk coordinates;
9. convert to absolute song time.

Keep the trellis/alignment implementation deterministic.

---

# 34. TOKENIZATION MAPPING

The tokenizer must preserve enough mapping to recover:

```text
original word index
normalized word index
alignment token indices
```

When a word expands into multiple tokens, its word span is constructed from the minimum/maximum token span associated with that word.

Unsupported punctuation or text must not disappear without provenance.

---

# 35. WORD RECORD

Canonical word record:

```json
{
  "line_index": 0,
  "word_index": 0,
  "original": "గెలుపు",
  "normalized": "గెలుపు",
  "start_ms": 25020,
  "end_ms": 25400,
  "score": 0.91,
  "source": "aligned",
  "interpolated": false
}
```

Possible `source` values:

```text
aligned
interpolated
missing
unsupported
```

Directly aligned words must remain distinguishable from inferred/interpolated words.

---

# 36. LOW-CONFIDENCE / MISSING / INTERPOLATED WORDS

## Low confidence

Retain the word and score. Do not silently remove it.

## Missing

Record the missing state and reason.

## Interpolated

Interpolation is explicitly labeled and never represented as if it had equivalent confidence to direct acoustic alignment.

## Whole-chunk fallback

If a chunk is poor:

```text
retry
↓
change relevant chunk parameters
↓
possibly try original-mix alignment
↓
retain the best validated result
```

---

# 37. DUAL-AUDIO ALIGNMENT STRATEGY

Primary:

```text
Demucs vocal stem
```

Fallback:

```text
original mix
```

Selection should consider alignment quality and validation evidence.

The system must prefer the better validated alignment, not blindly prefer one source forever.

---

# 38. OVERLAP DEDUPLICATION

Because chunks overlap, the same word can appear in multiple local alignment results.

Deterministic preference order:

1. candidate inside logical chunk region;
2. higher alignment score;
3. candidate that fits the anchor structure better;
4. deterministic chunk-index tie-break.

Only one word record survives into the canonical word timeline.

---

# 39. GLOBAL MERGE

Merge:

```text
local token spans
↓
absolute timestamps
↓
word spans
↓
overlap deduplication
↓
line assignment
↓
song-wide chronological order
```

The result must be deterministic.

---

# 40. LINE RECONSTRUCTION AND ANCHOR DRIFT

For each source LRC line:

```text
source_lrc_start_ms
aligned_line_start_ms
shift_ms = aligned - source
```

Record metrics such as:

```text
median anchor shift
mean absolute shift
p90 absolute shift
maximum shift
```

Flag severe patterns including:

- long runs of unexpected same-direction drift;
- large isolated shifts;
- discontinuities;
- collapse into neighboring repeated section.

Small timing differences must not automatically fail the alignment.

---

# 41. INSTRUMENTAL SECTION INFERENCE

Infer possible instrumental sections using combined evidence:

```text
no reliable aligned words
+
weak vocal activity
+
LRC gap/blank marker
+
energy structure
```

Represent sections with:

```text
start_ms
end_ms
section_type
confidence
evidence
```

Possible section types include:

```text
candidate_instrumental
confirmed_instrumental
silence
unknown_non_lyric
```

---

# 42. PHASE 2 QUALITY MODEL

Measure independently:

```text
word count
aligned word count
missing word count
interpolated word count
mean score
p10 score
minimum score
low-score percentage
interpolated percentage
anchor drift statistics
chunk failure statistics
```

Quality statuses:

```text
good
partial
needs_review
failed
```

Whole-song quality does not automatically determine Reel eligibility. A Reel can proceed when the selected hook region has strong local timing quality even when unrelated song sections are poor, provided the integration validator explicitly confirms the selected region is reliable.

---

# 43. CANONICAL WORD TIMELINE

The canonical timeline is the central artifact connecting Phase 2 and Phase 3.

Logical structure:

```text
Song
 ├── line 0
 │    ├── word 0
 │    ├── word 1
 │    └── ...
 ├── line 1
 │    └── ...
 └── ...
```

Every word has start and end.

Every line preserves original source wording.

Every timing decision is traceable to alignment evidence or explicitly labeled inference.

---

# 44. WORD-LEVEL LRC EXPORT

The final LRC is a derived export of the canonical word timeline.

The canonical millisecond values remain in JSON/database.

The LRC renderer applies one deterministic precision/rounding rule.

The LRC must never be read back and used as the canonical timing source.

Meaningful source blank markers may be preserved consistently.

---

# 45. PHASE 2 MP3 SURGICAL EMBEDDING

The output MP3 is based on a copy of the source MP3.

The embedder must:

```text
open existing tags
↓
preserve all existing frames
↓
add/update only Phase 2-owned synchronized lyric frame
↓
save
```

Do not strip and rebuild tags.

Existing `SYLT`, `USLT`, `APIC`, `TXXX`, `UFID`, `WXXX`, and other pre-existing frames must survive unless a specific frame is explicitly owned by the Phase 2 updater.

Phase 2 should use a deterministic descriptor/owner identity for its SYLT frame so that future reruns can replace its own data without destroying another SYLT record.

---

# 46. PHASE 2 JSON NAMESPACE

The final song JSON retains all original data and adds:

```json
"phase2": {
  "schema_version": 1,
  "pipeline_version": "1.0.0",
  "status": "finished",
  "quality_status": "good",
  "input": {},
  "model": {},
  "audio": {},
  "vocal_isolation": {},
  "lyrics": {},
  "alignment": {},
  "quality": {},
  "instrumental_sections": [],
  "outputs": {},
  "validation": {}
}
```

Do not delete or flatten Phase 1 keys.

---

# 47. PHASE 2 OUTPUT GATE

The Phase 2 package is accepted when:

```text
word-level MP3 exists
word-level LRC exists
word-level JSON exists
JSON parses
original metadata survives
original artwork survives
existing lyric frames survive
canonical word timing passes validation
LRC export is derived from canonical timing
input hashes match recorded values
```

Only after this gate does the package move into `songs/final/` as the canonical Phase 3 input.

---

# 48. PHASE 3 SONG INTELLIGENCE

Now analyze the **complete selected song**, not only a small set of preselected windows.

Inputs:

```text
full local song audio
shared Demucs stems
canonical word timeline
LRC/line model
```

Outputs:

```text
acoustic feature map
lyric feature map
phrase/repetition map
song structure map
```

---

# 49. FULL-SONG ACOUSTIC FEATURES

Analyze:

## Vocals

Possible features:

```text
RMS
activity
onset density
spectral characteristics
vocal continuity
local peaks
```

## Drums

Measure energy/onsets/rhythmic intensity.

## Bass

Measure low-frequency energy and movement.

## Other

Measure harmonic/instrumental density and spatially interesting content.

## Full mix

Measure global RMS/energy envelope, spectral energy, chroma, onset structure, and related normalized features.

Feature normalization must make scores comparable across the song rather than letting raw loudness dominate.

---

# 50. LYRIC ANALYSIS

Use the canonical word timeline and original lyric wording.

Derived metrics include:

```text
words/sec
line duration
inter-line gaps
word gaps
phrase length
phrase completeness
repeated phrases
repeated lines
repeated n-grams
local repetition
recurrence frequency
```

Do not treat blank regions as failed lyrics automatically; they can be musical structure.

---

# 51. REPETITION AND PHRASE CLUSTERS

Create normalized signatures for:

- individual lines;
- phrases;
- short n-grams;
- repeated refrains;
- recurrence across sections.

Use these to identify hook-like lyric material without replacing the original display wording.

Phrase clusters should retain original text examples and all time occurrences.

---

# 52. CHORUS / REFRAIN EVIDENCE

A chorus/refrain candidate is supported by combinations of:

```text
lyric repetition
section recurrence
vocal activity
energy/arrangement recurrence
phrase completeness
```

It is not automatically selected merely because a section occurs multiple times.

The final chorus/occurrence can be better or worse than an earlier occurrence; occurrence quality is scored independently.

---

# 53. SONG STRUCTURE DISCOVERY

Represent candidate repeated sections such as:

```text
intro
verse
pre-chorus/build
chorus/refrain
bridge
instrumental
final chorus/outro
```

These are descriptive structural labels rather than assumptions.

Repeated-section matching should combine lyric and acoustic evidence.

---

# 54. HOOK CORE CANDIDATE GENERATION

Generate candidates from all major families:

### A. Repeated lyric phrases

Strong repeated short phrases.

### B. Repeated lyric lines

Memorable repeated lines.

### C. Chorus/refrain sections

Section-level musical/lyrical recurrence.

### D. Vocal peaks

Strong vocal moments that also satisfy timing and phrase criteria.

### E. Musical peaks

High-energy musical peaks with useful content.

### F. Build → payoff

Transition into a satisfying resolution.

### G. Vocal entrances

A vocal entry following an instrumental setup where the full context improves the hook.

Candidate windows are variable, approximately 10–35 seconds for the hook core search space.

---

# 55. PHRASE-BOUNDARY OPTIMIZATION

Prefer boundaries that coincide with:

- word/phrase starts;
- line starts/ends;
- musical phrase endings;
- beat-aligned boundaries where safe;
- natural transitions.

Avoid:

- cutting through a word;
- cutting during a sustained note;
- abrupt phrase truncation;
- arbitrary fixed-length boundaries.

---

# 56. HOOK CORE SCORING

The inherited Phase 3 weighting is:

```text
Lyric memorability        25%
Vocal quality             20%
Phrase repetition         15%
Musical/rhythmic energy   10%
Arrangement richness      10%
Energy contour            10%
Phrase completeness        5%
Timing quality              5%
```

The final score should be stored as a combination of transparent components rather than a black-box total only.

### Lyric memorability

Consider repetition, compactness, phrase distinctiveness, and recognizable wording.

### Vocal quality

Consider vocal energy, continuity, peak strength, and stable activity.

### Phrase repetition

Reward recurrence and local repetition.

### Musical/rhythmic energy

Reward rhythm, beat/onset activity, and musically meaningful momentum.

### Arrangement richness

Reward sections with supportive multi-stem activity.

### Energy contour

Reward build/payoff and dynamic shape rather than only maximum loudness.

### Phrase completeness

Penalize cuts that omit the semantic/musical completion of the candidate phrase.

### Timing quality

Use word-level timing confidence and boundary reliability.

---

# 57. HARD HOOK FILTERS

Reject or strongly penalize candidates with:

```text
excessive silence
insufficient useful vocal content
too few usable words
severely unresolved timing
broken lyric phrases
unstable boundaries
large fractions of low-confidence words
```

Instrumental material remains allowed when it is functional context:

```text
pickup
build
transition
musical payoff
cadence
```

---

# 58. HOOK-FAMILY CLUSTERING

Do not let sliding-window variants appear as separate finalist ideas.

Example:

```text
01:42–02:10
01:43–02:11
01:44–02:12
01:45–02:13
```

becomes one hook family.

Cluster using combinations of:

```text
temporal overlap
lyric signature
repeated-phrase signature
musical signature
section identity
```

Each family gets a representative candidate.

---

# 59. FINALIST DIVERSITY

Target 10–15 genuinely distinct finalists.

Diversity should come from:

```text
different song locations
Different lyric phrases
Different chorus occurrences
different musical characters
different setup/payoff structures
```

Do not fill the list with near-duplicates.

Record all finalists and their evidence even though only one is finally selected.

---

# 60. MANUAL HOOK OVERRIDE

Automatic analysis remains the default.

Support:

```bash
python main.py --manualhook SongName
```

Interactive prompts:

```text
Start time [HH:MM:SS.mmm]:
End time   [HH:MM:SS.mmm]:
```

Non-interactive form:

```bash
python main.py --manualhook SongName --start 00:02:14.200 --end 00:02:34.800
```

Manual selection bypasses hook discovery/ranking only.

All downstream processing remains identical.

Record:

```json
"hook_selection": {
  "mode": "manual",
  "start_ms": 134200,
  "end_ms": 154800
}
```

Validate that the selected range is inside the source-song duration and that sufficient aligned lyric/audio evidence exists for the downstream Reel.

---

# 61. CONTEXT EXPANSION

After a hook core is chosen, search its neighborhood.

## Lead-in

Search approximately 0.5–5 seconds before the hook core.

Prefer ~2–3 seconds only when it improves flow.

Possible lead-in evidence:

```text
instrumental pickup
chord change
drum buildup
vocal pickup
rising energy
```

## Lead-in rejection

Reject when it introduces:

```text
silence
weak unrelated material
awkward lyric fragment
excessive waiting
```

## Tail

Search approximately 0–5 seconds after the hook core for:

```text
phrase completion
cadence
repeat payoff
natural ending
```

## Final context score

Combine:

```text
hook quality
lead-in usefulness
tail usefulness
boundary naturalness
duration fitness
```

---

# 62. FINAL REEL SEGMENT

The selected Reel segment is represented in the **original source-song timeline**:

```text
reel_start_ms
reel_end_ms
duration_ms
```

This is the master Reel time reference.

All audio, video matching, and lyrics later derive their timing from it.

---

# 63. SOURCE AUDIO EXTRACTION

Extract the exact source-song segment from the local MP3.

Use this clean query audio for video matching.

Do not spatialize it first.

Do not pitch-shift it first.

Do not speed-change it.

The query must represent the true source-song timeline.

---

# 64. YOUTUBE AUDIO-ONLY ACQUISITION

Use the selected Phase 1 YouTube video ID.

Download only audio first.

Do not download the entire high-resolution video before localization.

Store temporary audio in the song workspace.

This audio is a reference signal only.

It is never the final Reel audio.

---

# 65. VIDEO AUDIO MATCHING — PROBLEM DEFINITION

Input:

```text
query = selected local source-song Reel segment
reference = complete audio extracted from selected YouTube video
```

Goal:

```text
find the best occurrence of query inside reference
```

Output:

```text
video_match_start_ms
video_match_end_ms
confidence
```

Do not reduce the problem to a single global offset.

---

# 66. MULTI-STAGE AUDIO MATCHER

## Stage A — normalization

Normalize both signals into comparable analysis representations.

## Stage B — coarse representations

Use:

```text
log-mel
chroma
energy envelope
optional onset representation
```

## Stage C — whole-reference search

Search the complete YouTube audio efficiently and retain roughly the best five local candidates for fine verification.

## Stage D — fine alignment

Use waveform/envelope/chroma/DTW-style local verification and limited tempo variation where configured.

## Stage E — multi-anchor verification

Split the query conceptually into anchors such as:

```text
opening
early
center
late
ending
```

Check whether all anchors converge to one continuous reference timeline.

## Stage F — final confidence

Combine:

```text
coarse evidence
fine alignment score
anchor consistency
continuity
boundary confidence
```

The accepted result must have a recorded confidence value and supporting metrics.

---

# 67. VIDEO MATCH FAILURE POLICY

If confidence is below the configured threshold:

```text
VIDEO_MATCH_LOW_CONFIDENCE
→ needs_review
```

Never:

```text
assume 0 ms offset
```

Never silently use the first occurrence.

The failure must be reconstructable from logs/JSON/database.

---

# 68. VIDEO SECTION DOWNLOAD

After a trusted match:

```text
video_match_start_ms - guard
        ↓
required section
        ↓
video_match_end_ms + guard
```

The default guard is approximately 1.5 seconds unless configured otherwise.

Only the necessary video section is acquired.

---

# 69. EXACT VIDEO TRIM

Trim the guarded download to the exact matched source-song Reel interval.

The exact trimmed section must:

```text
start at 0
have the intended duration
align with the selected source-song Reel timeline
```

---

# 70. SMART 9:16 CROP ENGINE

Final target:

```text
1080 × 1920
```

No stretching.

No black bars.

No distortion.

## Tracking priority

```text
face detection
↓
pose/body fallback
↓
subject identity persistence
```

## Multi-person selection

Prefer the subject who remains relevant to the shot rather than switching to whichever face is currently most salient in a single frame.

## Tracking state

Maintain:

```text
subject identity
last trusted position
velocity/prediction
confidence
visibility state
```

## Prediction

When detections are temporarily absent, predict short-term position rather than jumping.

## Smoothing

Apply temporal smoothing and bounded movement to prevent jitter.

## Composition

The crop should keep the important subject in a visually useful upper/middle region while respecting the 9:16 geometry.

## Lyric-aware placement

The composition should reserve a safe lyric region and avoid placing subtitles across important face/action areas unnecessarily.

## No-subject handling

When no reliable subject exists, use a stable fallback composition rather than unstable searching.

---

# 71. VIDEO RENDERING

Render the exact crop path into a 1080×1920 video.

Record:

```text
source resolution
output resolution
crop path
subject tracker version
tracking confidence statistics
crop movement statistics
fallback frames
```

These statistics belong in the Reel provenance JSON.

---

# 72. FINAL AUDIO ARCHITECTURE

The local song is the sole final audio source.

Use the selected source segment and the shared Demucs stems.

A useful architecture is:

```text
vocals → centered
bass   → centered / mono-compatible
 drums → mostly centered, controlled width
other  → primary spatial movement
```

The exact implementation remains timeline preserving.

---

# 73. 8D / SPATIAL AUDIO ENGINE

## Vocals

Keep centered or near-centered.

## Bass

Keep centered/mono-compatible to protect low-frequency stability and translation.

## Drums

Allow controlled width, not extreme wandering.

## Other

Provide most spatial movement where musically appropriate.

## Phrase-aware modulation

Spatial movement can follow musical/lyrical phrase structure.

Examples:

```text
phrase entrance → movement begins
phrase center → movement emphasis
phrase ending → return/stabilize
```

## Timeline preservation

No processing step is allowed to alter the time base unless that transformation is explicitly propagated through every dependent timeline. The default implementation uses only timeline-preserving operations.

---

# 74. LOUDNESS AND AUDIO VALIDATION

Validate:

```text
integrated loudness
short-term loudness
true peak
clipping
unexpected silence
channel integrity
duration
```

The final Reel audio should meet the configured loudness target within the allowed tolerance.

Record metrics rather than merely saying “audio passed.”

---

# 75. WORD-TIMELINE EXTRACTION FOR REEL

Use only canonical Phase 2 word records that overlap the selected Reel source timeline.

Convert global source-song time to Reel-local time:

```text
local_start = source_start - reel_start
local_end   = source_end   - reel_start
```

Do not regenerate or reinterpret word timing during the Reel stage.

---

# 76. LEAD-IN KARAOKE BEHAVIOR

If the Reel contains instrumental lead-in before the first lyric word:

```text
video starts
audio starts
lyrics remain absent
↓
first canonical word enters at its source-relative time
```

The lyric layer may preserve surrounding line context but must not display words before their canonical start times.

---

# 77. TELUGU KARAOKE COMPOSITION

## 77.1 Canonical source

The canonical word timeline is the only source of word highlighting times.

## 77.2 Continuous context

Display a coherent lyric block rather than isolated words where practical.

The active word is highlighted while surrounding context remains readable.

## 77.3 Typography

Rendering must use a Telugu-capable font stack and validate shaping of Telugu glyph clusters.

Text wrapping must be based on rendered width, not raw character count.

## 77.4 Position

Default placement is centered in a safe region.

## 77.5 Subject-aware placement

Move or choose a safe vertical placement when needed to avoid covering important visual action, while remaining consistent enough not to cause subtitle jitter.

## 77.6 Line grouping

Prefer maximum two-line visual blocks when the source phrase and screen width permit.

## 77.7 Word highlighting

The current word is highlighted exactly over:

```text
start_ms → end_ms
```

## 77.8 Collision validation

Check that lyrics do not extend outside safe zones or clip outside the frame.

---

# 78. KARAOKE VISUAL STYLE

The source specification defines a centered, readable Telugu karaoke presentation rather than a generic subtitle overlay.

Implementation should separate:

```text
base lyric style
active-word style
shadow/outline
font sizing
line spacing
safe margins
```

All visual choices must remain readable across 1080×1920 exports.

---

# 79. FINAL ASSEMBLY

Inputs:

```text
exact 9:16 video
final timeline-preserving audio
karaoke subtitle/render layer
```

Output:

```text
Song_reel.mp4
```

Assembly must begin only after component validation succeeds.

---

# 80. CROSS-OUTPUT VALIDATION

## 80.1 MP4

Verify:

- decodes;
- has video;
- has audio;
- resolution is exactly 1080×1920;
- frame rate is valid;
- no unexpected black bars/stretching.

## 80.2 Audio

Verify:

- derived from local source song;
- YouTube audio not used as final audio;
- duration is expected;
- no clipping;
- loudness within tolerance.

## 80.3 Lyrics

Verify:

- every displayed word comes from canonical word timing;
- word order is correct;
- highlighted interval matches canonical interval;
- Telugu glyphs render correctly;
- no lyric extends beyond its timing;
- no lyric appears after Reel end.

## 80.4 Synchronization

Verify:

```text
video duration
≈ audio duration
≈ Reel timing domain
```

and that selected source-song words map to the same local time domain used for the final audio/video.

## 80.5 Source integrity

Verify the protected source files still hash to the recorded input values.

---

# 81. FINAL OUTPUT PACKAGE

For each Reel-ready song:

```text
reels/generated/
├── SongName_reel.mp4
└── SongName_reel.json
```

The original word-level song package remains:

```text
songs/final/
├── SongName.mp3
├── SongName.lrc
└── SongName.json
```

No extra user-facing files are required.

---

# 82. REEL JSON — MASTER PROVENANCE SCHEMA

Recommended structure:

```json
{
  "schema_version": 1,
  "pipeline_version": "1.0.0",
  "status": "finalized",

  "source": {
    "song_id": "...",
    "basename": "...",
    "mp3_sha256": "...",
    "lrc_sha256": "...",
    "json_sha256": "...",
    "source_duration_ms": 0
  },

  "processing": {
    "run_id": "...",
    "config_hash": "...",
    "models": {},
    "algorithms": {}
  },

  "hook_selection": {
    "mode": "automatic",
    "reel_start_ms": 0,
    "reel_end_ms": 0,
    "duration_ms": 0,
    "selected_candidate_id": "...",
    "selected_family_id": "...",
    "final_score": 0,
    "finalists": []
  },

  "video_source": {
    "youtube_video_id": "...",
    "url": "...",
    "title": "..."
  },

  "video_match": {
    "query_start_ms": 0,
    "query_end_ms": 0,
    "video_match_start_ms": 0,
    "video_match_end_ms": 0,
    "confidence": 0,
    "coarse_score": 0,
    "fine_score": 0,
    "anchors": []
  },

  "video_render": {
    "input_resolution": {},
    "output_resolution": {"width": 1080, "height": 1920},
    "tracker_version": "...",
    "crop_path_artifact": "...",
    "tracking_statistics": {}
  },

  "audio_8d": {
    "source": "local_song",
    "timeline_preserved": true,
    "processing_version": "...",
    "loudness": {},
    "stems": {}
  },

  "lyrics": {
    "language": "te",
    "source": "phase2_canonical_word_timeline",
    "word_count": 0,
    "rendered_word_count": 0,
    "words": []
  },

  "output": {
    "mp4_path": "...",
    "mp4_sha256": "...",
    "mp4_size": 0,
    "json_path": "...",
    "json_sha256": "..."
  },

  "validation": {
    "status": "good",
    "checks": {},
    "metrics": {}
  },

  "errors": []
}
```

The exact JSON fields may be expanded but must remain backward-compatible after schema versioning.

---

# 83. HOOK FINALIST PROVENANCE

The selected Reel JSON must not discard the alternative finalist list.

Record for each finalist:

```text
candidate_id
family_id
core timeline
context timeline
source family
score components
hard-filter result
quality status
```

This makes hook selection explainable without rerunning the analysis.

---

# 84. VIDEO MATCH PROVENANCE

Record:

```text
YouTube video ID
query source timeline
reference audio duration
coarse candidates
fine candidate scores
multi-anchor locations
anchor agreement
accepted start/end
confidence threshold
algorithm version
```

---

# 85. SMART-CROP PROVENANCE

Record:

```text
tracker version
tracking model configuration
subject identity decisions
fallback periods
crop coordinates/path summary
smoothing settings
lyric safe-zone decisions
```

Do not store only the final output video and discard the reasoning needed to understand crop behavior.

---

# 86. AUDIO PROVENANCE

Record:

```text
source MP3 hash
source segment start/end
Demucs model/revision
stem paths/hashes where retained
8D processing version
spatial movement parameters
loudness metrics
true peak
```

Explicitly record that YouTube audio was reference-only.

---

# 87. STATEFUL RECOVERY MODEL

The system must checkpoint expensive work.

## Demucs succeeded, hook scoring failed

Do not rerun Demucs.

Resume from shared audio.

## Hook selected, YouTube audio download failed

Keep:

```text
hook selection
source query clip
```

Retry only the network acquisition/matching branch.

## Video match succeeded, rendering failed

Keep the accepted match and downloaded guarded section.

Retry crop/render/assembly.

## Final MP4 exists, JSON write failed

Treat MP4 as staged/uncommitted.

Validate it, regenerate JSON, then finalize atomically.

## Final package exists, DB state incomplete

Reconcile files/hashes against the database and finalize the database transaction if all integrity checks succeed.

---

# 88. ATOMIC FINALIZATION

Never declare final success merely because an MP4 exists.

Preferred sequence:

```text
build MP4 in stage area
↓
validate MP4
↓
write Reel JSON to stage
↓
validate JSON
↓
hash both
↓
fsync/close as appropriate
↓
atomic rename to final output
↓
DB transaction marks finalized
↓
cleanup temp
```

If database finalization fails, the filesystem artifacts remain in a recoverable staged/final state and a reconciliation command repairs state.

---

# 89. IDEMPOTENCY

For a fixed processing identity:

- do not acquire the same artifact unnecessarily;
- do not rerun Demucs unnecessarily;
- do not recompute word alignment unnecessarily;
- do not redownload YouTube audio unnecessarily;
- do not re-match video unnecessarily;
- do not rerender if final outputs are already validated.

A `--force` mode may invalidate derived stages deliberately.

The force scope must be recorded in the run metadata.

---

# 90. ERROR TAXONOMY

Recommended stable error codes combine all phase concerns.

## Input

```text
INPUT_MP3_MISSING
INPUT_LRC_MISSING
INPUT_JSON_MISSING
INPUT_JSON_INVALID
INPUT_MP3_INVALID
INPUT_LRC_INVALID
WORD_TIMELINE_MISSING
YOUTUBE_VIDEO_ID_MISSING
```

## Acquisition

```text
YTM_UNAVAILABLE
YTDLP_FAILED
YTDLP_TIMEOUT
AUDIO_DECODE_FAILED
```

## Enrichment

```text
SPOTIFY_FAILED
SPOTIFY_NO_MATCH
LRCLIB_FAILED
LRCLIB_NO_SYNC
YOUTUBE_SEARCH_FAILED
YOUTUBE_NO_ACCEPTABLE_RESULT
```

## Duplicate

```text
ISRC_INVALID
DUPLICATE_REVIEW_REQUIRED
DUPLICATE_COMMIT_FAILED
```

## Phase 2

```text
DEMUCS_FAILED
DEMUCS_OOM
VOCAL_STEM_INVALID
VAD_FAILED
NORMALIZATION_FAILED
TOKENIZATION_FAILED
MMS_LOAD_FAILED
MMS_INFERENCE_FAILED
CTC_ALIGNMENT_FAILED
TOO_MANY_FAILED_CHUNKS
TIMESTAMP_INVALID
ANCHOR_DRIFT
LRC_GENERATION_FAILED
SYLT_EMBED_FAILED
MP3_VALIDATION_FAILED
```

## Phase 3

```text
HOOK_NO_VALID_CANDIDATES
HOOK_REVIEW_REQUIRED
YOUTUBE_AUDIO_FAILED
VIDEO_MATCH_LOW_CONFIDENCE
VIDEO_MATCH_FAILED
VIDEO_SECTION_DOWNLOAD_FAILED
VIDEO_TRIM_FAILED
TRACKING_UNSTABLE
CROP_RENDER_FAILED
AUDIO_8D_FAILED
LOUDNESS_VALIDATION_FAILED
KARAOKE_RENDER_FAILED
ASSEMBLY_FAILED
FINAL_MP4_VALIDATION_FAILED
REEL_JSON_FAILED
FINAL_PROMOTION_FAILED
SOURCE_MODIFIED
```

---

# 91. RETRY POLICY

Not every failure should be retried.

## Retryable

Examples:

```text
network timeouts
transient HTTP failures
temporary GPU OOM with alternate chunk/batch strategy
transient file locks
temporary FFmpeg failure
```

## Non-retryable without intervention

Examples:

```text
missing source LRC
missing source JSON
corrupt MP3
missing YouTube video ID
invalid configuration
```

## Review-worthy

Examples:

```text
low alignment confidence
severe anchor drift
high interpolation rate
video match uncertainty
unstable subject tracking
```

Retry classification must be stored with the error.

---

# 92. LOGGING

Support:

```text
INFO
WARNING
ERROR
DEBUG
```

Every major stage emits an INFO event.

Every retry emits a WARNING.

Every terminal failure emits an ERROR.

Prefer structured JSON event payloads for stage metrics.

Example:

```json
{
  "stage": "ctc_alignment",
  "chunk_index": 7,
  "attempt": 2,
  "device": "cuda",
  "frame_count": 936,
  "token_count": 52,
  "score": 0.74
}
```

---

# 93. SECURITY AND CREDENTIAL HANDLING

Protect:

```text
YT Music auth
cookies.txt
Spotify secrets
environment variables
```

Do not commit credentials.

Do not place secrets in MP3 metadata.

Do not put secrets in provenance JSON.

Log only redacted identifiers where necessary.

---

# 94. SOURCE FILE INTEGRITY

At intake:

```text
hash input MP3
hash input LRC
hash input JSON
```

Before/after any stage that reads protected inputs, the pipeline may recheck hashes where practical.

At final validation:

```text
original hashes == recorded hashes
```

Any change is:

```text
SOURCE_MODIFIED
```

and must block finalization.

---

# 95. FILENAME RULES

Use exact source basename relationships.

Do not fuzzy-match:

```text
.mp3
.lrc
.json
```

Maximum safe filename length remains configurable, with the Phase 1 default target of 180 characters.

Preserve the source basename wherever possible.

For Reel outputs:

```text
<basename>_reel.mp4
<basename>_reel.json
```

---

# 96. FULL CLI DESIGN

## Doctor

```bash
python main.py --doctor
```

## Ingest playlist

```bash
python main.py --ingest
```

## Process next song

```bash
python main.py --next
```

## Process a specific serial

```bash
python main.py --serial 1
```

## Process a specific song/basename

```bash
python main.py --song "SongName"
```

## Resume unfinished work

```bash
python main.py --resume
```

## Retry errors

```bash
python main.py --retry-errors
```

## Force rebuild

```bash
python main.py --song "SongName" --force
```

## Manual hook

```bash
python main.py --manualhook SongName --start 00:02:14.200 --end 00:02:34.800
```

## Inspect hook candidates

```bash
python main.py --inspect-hook SongName
```

## Validate Reel

```bash
python main.py --validate-reel SongName
```

## Inspect song/package state

```bash
python main.py --inspect-song SongName
```

## Clean temporary workspaces

```bash
python main.py --clean-temp
```

---

# 97. OPERATING WORKFLOW FOR A WINDOWS USER

## First installation

1. install Python 3.11+;
2. install FFmpeg/FFprobe;
3. install required Python packages from lock file;
4. configure YT Music authentication if needed;
5. configure Spotify only when enabled;
6. verify CUDA/PyTorch if GPU processing is desired;
7. ensure storage is sufficient;
8. run doctor.

## Initial verification

```bash
python main.py --doctor
```

## Start playlist ingestion

```bash
python main.py --ingest
```

## Process one by one

```bash
python main.py --next
```

Repeat until no eligible pending occurrence remains.

## Inspect state

```bash
python main.py --inspect-song "SongName"
```

## Retry recoverable failures

```bash
python main.py --retry-errors
```

---

# 98. PERFORMANCE STRATEGY

## GPU

Use GPU primarily for:

```text
Demucs
MMS inference where supported
```

Keep tracking primarily on CPU to preserve memory headroom.

## Cache

Cache expensive stage outputs:

```text
Demucs stems
acoustic features
lyric features
word alignment
hook candidates
YouTube audio
match candidates
```

## Storage

Delete large temporary WAV/video files after all dependent stages are checkpointed.

Keep enough diagnostic information to reproduce or inspect failures.

## Memory

Avoid holding the complete source song, all stems, high-resolution video, and all feature arrays simultaneously when unnecessary.

---

# 99. DETERMINISM AND REPRODUCIBILITY

Record:

```text
pipeline version
schema versions
config hash
model names
model revisions
library versions
algorithm versions
random seeds when any
runtime/device
```

The same processing identity should result in reproducible candidate ordering and state decisions within the limits of nondeterministic external services and numerical libraries.

External web data must be recorded because it can change independently of local code.

---

# 100. TESTING STRATEGY

## 100.1 Unit tests

Cover:

- basename matching;
- SHA-256 hashing;
- filename safety;
- LRC parsing;
- Telugu normalization;
- token/word mapping;
- chunk boundary generation;
- CTC timestamp conversion;
- word merge/deduplication;
- anchor drift metrics;
- LRC generation;
- ID3 preservation;
- JSON merge preservation;
- ISRC canonicalization;
- duplicate state logic;
- hook feature calculations;
- hook score calculations;
- hook family clustering;
- context expansion;
- time conversions;
- video match result validation;
- crop geometry;
- lyric collision/safe-zone calculations.

## 100.2 Integration tests

At minimum:

```text
Phase 1 package → Phase 2 package
Phase 2 package → Phase 3 input
word timeline → karaoke
selected hook → source audio query
source audio query → video match
video match → exact section
exact section → crop
crop + local audio → final Reel
final Reel → Reel JSON
```

## 100.3 Failure tests

Simulate:

- missing MP3;
- missing LRC;
- invalid JSON;
- unavailable YT Music item;
- yt-dlp failure;
- Spotify timeout;
- YouTube no-match;
- LRCLIB no-sync;
- Demucs OOM;
- MMS load failure;
- failed chunk;
- anchor drift;
- low hook quality;
- video match low confidence;
- tracking loss;
- FFmpeg failure;
- JSON write failure;
- DB commit failure;
- source modification.

---

# 101. PHASE 1 ACCEPTANCE TESTS

Verify:

### Playlist

- returned order preserved;
- serials permanent;
- repeated tracks stay distinct;
- unavailable items survive ingestion.

### Download

- one complete yt-dlp acquisition;
- MP3 valid;
- info JSON captured;
- thumbnails considered.

### Spotify

- duration-compatible first result selected;
- artwork behavior correct;
- failure does not unexpectedly block according to config.

### Duplicate

- ISRC-only duplicate identity;
- keep-previous preserves old artifacts;
- keep-current is transactional.

### YouTube

- correct query;
- only `lyrics` title exclusion;
- first acceptable result selected.

### Lyrics

- `/api/get` only;
- synchronized only;
- LRC saved when valid.

### Metadata

- required ID3 fields present;
- artwork embedded;
- synchronized lyrics embedded;
- provenance lives in JSON.

### Finalization

- validation before promotion;
- hashes recorded;
- database and filesystem agree.

---

# 102. PHASE 2 ACCEPTANCE TESTS

Verify:

```text
source files unchanged
all original JSON keys preserved
all existing MP3 metadata preserved
LRC parses
MMS loads
CTC alignment works
word start/end monotonicity holds
word durations are plausible
missing/interpolated words are explicit
anchor drift is measured
instrumental gaps are detected
final LRC derives from canonical words
SYLT contains expected word timing
final JSON contains phase2 namespace
```

The supplied sample song is an important regression fixture because its LRC includes 42 timestamp entries, 39 non-empty lyric lines, and two large blank regions.

---

# 103. HOOK ACCEPTANCE TESTS

Verify:

- candidate generation uses multiple families;
- candidates have variable duration;
- phrase boundaries are natural;
- scoring components are stored independently;
- hard filters operate;
- near-duplicate windows cluster together;
- 10–15 distinct finalists are retained when enough valid candidates exist;
- lead-in and tail are considered after core selection;
- final segment has valid word/timing quality.

---

# 104. VIDEO MATCH ACCEPTANCE TESTS

Verify:

- complete YouTube audio used only temporarily;
- query is exact selected source-song segment;
- coarse search finds candidate region;
- fine alignment validates candidate;
- multi-anchor verification agrees;
- confidence is recorded;
- low-confidence results stop rather than guess;
- only required video section is downloaded.

---

# 105. SMART-CROP ACCEPTANCE TESTS

Verify:

- subject remains visible;
- jitter is controlled;
- tracking loss is handled gracefully;
- multi-person switching is stable;
- crop stays inside source bounds;
- lyrics remain in a safe region;
- output is exactly 1080×1920;
- no stretch;
- no black bars.

---

# 106. AUDIO ACCEPTANCE TESTS

Verify:

- final audio originates from local source;
- YouTube audio is reference-only;
- vocals centered;
- bass centered/mono-compatible;
- spatial movement primarily on suitable stems;
- effect is audible but controlled;
- timeline unchanged;
- loudness target within tolerance;
- no clipping.

---

# 107. LYRIC ACCEPTANCE TESTS

Verify:

- rendered words map to canonical timing;
- first lyric respects its exact start;
- word highlights proceed in order;
- Telugu shaping is correct;
- maximum two-line presentation is respected where configured;
- text remains in safe region;
- no word outlives its interval;
- no subtitles appear after Reel end.

---

# 108. FINAL PACKAGE ACCEPTANCE TEST

The package is accepted only if all of the following are true:

```text
Song_reel.mp4 exists
Song_reel.json exists
MP4 decodes
JSON parses
1080×1920 output confirmed
video stream confirmed
audio stream confirmed
audio/video durations agree
canonical lyric timings fit Reel
audio is source-derived
YouTube audio not used as final audio
input hashes unchanged
output hashes recorded
validation.status = good or approved configured equivalent
DB state = FINALIZED
```

---

# 109. MANUAL REVIEW PACKAGE

The operator should be able to inspect a generated song without rerunning it.

Provide a command/UI view containing:

```text
selected hook
hook score breakdown
10–15 finalist list
selected source timeline
YouTube matched timeline
match confidence
crop tracking summary
audio processing summary
lyric word count
validation result
output paths
```

The final Reel JSON is the authoritative machine-readable review record.

---

# 110. MIGRATION / COMPATIBILITY PLAN

## 110.1 Existing Phase 1 packages

They can be imported as song-package inputs provided the required MP3/LRC/JSON contract is satisfied.

## 110.2 Existing Phase 2 packages

Existing word-level packages can enter directly at the Phase 3 stage if their JSON contains a valid canonical Phase 2 word timeline and the selected YouTube video record.

## 110.3 Existing MP3 re-embedding

Provide a dedicated command for cases where only the Phase 2 synchronized lyric frame needs to be regenerated. This must preserve all other MP3 frames.

## 110.4 Database migration

The unified `project.db` migration should import:

```text
Phase 1 playlist entries
Phase 1 song rows
Phase 2 alignment state where available
Phase 3 job/match state where available
```

No input artifact should be mutated solely for migration.

---

# 111. OUT-OF-SCOPE ITEMS THAT REMAIN OUT OF SCOPE

The unified project does not add:

- automatic Instagram publishing;
- Instagram Graph API credentials;
- cloud staging as a requirement;
- Phase 1/2 database dependencies after migration;
- a replacement lyric provider when LRCLIB fails;
- Whisper-first lyric transcription as the primary method;
- fingerprint-evasion processing;
- arbitrary global-offset synchronization.

---

# 112. FUTURE EXTENSION POINTS

The architecture can later add:

- multiple Reel outputs per song;
- manual hook approval UI;
- scene-change intelligence;
- stronger visual semantic ranking;
- OCR-aware visual context;
- improved subject identity models;
- alternative audio-matching algorithms;
- additional language adapters;
- alternate karaoke themes;
- automated thumbnail generation;
- additional publication integrations.

These are not required for the first production version.

---

# 113. IMPLEMENTATION ORDER

The recommended implementation order is:

## Milestone 1 — Unified foundation

Build:

```text
config
logging
hashing
filesystem
project.db
models
state machine
CLI doctor
```

## Milestone 2 — Phase 1 migration

Integrate:

```text
playlist ingest
yt-dlp acquisition
metadata normalization
Spotify
ISRC duplicate logic
YouTube discovery
LRCLIB
artwork
MP3 embedder
song JSON
```

Do not change Phase 1 semantics accidentally during migration.

## Milestone 3 — Shared audio engine

Build:

```text
decode/resample
Demucs
stem validation
activity/energy maps
```

Make it reusable by both alignment and Reel intelligence.

## Milestone 4 — Phase 2

Build:

```text
LRC parser
Telugu normalizer
token mapping
chunker
MMS
CTC aligner
word builder
merge
validation
LRC export
SYLT
phase2 JSON
```

## Milestone 5 — Phase 3 song intelligence

Build:

```text
acoustic analyzer
lyric analyzer
repetition
structure
hook candidates
hook scoring
family clustering
context expansion
```

## Milestone 6 — Video matching

Build:

```text
source query extraction
YouTube audio downloader
coarse matcher
fine matcher
multi-anchor verification
confidence model
section downloader
```

## Milestone 7 — Visual/audio/karaoke rendering

Build:

```text
tracking
smart crop
8D audio
karaoke renderer
assembler
```

## Milestone 8 — End-to-end validation/recovery

Build:

```text
final validators
artifact registry
atomic promotion
reconciliation
resume/retry
manual inspection
```

## Milestone 9 — Full playlist production test

Run the entire playlist one song at a time and inspect:

```text
retention rate
word-sync quality
hook candidate quality
video match quality
crop stability
audio quality
Reel validation
failure/recovery behavior
```

---

# 114. DEFINITION OF DONE FOR THE WHOLE PROJECT

The unified project is production-ready when:

1. A playlist can be ingested without renumbering existing serial identities.
2. Every usable playlist occurrence can be acquired into a retained song package.
3. Duplicate detection obeys the ISRC-only rule.
4. Synchronized LRCLIB lyrics are retained when available.
5. Songs without synced lyrics remain correctly represented but are blocked from Reel generation.
6. The word-level alignment stage uses the supplied lyric reference and CTC forced alignment rather than replacing the transcript with ASR output.
7. The source MP3/LRC/JSON are never overwritten.
8. Original JSON content survives Phase 2.
9. Original MP3 metadata survives Phase 2 except for the explicitly owned synchronized lyric update.
10. A canonical word-level timeline exists for Reel-ready songs.
11. Hook analysis sees the whole song rather than a fixed search window.
12. The hook engine generates multiple candidate families.
13. Near-duplicate candidates are clustered.
14. 10–15 distinct finalists can be inspected.
15. Lead-in/tail context is optimized after hook-core selection.
16. The selected source-song segment becomes the master Reel timeline.
17. The chosen YouTube video is the Phase 1 selected video, not an unrelated second search.
18. YouTube audio is downloaded for localization only.
19. The audio matcher finds the selected segment in the complete reference audio.
20. Low-confidence matches fail safely rather than guessing.
21. Only the necessary video section is downloaded after a match is accepted.
22. The final video is exactly 1080×1920.
23. Subject tracking is stateful and temporally stable.
24. Final Reel audio comes from the local source song.
25. 8D/spatial processing preserves timeline.
26. Karaoke uses canonical word timing.
27. Telugu shaping and wrapping are validated.
28. Audio/video/lyrics pass cross-output synchronization checks.
29. Reel provenance JSON contains enough detail to reconstruct all major decisions.
30. Finalization is atomic and idempotent.
31. A failed song does not halt the playlist unless explicitly configured to do so.
32. A completed song can be skipped on subsequent runs using processing identity.
33. Every expensive stage is checkpointed and resumable.
34. Protected source hashes are verified.
35. The final user-facing deliverable is a validated MP4 + Reel JSON per Reel-ready song.

---

# 115. FINAL ONE-LINE ARCHITECTURE

```text
YouTube Music playlist → permanent playlist identity → one complete YT Music source acquisition → metadata/Spotify/ISRC/YouTube/LRCLIB enrichment → retained song package → one shared Demucs separation → Telugu LRC-anchored CTC word alignment → canonical word timeline → full-song acoustic + lyrical structure intelligence → hook candidates → transparent scoring → family clustering → 10–15 distinct finalists → lead-in/tail expansion → final source-song Reel timeline → exact local query extraction → selected YouTube video audio-only acquisition → coarse/fine/multi-anchor audio matching → exact video timeline → minimal video-section download → stateful smart 9:16 crop → timeline-preserving local-source 8D audio → canonical word-level Telugu karaoke → 1080×1920 final assembly → cross-output validation → provenance JSON → atomic finalization → next song.
```

---

# 116. ENGINE OWNERSHIP MATRIX

| Engine | Reads | Produces | Downstream Consumers |
|---|---|---|---|
| Playlist ingest | YT Music playlist | playlist entries | acquisition worker |
| Acquisition | YT Music / yt-dlp | source MP3/info/thumbnails | metadata |
| Metadata | source info + Spotify + video + LRCLIB | normalized song model | song package |
| Duplicate engine | normalized ISRC | duplicate decision | package finalization |
| Song package | normalized song + lyrics + artwork | MP3/LRC/JSON | Phase 2 |
| Shared audio | source MP3 | stems/activity/features | Phase 2 + Phase 3 |
| Word alignment | LRC + vocals/original mix + MMS | canonical word timeline | LRC/SYLT/JSON + Reel |
| Song intelligence | stems + word timeline | acoustic/lyric/structure maps | hook engine |
| Hook engine | song maps | candidates/families/finalists/selection | query extraction |
| Video matcher | query audio + YouTube audio | match timestamps/confidence | video grabber |
| Video renderer | exact video section | 9:16 video | assembler |
| 8D engine | local song stems | spatial Reel audio | assembler |
| Karaoke engine | canonical words + crop safe zones | lyric render | assembler |
| Assembler | video + audio + karaoke | MP4 | validator |
| Validator | all final artifacts | validation result | finalizer |
| Provenance | database + artifacts + metrics | Reel JSON | operator/manual upload |
| Recovery | checkpoints + database + files | resumed stage | pipeline |

---

# 117. CRITICAL INVARIANTS — ABSOLUTE MUST-DO

```text
1. Input packages are immutable.
2. Exact basenames define MP3/LRC/JSON package relationships.
3. Playlist occurrence serials are permanent.
4. ISRC is the sole duplicate identifier when valid.
5. Spotify is enrichment, not final audio.
6. Selected Phase 1 YouTube video is the Phase 3 video source.
7. LRCLIB uses GET /api/get and synchronized lyrics only.
8. Phase 2 never replaces reference lyrics with ASR transcription.
9. MMS provides acoustic evidence; CTC aligns the known reference transcript.
10. Word records retain start and end time.
11. Original MP3 metadata is preserved surgically.
12. Original JSON is preserved and extended, not reconstructed.
13. One canonical word timeline drives all downstream lyric timing.
14. Demucs is shared across Phase 2 and Phase 3.
15. Hook discovery is whole-song and content-driven.
16. Hook candidates are diversified into distinct families.
17. Context is added after hook-core selection.
18. Final Reel audio comes from the local song.
19. YouTube audio is reference-only.
20. Video matching is segment localization, not blind global offset.
21. Low-confidence video matches are never guessed.
22. Only the required video section is downloaded.
23. Final video is exactly 1080×1920.
24. Smart crop is stateful and temporally smoothed.
25. Lyrics are safe-zone aware and subject-aware.
26. 8D processing preserves the timeline.
27. Finalization occurs only after complete validation.
28. Every final decision is provenance-recorded.
29. Expensive stages are checkpointed.
30. Failed songs do not corrupt the playlist queue.
31. Instagram publishing is manual.
```

---

# 118. SOURCE COVERAGE INDEX

The detailed source documents are preserved verbatim in the appendices below. This guarantees that historical/current wording, detailed field inventories, SQL schema fragments, command details, acceptance criteria, and implementation notes are not silently lost while building the unified architecture.

The integrated sections above incorporate the responsibilities of the source headings, while the appendices preserve the complete original documents for exact reference.

### Phase 1 coverage domains

```text
Executive summary
Current authoritative rules
Playlist identity
Playlist ingestion
Source download
Spotify enrichment
ISRC duplicate detection
Duplicate resolution
YouTube music-video discovery
LRCLIB lyrics
Artwork
MP3 metadata
Sidecar JSON
End-to-end architecture
Project directory
Runtime dependencies
Configuration
Playlist database
Songs database
Database invariants
State machine
Working directory
yt-dlp acquisition
Source validation
Metadata normalization
Metadata precedence
Spotify detailed plan
ISRC detailed plan
Transactional duplicate safety
YouTube search
LRCLIB detailed plan
Artwork detailed plan
MP3 metadata contract
Sidecar contract
Filename rules
Finalization order
Validation contract
Hashing
Error handling
Recovery/restart
CLI
Logging
Security
Module responsibilities
One-song data flow
Responsibility matrix
Duplicate matrix
Lyrics matrix
Artwork matrix
Testing
Acceptance criteria
Design decisions
Migration/compatibility
Existing-MP3 re-embedding
Windows operation
Examples
API inventory
Release gates
Historical appendix
Future-change principles
Final release checklist
```

### Phase 2 coverage domains

```text
Executive definition
Non-negotiable requirements
Real sample input contract
Objectives/non-objectives
End-to-end pipeline
Directory structure
File matching
Source fingerprinting
Identity model
JSON handling
Phase 2 JSON schema
Input validation
Audio duration consistency
Demucs vocal isolation
Dual-audio alignment
Vocal activity analysis
VAD meaning
LRC gap model
Telugu normalization
Original word record
Unsupported text
Normalization versioning
LRC anchor scaffold
Anchor-aware chunking
Chunk duration policy
Chunk priority
Overlapping context
Chunk database fields
MMS initialization
Adapter requirement
Model cache
Model loading strategy
MMS input/output
CTC rationale
Reference preparation
Token mapping
CTC trellis/alignment
Token timestamps
Word spans
Word score
Low-confidence words
Missing words
Interpolation
Chunk retries
Overlap deduplication
Global merge
Line reconstruction
Anchor comparison
Anchor drift
Instrumental inference
Instrumental outputs
Sample gap handling
Canonical word/line records
Final LRC
Timestamp precision
Blank markers
MP3 strategy
Metadata preservation
Existing SYLT preservation
Phase 2 SYLT ownership/replacement
Post-embed validation
JSON output
Quality metrics
Timing/order/duration validation
Output promotion
State machine
Resumability
Error handling
Logging
Performance
Determinism
Output naming
Future extensions
Final architectural summary
Definition of done
```

### Phase 3 coverage domains

```text
Executive definition
Architecture invariants
Standalone file contract
Input requirements
Input fingerprinting
Directory structure
Dependencies
Configuration
Batch scanner
Package validation
Audio preparation
Demucs
Acoustic features
Lyric analysis
Song structure
Hook candidates
Hook scoring
Hard filters
Hook family clustering
Distinct finalists
Context expansion
Final Reel scoring
Selected hook output
Manual hook mode
Source audio extraction
YouTube source identification
YouTube audio acquisition
Audio matching problem
Multi-stage matcher
Match failure policy
Match result
Video section download
Exact trim
Smart crop
Subject priority
Multi-person tracking
Identity
Composition
Prediction
Smoothing
9:16 geometry
Vertical placement
Lyric-aware crop
No-subject handling
Video rendering
Final audio architecture
8D audio
Loudness validation
Canonical lyric timeline
Karaoke rendering
Typography
Centered layout
Subject-aware lyric placement
Line grouping
Word timing
Visual palette
Collision validation
Final assembly
Cross-output validation
Final output package
Reel JSON
Source JSON section
Processing section
Hook JSON
Video source JSON
Match JSON
Video render JSON
Audio JSON
Lyrics JSON
Output JSON
Validation JSON
Database design
State machine
Resumability
Atomic finalization
Idempotency
Error codes
Error handling
Logging
Do-not-do list
Must-do list
CLI
Tests
Acceptance tests
Manual review
Performance
Determinism
Naming
Future extensions
Architectural summary
End-to-end reference flow
Final design principles
Definition of done
```

---

# 119. INTEGRATION CHANGE LOG — DECISIONS MADE DURING DISCUSSION

## Decision 1 — These are one product, not three products

The three pipelines are unified under one playlist → song → word-timeline → Reel lifecycle.

## Decision 2 — Preserve modular responsibilities

Do not create a tangled single module. Keep internal engines separated while one master pipeline orchestrates them.

## Decision 3 — One operational database

Use one `project.db` while preserving the source schemas and semantics required for compatibility.

## Decision 4 — One shared Demucs run

Use the same stem outputs for word-sync, song intelligence, and final spatial audio.

## Decision 5 — Phase 1 can succeed while the Reel is blocked

No synced lyric or no selected YouTube video does not destroy the retained song. It only prevents Reel generation.

## Decision 6 — The Phase 2 word-level package is the canonical Phase 3 input

This creates a clean immutable file boundary.

## Decision 7 — One canonical timing model

The word timeline is the source of truth for Phase 2 exports and Phase 3 karaoke.

## Decision 8 — Hook selection occurs entirely before video acquisition

The exact source-song timeline must be known before the YouTube audio matching problem is solved.

## Decision 9 — YouTube is localized, not substituted

YouTube provides visual timing reference. The local song remains final audio.

## Decision 10 — Every song runs one-by-one by default

This is the primary operational mode for reliability and resource control.

---

# 120. FINAL PROJECT SUCCESS DEFINITION

The project succeeds when a user can give the system a YouTube Music playlist and the system can deterministically process each eligible song through:

```text
playlist occurrence
→ retained song
→ enriched metadata
→ synchronized lyrics
→ word-level Telugu timing
→ musical/lyrical analysis
→ hook discovery
→ final hook/context selection
→ exact YouTube visual localization
→ stateful portrait crop
→ local-source spatial audio
→ word-level Telugu karaoke
→ validated Reel
```

while preserving all original source information, maintaining traceability, failing safely when evidence is insufficient, and producing a final downloadable Reel artifact for each song that successfully passes the gates.

---

# APPENDIX A — PHASE 1 ORIGINAL SPECIFICATION

The complete Phase 1 source document follows verbatim below. It is retained as a requirement-preservation appendix so that no source-level detail, field, compatibility rule, historical implementation note, example, or acceptance criterion is lost from the unified project plan.

# PHASE 1 — YouTube Music Playlist Downloader & Enricher

## Complete Ultra-Detailed Project Plan — Current Authoritative Build

**Status:** Current consolidated implementation plan

**Purpose:** This document consolidates the original Phase 1 specification and every subsequent project change discussed during implementation. The **Current Authoritative Specification** sections describe what the implementation is intended to do now. The **Historical Original Specification** appendix preserves the original planning document verbatim so no original requirement is lost. Where later requirements changed an earlier rule, the current rule explicitly takes precedence and the superseded rule is identified.

**Generated:** 2026-09-27

---

# 1. Executive Summary

This project is a standalone Python pipeline that ingests one YouTube Music playlist, assigns every playlist occurrence a permanent serial number, downloads usable YT Music source audio, enriches the song with optional Spotify catalog information, locates one YouTube music-video result using the project's deterministic search rule, obtains only synchronized lyrics from LRCLIB through `GET /api/get`, selects high-quality artwork, writes a concise and player-compatible final ID3 metadata set, embeds synchronized lyrics, creates a same-basename detailed JSON sidecar, validates and hashes the final MP3, and commits the resulting retained-song record into SQLite.

The architecture deliberately separates:

1. **Playlist identity** — permanent serial + playlist position in `playlist.db`.
2. **Retained song identity** — song row in `songs.db`, with **ISRC as the only duplicate identifier** when an ISRC exists.
3. **Source metadata** — detailed YT Music/yt-dlp information.
4. **Catalog enrichment** — optional Spotify information and Spotify artwork.
5. **Video enrichment** — selected YouTube music-video ID/title/URL and core facts.
6. **Lyrics enrichment** — LRCLIB synchronized lyrics only.
7. **Player-facing MP3 metadata** — concise standard ID3 + durable custom identifiers + artwork + lyrics.
8. **Full detailed provenance** — same-basename JSON sidecar containing detailed source/API fields, raw JSON, selection information, artwork provenance, lyric response/matching details, and file hashes.

The current implementation intentionally does **not** dump raw source descriptions, age-limit information, channel internals, downloader internals, or raw API blobs into the main MP3 metadata. Those details belong in the JSON sidecar.

---

# 2. Current Authoritative Rules

These rules are locked for the current build unless explicitly changed in a future revision.

## 2.1 Playlist identity

- Every playlist occurrence receives one permanent integer serial number.
- Serial numbers are assigned according to the order returned by YTMusic playlist ingestion.
- Serial numbers never change.
- Serial numbers are never reused.
- Repeated tracks in the playlist remain separate playlist occurrences.
- The permanent serial is the stable link between a playlist occurrence and its retained file/record.

## 2.2 Playlist ingestion

- The complete playlist is read through `ytmusicapi`.
- Returned playlist order is authoritative.
- No alphabetical, artist, duration, popularity, ISRC, or other sorting is performed.
- An unavailable item (`videoId=None`, `isAvailable=False`) must not crash ingestion.
- An unavailable entry is preserved with its serial and position and recorded as `error` until it can be retried.
- When a previously unavailable occurrence later becomes usable, the existing serial is reused rather than assigning a new serial.

## 2.3 Source download

- The actual song audio comes from the YT Music source associated with the playlist occurrence.
- One complete initial `yt-dlp` acquisition is used for audio, source `info.json`, and thumbnails.
- `--add-metadata` is not used by the initial acquisition.
- FFmpeg/FFprobe are required.
- A supported JavaScript runtime may be required by the installed yt-dlp version for some YouTube extraction paths.

## 2.4 Spotify enrichment

- Spotify enrichment is optional and controlled by configuration.
- Client Credentials authentication is used.
- Credentials may be supplied in `config.json` or via `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` environment variables.
- Search query is exactly `title + album`.
- Returned Spotify result order is preserved.
- The first returned result within the configured duration tolerance of the actual downloaded YT Music audio duration is selected.
- No Spotify candidate scoring system is used.
- No Spotify result ranking beyond returned order + duration match is introduced.
- Spotify can enrich core music metadata.
- Spotify ISRC is preferred as the canonical ISRC when a Spotify track is successfully matched and supplies a valid ISRC.
- If Spotify does not supply a valid ISRC, valid source ISRC from yt-dlp may be used.
- ISRC is metadata and the sole duplicate identifier; it is not used for any other matching heuristic.
- Spotify artwork uses the largest album image returned by Spotify.
- Spotify artwork bytes are preserved byte-for-byte and are not cropped, resized, recompressed, sharpened, recolored, or otherwise transformed.
- If Spotify artwork is unavailable/invalid for the intended use, the pipeline may fall back to the YT Music artwork pipeline.

## 2.5 ISRC duplicate detection

- ISRC is the **only** retained-song duplicate identifier.
- Canonical ISRC is normalized by removing spaces and hyphens and uppercasing alphanumeric content, then validated against the standard 12-character form.
- Invalid ISRC is treated as missing.
- Missing/invalid ISRC means no duplicate lookup is performed.
- No title, artist, album, duration, YT Music ID, YouTube ID, filename, audio hash, fuzzy similarity, or composite metadata matching is permitted.
- When a duplicate exists, the operator explicitly chooses `keep_previous` or `keep_current`.

## 2.6 Duplicate resolution

### Keep previous

- The existing retained song is untouched.
- The previous MP3/LRC/JSON remains untouched.
- The current temporary acquisition is discarded.
- The current playlist occurrence is marked `duplicate`.
- No current `songs.db` row is created.

### Keep current

- The current replacement is completely built and validated before old physical artifacts are destroyed.
- The old retained row and current retained row transition is performed transactionally.
- The old playlist serial is returned to `pending`.
- The current playlist serial becomes `completed`.
- The old physical artifacts are cleaned after the database commit.
- Playlist serial identities never change.

## 2.7 YouTube music-video discovery

- Search query is built as `{title} {album} official video song` using normalized/current song metadata.
- Search results are consumed in returned order.
- A result is skipped only when its title contains the word `lyrics`, case-insensitively.
- The first remaining result is immediately selected.
- No result score, confidence value, ranking, weighted heuristic, duration comparison, channel comparison, popularity comparison, or manual weighting is performed by the application.
- If every fetched result contains `lyrics`, there is no selected video.
- Lack of an acceptable YouTube result does not fail the song.

## 2.8 LRCLIB lyrics

- Only `GET /api/get` is permitted.
- `/api/search` is never called.
- Lookup uses the current song metadata and duration.
- Only valid synchronized lyrics are accepted.
- Plain-only lyrics are not downloaded as `.lrc` and do not count as synchronized lyrics.
- Synced lyrics are saved alongside the MP3 as `.lrc`.
- Synced lyrics are also embedded into the MP3 using synchronized lyrics metadata plus a compatibility plain-text lyrics projection.
- Songs with synced lyrics are stored under `songs/synced_lyrics/`.
- Songs without synced lyrics are stored under `songs/no_synced_lyrics/`.
- Unsynced songs do not receive an `.lrc` file.

## 2.9 Artwork

- Spotify is the preferred final artwork provider when Spotify enrichment is enabled, a track is matched, and usable album artwork is available.
- The largest Spotify image returned is selected.
- Spotify image bytes are preserved unchanged.
- For YT Music fallback artwork, all useful yt-dlp thumbnail variants may be considered and a page OpenGraph image may be inspected.
- The YT Music fallback prefers a valid square candidate and can normalize a non-square fallback to square JPEG.
- Artwork is embedded as front cover APIC.

## 2.10 MP3 metadata

The MP3 is intentionally concise and player-facing. It contains:

- Title
- Track artist
- Album artist
- Album
- Release date
- Track/disc number when known
- Genre when known
- Composer when known
- Publisher/label when known
- Copyright when known
- Language when known
- BPM when known
- Compilation when known
- Actual MP3 duration
- Canonical ISRC when available
- YT Music source video ID and URL
- Selected YouTube music-video ID, URL and title
- Spotify track ID, album ID, URL and ISRC when matched/available
- Front-cover artwork
- Synchronized lyrics
- A small durable set of application metadata via TXXX/UFID/WXXX

The MP3 does **not** contain the large raw API blobs or verbose source/debug information.

## 2.11 Sidecar JSON

Every finalized MP3 gets a same-basename `.json` sidecar.

The JSON is the detailed record and can contain:

- Complete normalized metadata
- Playlist identity
- YT Music playlist-item JSON
- yt-dlp source `info.json`
- Spotify search/match information
- Spotify track JSON
- Spotify album JSON
- Spotify artwork provenance
- Selected YouTube search information
- Selected YouTube information JSON
- LRCLIB response/matching information
- Downloaded synchronized lyric text
- Artwork provenance and hashes
- MP3 file size/hash
- LRC path/status
- Duplicate decision information
- Build/schema versions

---

# 3. End-to-End Architecture

```text
YouTube Music Playlist
        |
        v
YTMusic API ingestion
        |
        +--> preserve API order
        +--> assign/reuse permanent serials
        |
        v
playlist.db
        |
        v
next pending playlist occurrence
        |
        v
Create temp/{serial}/
        |
        v
ONE yt-dlp acquisition
  |-- master.mp3
  |-- master.info.json
  `-- thumbnails
        |
        +--> source validation
        |
        +--> metadata normalization
        |
        +--> optional Spotify search
        |       |
        |       +--> first duration match
        |       `--> optional largest Spotify artwork
        |
        +--> canonical ISRC determination
        |       |
        |       `--> ISRC-only duplicate lookup
        |                |
        |                +--> unique
        |                |
        |                `--> user decision
        |                         |
        |                         +--> keep previous
        |                         `--> keep current
        |
        +--> YouTube video search
        |       |
        |       `--> first result not containing 'lyrics'
        |
        +--> LRCLIB GET /api/get
        |       |
        |       `--> synchronized lyrics only
        |
        +--> artwork selection
        |
        v
final metadata model
        |
        +-------------------+
        |                   |
        v                   v
concise MP3 tags       detailed sidecar JSON
        |                   |
        +-- APIC             +-- raw source JSON
        +-- SYLT             +-- Spotify JSON
        +-- USLT             +-- YouTube JSON
        +-- standard ID3     +-- LRCLIB data
        +-- TXXX             +-- provenance
        +-- UFID             +-- hashes
        +-- WXXX             +-- file information
        |
        v
validate final MP3
        |
        v
SHA-256
        |
        v
atomic promotion
        |
        +--> songs/.../*.mp3
        +--> songs/.../*.lrc (synced only)
        +--> songs/.../*.json
        |
        v
transactional SQLite commit
        |
        +--> songs.db
        `--> playlist.db status=completed
```

---

# 4. Project Directory

```text
phase1_project/
├── main.py
├── config.json
├── cookies.txt
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
├── README.md
├── BUILD_INFO.md
├── CHANGELOG.md
├── .gitignore
│
├── src/
│   ├── __init__.py
│   ├── db_playlist.py
│   ├── db_songs.py
│   ├── playlist_ingest.py
│   ├── downloader.py
│   ├── metadata.py
│   ├── duplicate_checker.py
│   ├── spotify.py
│   ├── youtube_finder.py
│   ├── lrclib.py
│   ├── artwork.py
│   ├── embedder.py
│   ├── validator.py
│   ├── hashing.py
│   ├── sidecar.py
│   └── pipeline.py
│
├── scripts/
│   ├── clean_runtime.py
│   ├── init_db.py
│   ├── inspect_mp3.py
│   └── reembed_existing.py
│
├── tests/
│   ├── test_phase1.py
│   └── fixtures/
│       ├── sample.mp3
│       └── sample.jpg
│
├── docs/
│   ├── ACTIVE_SPEC.md
│   ├── ACTIVE_IMPLEMENTATION_RULES.md
│   ├── CURRENT_IMPLEMENTATION_RULES.md
│   ├── DUPLICATE_ISRC.md
│   ├── METADATA_EMBEDDING.md
│   ├── ENHANCEMENTS_SPOTIFY_LRCLIB.md
│   ├── ARTWORK_FIX.md
│   ├── ARCHITECTURE.md
│   ├── TEST_MATRIX.md
│   ├── FINAL_AUDIT*.md
│   ├── HISTORICAL_PHASE1_SPEC.md
│   ├── project_spec.md
│   ├── implementation_analysis.md
│   └── runtime_notes.md
│
├── songs/
│   ├── synced_lyrics/
│   │   ├── <name>.mp3
│   │   ├── <name>.lrc
│   │   └── <name>.json
│   └── no_synced_lyrics/
│       ├── <name>.mp3
│       └── <name>.json
│
├── temp/
├── logs/
│   └── phase1.log
└── db/
    ├── playlist.db
    └── songs.db
```

---

# 5. Runtime Dependencies

## 5.1 Python

- Python 3.11+.

## 5.2 Python packages

The project requires these functional dependencies:

- `ytmusicapi`
- `yt-dlp`
- `mutagen`
- `requests`
- `Pillow`

Development/testing dependencies include pytest tooling.

## 5.3 External binaries

- FFmpeg
- FFprobe
- A supported JavaScript runtime for yt-dlp where the installed yt-dlp extraction path requires it.

## 5.4 Runtime doctor

`python main.py --doctor` checks the configuration/environment and reports missing runtime components before normal processing.

---

# 6. Configuration

The configuration controls integration availability and operational limits but must not silently change architectural rules.

Current example:

```json
{
  "ytmusic_playlist_id": "YOUR_PLAYLIST_ID",
  "ytmusic_auth_file": null,
  "paths": {
    "songs": "songs",
    "songs_with_synced_lyrics": "songs/synced_lyrics",
    "songs_without_synced_lyrics": "songs/no_synced_lyrics",
    "temp": "temp",
    "database": "db",
    "logs": "logs"
  },
  "download": {
    "audio_format": "mp3",
    "audio_quality": "0",
    "write_info_json": true,
    "write_thumbnail": true,
    "convert_thumbnail": "jpg",
    "write_all_thumbnails": true
  },
  "youtube_video_search": {
    "results_to_fetch": 10,
    "skip_title_keyword": "lyrics"
  },
  "spotify": {
    "enabled": false,
    "client_id": "",
    "client_secret": "",
    "use_env": true,
    "market": "IN",
    "search_limit": 10,
    "duration_tolerance_seconds": 2,
    "timeout_seconds": 30,
    "max_retries": 3,
    "fail_on_error": false,
    "artwork": {
      "enabled": true,
      "timeout_seconds": 30,
      "fail_on_error": false
    }
  },
  "lyrics": {
    "enabled": true,
    "timeout_seconds": 30,
    "max_retries": 3,
    "request_delay_seconds": 0.5,
    "user_agent": "Phase1AudioDownloader/1.0 (https://github.com/your-user/your-repo)",
    "fail_on_error": false,
    "endpoint": "/api/get",
    "download_only_synced": true,
    "embed_synced": true,
    "embed_plain_fallback": true
  },
  "retry": {
    "max_attempts": 3,
    "backoff_seconds": 2
  },
  "yt_dlp_binary": "yt-dlp",
  "cookies_file": "cookies.txt",
  "ffmpeg_location": null,
  "js_runtime": "auto",
  "js_runtime_path": null,
  "socket_timeout_seconds": 30,
  "download_timeout_seconds": 3600,
  "youtube_search_timeout_seconds": 120,
  "youtube_metadata_timeout_seconds": 120,
  "max_description_chars": 0,
  "artwork": {
    "og_image_enabled": true,
    "og_image_timeout_seconds": 30,
    "force_square": true,
    "max_dimension": 1200,
    "jpeg_quality": 98
  },
  "filesystem": {
    "max_filename_length": 180
  },
  "duplicate_detection": {
    "enabled": true,
    "identifier": "isrc",
    "on_duplicate": "prompt"
  }
}

```

## 6.1 Configuration semantics

### YouTube Music

- `ytmusic_playlist_id`: playlist to ingest.
- `ytmusic_auth_file`: optional authentication file.

### Paths

- `songs`: root song directory.
- `songs_with_synced_lyrics`: final synced output directory.
- `songs_without_synced_lyrics`: final non-synced output directory.
- `temp`: per-entry work area.
- `database`: SQLite directory.
- `logs`: application logs.

### Download

- `audio_format`: final audio format (`mp3`).
- `audio_quality`: yt-dlp audio quality selection.
- `write_info_json`: source info JSON must be written.
- `write_thumbnail`: artwork acquisition must be attempted.
- `convert_thumbnail`: YT Music fallback thumbnail conversion format.
- `write_all_thumbnails`: collect all available yt-dlp thumbnail variants for selection.

### YouTube video search

- `results_to_fetch`: maximum results fetched.
- `skip_title_keyword`: title exclusion keyword; current value `lyrics`.

### Spotify

- `enabled`: enable/disable enrichment.
- `client_id`, `client_secret`: credentials.
- `use_env`: permit environment-variable credential overrides.
- `market`: Spotify market used for search/catalog requests.
- `search_limit`: number of search results requested.
- `duration_tolerance_seconds`: maximum allowed duration difference.
- request timeout/retry controls.
- `artwork.enabled`: enable Spotify artwork.
- artwork timeout/failure behavior.

### Lyrics

- `enabled`: enable LRCLIB integration.
- `timeout_seconds`: HTTP timeout.
- `max_retries`: retry count.
- `request_delay_seconds`: throttle between calls.
- `user_agent`: HTTP user-agent.
- `fail_on_error`: whether LRCLIB failure should fail the song.
- `endpoint`: must remain `/api/get`.
- `download_only_synced`: synchronized lyrics only.
- `embed_synced`: embed synchronized lyrics.
- `embed_plain_fallback`: current compatibility behavior; no unsynced `.lrc` is created.

### Retry

- `max_attempts`: pipeline attempts.
- `backoff_seconds`: delay between attempts.

### yt-dlp / network

- `yt_dlp_binary`: command/executable.
- `cookies_file`: optional cookies.
- `ffmpeg_location`: optional explicit FFmpeg location.
- `js_runtime`, `js_runtime_path`: JavaScript runtime selection.
- socket/download/search/metadata timeouts.

### Artwork

- `og_image_enabled`: inspect page OpenGraph image for YT Music fallback.
- `og_image_timeout_seconds`: OG request timeout.
- `force_square`: square YT Music fallback normalization.
- `max_dimension`: maximum normalized YT Music fallback size.
- `jpeg_quality`: YT Music fallback JPEG quality.

### Filesystem

- `max_filename_length`: maximum safe final filename length.

### Duplicate detection

- `enabled`: enable ISRC duplicate handling.
- `identifier`: must be `isrc` for current architecture.
- `on_duplicate`: `prompt` for interactive resolution.

---

# 7. Playlist Ingestion

## 7.1 Read configuration

Load `ytmusic_playlist_id` and optional YTMusic authentication.

## 7.2 Create client

Create a `ytmusicapi.YTMusic` client.

## 7.3 Retrieve complete playlist

The playlist ingestion layer requests the complete playlist according to the current ytmusicapi interface and processes returned items in order.

## 7.4 Track extraction

For normal entries, extract:

- `videoId`
- title
- artists
- album
- duration
- availability
- original playlist-item JSON

## 7.5 Unavailable entries

An item such as:

```json
{
  "videoId": null,
  "title": "Nuvvu Navvukuntu",
  "isAvailable": false
}
```

is not an ingestion-fatal error.

The item is preserved. The application stores the metadata that exists, keeps the permanent serial, and records an `error` state explaining that the entry currently has no usable source video ID.

No fake `videoId` is generated.

## 7.6 Existing entries

When the same usable playlist occurrence is ingested again:

- preserve its serial,
- preserve its historical status when applicable,
- refresh source fields as appropriate,
- never recycle serials.

## 7.7 New entries

Allocate the next never-used serial after the existing maximum.

## 7.8 Ingestion order

Initial serial assignment follows API return order. Processing of pending entries follows:

```sql
ORDER BY playlist_position ASC, serial_number ASC
LIMIT 1
```

---

# 8. Playlist Database — Current Schema

`playlist.db` answers: **which playlist occurrences exist and what state are they in?**

Current table:

```sql
CREATE TABLE playlist_entries (
    serial_number INTEGER PRIMARY KEY,
    playlist_position INTEGER NOT NULL,
    ytm_playlist_id TEXT,
    ytm_video_id TEXT,
    ytm_url TEXT,
    title TEXT NOT NULL,
    artist TEXT NOT NULL,
    album TEXT,
    duration INTEGER,
    ytm_playlist_item_json TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'completed', 'duplicate', 'error')),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Indexes:

```sql
CREATE INDEX idx_playlist_status_position
ON playlist_entries(status, playlist_position, serial_number);

CREATE INDEX idx_playlist_video_id
ON playlist_entries(ytm_video_id);
```

## 8.1 Status meanings

### pending
Entry is ready to be processed.

### completed
Entry currently owns the retained song row/file.

### duplicate
Entry was processed and intentionally did not retain its own song because its ISRC duplicated an existing retained song and the operator chose to keep the previous song.

### error
The entry cannot currently be processed successfully, for example because the source is unavailable or an unrecoverable processing error occurred.

---

# 9. Songs Database — Current Schema

`songs.db` answers: **which playlist entries currently own retained songs, and what normalized/file/enrichment metadata belongs to those songs?**

Current table:

```sql
CREATE TABLE songs (
    serial_number INTEGER PRIMARY KEY,
    ytm_playlist_id TEXT,
    title TEXT NOT NULL,
    title_original TEXT,
    primary_artist TEXT,
    artist TEXT,
    artists_json TEXT,
    album TEXT,
    album_artist TEXT,
    isrc TEXT,
    track_number TEXT,
    disc_number TEXT,
    release_date TEXT,
    release_date_source TEXT,
    upload_date TEXT,
    upload_timestamp INTEGER,
    release_timestamp INTEGER,
    modified_date TEXT,
    modified_timestamp INTEGER,
    description TEXT,
    genre TEXT,
    composer TEXT,
    publisher TEXT,
    copyright TEXT,
    license TEXT,
    comment TEXT,
    language TEXT,
    bpm INTEGER,
    compilation INTEGER,
    encoder TEXT,
    duration INTEGER,
    source_duration INTEGER,
    source_ext TEXT,
    source_container TEXT,
    source_codec TEXT,
    source_format_id TEXT,
    source_format_note TEXT,
    source_bitrate INTEGER,
    source_sample_rate INTEGER,
    source_channels INTEGER,
    source_filesize INTEGER,
    source_filesize_approx INTEGER,
    source_language TEXT,
    source_video_id TEXT,
    source_webpage_url TEXT,
    source_original_url TEXT,
    source_display_id TEXT,
    source_webpage_url_basename TEXT,
    source_webpage_url_domain TEXT,
    source_extractor TEXT,
    source_extractor_key TEXT,
    source_channel TEXT,
    source_channel_id TEXT,
    source_channel_url TEXT,
    source_channel_follower_count INTEGER,
    source_channel_is_verified INTEGER,
    source_uploader TEXT,
    source_uploader_id TEXT,
    source_uploader_url TEXT,
    source_views INTEGER,
    source_location TEXT,
    source_availability TEXT,
    source_age_limit INTEGER,
    source_live_status TEXT,
    source_media_type TEXT,
    source_thumbnail TEXT,
    source_thumbnails_json TEXT,
    source_categories_json TEXT,
    source_tags_json TEXT,
    source_playlist TEXT,
    source_playlist_id TEXT,
    source_playlist_count INTEGER,
    source_playlist_index INTEGER,
    source_playlist_uploader TEXT,
    source_playlist_uploader_id TEXT,
    source_playlist_channel TEXT,
    source_playlist_channel_id TEXT,
    source_playlist_webpage_url TEXT,
    ytm_video_id TEXT,
    ytm_url TEXT,
    ytm_playlist_item_json TEXT,
    source_info_json TEXT NOT NULL,
    mp3_path TEXT NOT NULL,
    mp3_size INTEGER,
    mp3_sha256 TEXT,
    yt_video_id TEXT,
    yt_video_url TEXT,
    yt_video_title TEXT,
    yt_video_fulltitle TEXT,
    yt_video_alt_title TEXT,
    yt_video_channel TEXT,
    yt_video_channel_id TEXT,
    yt_video_uploader TEXT,
    yt_video_uploader_id TEXT,
    yt_video_upload_date TEXT,
    yt_video_timestamp INTEGER,
    yt_video_release_date TEXT,
    yt_video_release_timestamp INTEGER,
    yt_video_duration INTEGER,
    yt_video_views INTEGER,
    yt_video_likes INTEGER,
    yt_video_comments INTEGER,
    yt_video_thumbnail TEXT,
    yt_video_description TEXT,
    yt_video_categories_json TEXT,
    yt_video_tags_json TEXT,
    yt_video_extractor TEXT,
    yt_video_extractor_key TEXT,
    yt_video_info_json TEXT,
    yt_video_search_query TEXT,
    yt_video_search_result_index INTEGER,
    yt_video_search_results_fetched INTEGER,
    yt_video_match_method TEXT,
    artwork_source_url TEXT,
    artwork_width INTEGER,
    artwork_height INTEGER,
    artwork_path TEXT,
    artwork_provider TEXT,
    metadata_json_path TEXT,
    spotify_track_id TEXT,
    spotify_track_name TEXT,
    spotify_track_url TEXT,
    spotify_uri TEXT,
    spotify_artists_json TEXT,
    spotify_artist_ids_json TEXT,
    spotify_artist_urls_json TEXT,
    spotify_album_id TEXT,
    spotify_album_name TEXT,
    spotify_album_url TEXT,
    spotify_album_type TEXT,
    spotify_album_release_date TEXT,
    spotify_album_release_precision TEXT,
    spotify_album_total_tracks INTEGER,
    spotify_album_artwork_url TEXT,
    spotify_album_artwork_width INTEGER,
    spotify_album_artwork_height INTEGER,
    spotify_album_label TEXT,
    spotify_album_copyrights_json TEXT,
    spotify_duration_ms INTEGER,
    spotify_duration_seconds INTEGER,
    spotify_duration_delta_ms INTEGER,
    spotify_explicit INTEGER,
    spotify_popularity INTEGER,
    spotify_isrc TEXT,
    spotify_track_number INTEGER,
    spotify_disc_number INTEGER,
    spotify_search_query TEXT,
    spotify_search_result_index INTEGER,
    spotify_raw_json TEXT,
    spotify_album_raw_json TEXT,
    lyrics_status TEXT,
    lyrics_path TEXT,
    lrclib_id INTEGER,
    lrclib_track_name TEXT,
    lrclib_artist_name TEXT,
    lrclib_album_name TEXT,
    lrclib_duration INTEGER,
    lrclib_duration_delta_seconds REAL,
    lrclib_match_method TEXT,
    lrclib_raw_json TEXT,
    lyrics_embedded INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Indexes:

```sql
CREATE INDEX idx_songs_isrc ON songs(isrc) WHERE isrc IS NOT NULL;
CREATE INDEX idx_songs_yt_video_id ON songs(yt_video_id);
CREATE INDEX idx_songs_ytm_video_id ON songs(ytm_video_id);
```

---

# 10. Database Invariants

After every successful committed state:

1. A serial exists at most once in `playlist.db`.
2. A serial exists at most once in `songs.db`.
3. `completed` playlist entries have a matching `songs.db` row.
4. A completed row points to an existing valid final MP3.
5. `duplicate` playlist entries do not own a retained `songs.db` row.
6. `pending` entries normally do not own a retained `songs.db` row.
7. `error` entries are allowed without a retained song.
8. `songs.isrc` contains the canonical ISRC when one exists.
9. The ISRC index contains non-NULL values only.
10. Duplicate lookup never considers the current serial as an existing duplicate of itself.

---

# 11. State Machine

```text
pending
   |
   v
processing
   |
   +-----------------------------+
   |                             |
   v                             v
success                       failure
   |                             |
   v                             v
ISRC duplicate check           error
   |                             |
   +----------+----------+       |
              |          |       |
              v          v       |
            unique    duplicate  |
              |          |       |
              |      user choice |
              |       /      \   |
              |      v        v  |
              | keep_prev  keep_current
              |      |        |
              |      v        v
              |  duplicate  completed
              |                 |
              +-----------------+

Old completed entry + keep_current:
old serial -> pending
current serial -> completed
```

Error retry:

```text
error -> pending
```

---

# 12. Per-Entry Working Directory

For serial `004`:

```text
temp/004/
```

The directory is the complete temporary workspace for one processing attempt.

Expected acquisition artifacts:

```text
temp/004/
├── master.mp3
├── master.info.json
├── thumbnails / thumbnail variants
└── manifest/recovery metadata when applicable
```

Temporary final production output can be staged separately until validation and promotion.

No temporary artifact is considered a retained library file.

---

# 13. One Complete yt-dlp Acquisition

The downloader must obtain the source package in one initial acquisition operation.

Conceptual behavior:

```bash
yt-dlp \
  -x \
  --audio-format mp3 \
  --audio-quality 0 \
  --write-info-json \
  --write-thumbnail \
  --write-all-thumbnails \
  --convert-thumbnails jpg \
  -o "temp/{serial}/master.%(ext)s" \
  "{ytm_url}"
```

The exact command may adapt to the installed yt-dlp version, but these behaviors must remain:

- acquire source audio;
- write complete source info JSON;
- acquire thumbnails needed for artwork selection;
- do not use `--add-metadata`;
- use the YT Music source URL, not a general YouTube audio search.

---

# 14. Source Validation

Before enrichment:

- `master.mp3` exists.
- `master.info.json` exists.
- JSON parses successfully.
- MP3 is readable.
- MP3 duration can be obtained.
- At least one usable artwork source exists when artwork is required.

Failure behavior:

1. write descriptive error;
2. set playlist entry to `error`;
3. do not create a `songs.db` retained row;
4. preserve serial;
5. retain enough information for retry.

---

# 15. Metadata Normalization

The metadata pipeline has three conceptual layers.

## Layer A — Raw metadata

The exact `master.info.json`, YT Music playlist-item JSON, Spotify API JSON, YouTube selected-result JSON, and LRCLIB response are preserved in the sidecar.

## Layer B — Normalized application model

A structured normalized representation is used internally and persisted to `songs.db`.

## Layer C — MP3 export model

Only selected player-facing fields and important identifiers are mapped into ID3.

---

# 16. Final Metadata Source Precedence

## 16.1 Title

Primary: normalized YT Music/yt-dlp title.

Spotify matched track may overlay the final title when Spotify enrichment is enabled and matched.

## 16.2 Artist

Primary: normalized YT Music/yt-dlp artist information.

Spotify matched track may overlay artist names when matched.

## 16.3 Album

Primary: YT Music/yt-dlp album.

Spotify matched track may overlay album identity/name when matched.

## 16.4 Album artist

Spotify album artists may improve album-artist identity when matched; otherwise source metadata is used when available.

## 16.5 Release date

Use catalog/source release date rather than silently replacing it with upload date.

Spotify release date can enrich/overlay the music release date when a match is accepted.

## 16.6 Track/disc number

Spotify catalog track/disc values can enrich source metadata when matched.

Playlist serial is never used as album track number.

## 16.7 Publisher/label

Use source publisher when present; Spotify album label can fill/enrich when present.

## 16.8 Copyright

Use source copyright when present; Spotify album copyright data can enrich it when present.

## 16.9 Duration

The actual downloaded MP3 duration is authoritative for the song file.

Spotify duration is used only for candidate matching and retained as catalog metadata.

YouTube music-video duration is video metadata and does not replace song duration.

## 16.10 ISRC

Canonical precedence:

1. valid Spotify matched-track ISRC;
2. valid source/yt-dlp ISRC fallback;
3. missing if neither exists.

---

# 17. Spotify Integration — Detailed Plan

## 17.1 Authentication

Use Spotify Web API Client Credentials flow.

Credential priority:

1. environment variables when `use_env=true` and variables exist;
2. config values;
3. disabled/error behavior according to configuration.

The project does not download Spotify audio.

## 17.2 Search

Search query:

```text
{title} {album}
```

The request should identify tracks rather than albums/playlists.

## 17.3 Candidate selection

For each returned result in original order:

1. read Spotify track duration;
2. compare with actual downloaded audio duration;
3. accept the first track whose duration delta is within `duration_tolerance_seconds`.

No post-search scoring is used.

## 17.4 Spotify data imported

Track:

- Spotify track ID
- track name
- Spotify URL
- URI
- artists
- artist IDs
- artist URLs
- album ID/name/URL/type
- album release date/precision
- album total tracks
- track/disc number
- duration in milliseconds/seconds
- explicit flag
- popularity
- external IDs including ISRC

Album:

- album object
- album label
- copyrights
- all album image metadata

## 17.5 Spotify artwork

- select largest returned album image by dimensions/area;
- download exact bytes;
- validate image format/readability;
- preserve bytes unchanged;
- embed unchanged image as APIC;
- record URL, dimensions, MIME type, byte length and SHA-256 in sidecar.

No resampling is done to Spotify artwork.

---

# 18. ISRC — Detailed Plan

## 18.1 Canonicalization

Input examples may contain spaces or hyphens. Canonical representation is uppercase alphanumeric characters in the standard 12-character shape.

Invalid values become missing.

## 18.2 Storage

Canonical ISRC:

```text
songs.isrc
```

Spotify original source value:

```text
songs.spotify_isrc
```

## 18.3 MP3

Write canonical ISRC to:

```text
TSRC
```

and expose it as:

```text
TXXX:isrc
```

only when one exists.

## 18.4 Duplicate query

Only:

```sql
SELECT *
FROM songs
WHERE isrc = ?
LIMIT 1;
```

No fallback matching.

---

# 19. Duplicate Resolution — Transactional Safety

## 19.1 Keep previous

The current temporary work is disposable.

Order:

1. detect duplicate;
2. show current + existing metadata;
3. operator selects previous;
4. mark current playlist entry `duplicate`;
5. commit status;
6. clean current temp artifacts.

## 19.2 Keep current

Never destroy old retained artifacts before the replacement is valid.

Order:

1. detect duplicate;
2. operator selects current;
3. finish Spotify/YouTube/LRCLIB/artwork work;
4. build final MP3;
5. write tags;
6. write lyrics;
7. validate final MP3;
8. generate sidecar;
9. compute hashes;
10. stage replacement files;
11. transactionally replace old/current DB ownership;
12. commit;
13. remove old artifacts;
14. clean temporary workspace.

If a failure occurs before commit, the previous retained song should remain intact.

---

# 20. YouTube Music-Video Search

## 20.1 Query

```text
{title} {album} official video song
```

## 20.2 Filtering

For each result in returned order:

```text
lower(result.title)
```

If it contains `lyrics`, skip it.

Otherwise select immediately.

## 20.3 Selected fields

Main MP3 metadata only needs:

- YouTube video ID
- YouTube video URL
- YouTube video title

Detailed fields remain in JSON, including when available:

- channel
- channel ID
- uploader
- uploader ID
- upload date
- release date
- timestamp
- duration
- views
- likes/comments
- categories/tags
- thumbnail
- raw info JSON

## 20.4 No acceptable result

Set selected-video fields to null/absent and continue successfully.

---

# 21. LRCLIB — Detailed Plan

## 21.1 Allowed endpoint

Only:

```text
GET /api/get
```

is permitted.

The implementation must never call `/api/search`.

## 21.2 Inputs

Use current song metadata:

- track name/title
- artist
- album
- duration

## 21.3 Acceptance

Accept only when:

- response is structurally valid;
- synchronized lyrics are present;
- synchronized lyrics parse into valid timestamped lines.

Plain-only lyrics are rejected for the `.lrc` workflow.

## 21.4 Saved lyrics

Synced:

```text
<name>.lrc
```

and embedded as synchronized lyrics.

Unsynced:

- no `.lrc` file;
- song placed in `songs/no_synced_lyrics`;
- JSON records the lyric lookup/result status.

## 21.5 Lyrics embedding

The final MP3 receives:

- `SYLT` for synchronized timestamped lyrics;
- `USLT` compatibility representation containing lyric text.

The actual `.lrc` file preserves the timestamped external representation.

---

# 22. Artwork — Detailed Plan

## 22.1 Provider precedence

1. Spotify matched track artwork when enabled and valid.
2. YT Music/yt-dlp fallback artwork.

## 22.2 Spotify

Use the largest image returned by Spotify.

Preserve the bytes exactly.

## 22.3 YT Music fallback

The thumbnail problem addressed by the implementation is that generic YouTube thumbnails can be padded/widescreen while YT Music exposes square album-art images.

The fallback process:

1. collect all yt-dlp thumbnails;
2. inspect thumbnail dimensions/URLs;
3. optionally inspect YT Music OpenGraph image;
4. classify square candidates;
5. prefer valid square artwork;
6. use source provenance to break ties;
7. if fallback is not square and square normalization is enabled, center-crop to square;
8. correct EXIF orientation;
9. output normalized JPEG.

Spotify artwork does not go through this transformation stage.

## 22.4 MP3 embedding

Artwork is embedded as front cover `APIC`.

---

# 23. MP3 Metadata Contract

## 23.1 Standard ID3 frames

When available:

```text
TIT2  Title
TPE1  Track artist
TPE2  Album artist
TALB  Album
TDRC  Release date
TRCK  Track number
TPOS  Disc number
TCON  Genre
TCOM  Composer
TPUB  Publisher/label
TCOP  Copyright
TLAN  Language
TBPM  BPM
TCMP  Compilation
TENC  Encoder
TLEN  Actual duration in milliseconds
TSRC  Canonical ISRC
APIC  Front cover
SYLT  Synchronized lyrics
USLT  Lyrics text compatibility
```

Only fields with meaningful values are written, except fields explicitly required by the final validation contract.

## 23.2 TXXX

Keep TXXX concise. Durable application/catalog fields include:

- serial number
- playlist position
- YT Music source ID
- YouTube selected video ID/title
- Spotify track ID
- Spotify album ID
- Spotify ISRC
- canonical ISRC
- lyrics status
- artwork provider/basic properties

## 23.3 UFID

Use machine-readable identifiers for:

- YT Music source ID
- selected YouTube video ID
- Spotify track ID when available

## 23.4 WXXX

Use important URLs:

- YT Music source URL
- selected YouTube video URL
- Spotify track URL
- Spotify album URL when available

## 23.5 Intentionally excluded from main MP3 metadata

Do not embed:

- raw API JSON
- raw yt-dlp blobs
- long source descriptions
- age restrictions
- verbose channel details
- extractor internals
- downloader debug information
- giant thumbnail lists
- format-selection internals

Those go to JSON sidecar.

---

# 24. Sidecar JSON Contract

Every finalized MP3 must have a same-basename JSON.

Example:

```text
001_Urike_Urike_Artist.mp3
001_Urike_Urike_Artist.json
```

If synced:

```text
001_Urike_Urike_Artist.lrc
```

## 24.1 Recommended top-level sections

```json
{
  "schema_version": "...",
  "metadata_export_version": "...",
  "playlist": {},
  "song": {},
  "source": {},
  "spotify": {},
  "youtube_video": {},
  "lyrics": {},
  "artwork": {},
  "files": {},
  "duplicate": {},
  "timestamps": {}
}
```

## 24.2 Raw provenance

The sidecar can contain complete raw objects rather than trying to encode them into ID3.

This is where verbose source data belongs.

---

# 25. Filename Rules

Final filename:

```text
{serial:03d}_{safe_title}_{safe_artist}.mp3
```

Corresponding files:

```text
{same basename}.json
{same basename}.lrc    # only synced lyrics
```

Requirements:

- serial always present;
- Windows-invalid characters removed/replaced;
- no directory traversal;
- reserved Windows names protected;
- filename length bounded;
- readable title/artist preserved where possible;
- database identity never changes because of filename sanitization.

---

# 26. Finalization Order

The safe order is:

```text
1. Read playlist occurrence
2. Create/recover temporary workspace
3. Acquire source once with yt-dlp
4. Validate source artifacts
5. Normalize metadata
6. Attempt Spotify enrichment when enabled
7. Determine canonical ISRC
8. Check ISRC duplicate
9. Resolve duplicate decision if needed
10. Search selected YouTube music video
11. Fetch selected video metadata
12. Obtain accepted LRCLIB synced lyrics through /api/get only
13. Select artwork
14. Construct final MP3 staging path
15. Copy/source audio into staging output
16. Write standard ID3 tags with Mutagen
17. Write concise TXXX fields
18. Write UFID/WXXX identity/URL fields
19. Embed APIC artwork
20. Embed SYLT/USLT lyrics
21. Save
22. Reopen
23. Validate
24. Generate JSON sidecar
25. Hash final MP3
26. Stage MP3/LRC/JSON
27. Atomically promote final files
28. Commit songs.db + playlist.db state transactionally
29. Clean previous duplicate artifacts if applicable
30. Remove temp directory
31. Report result
```

Physical file replacement and DB transitions must be coordinated so the application does not destroy the previous retained song before the replacement is known to be valid.

---

# 27. Validation Contract

Validation occurs on the **fully tagged, fully embedded final MP3**, not on the raw `master.mp3`.

Checks should include:

## File

- exists;
- nonzero size;
- reopenable;
- valid MP3/audio stream;
- readable duration.

## Standard metadata

- title present;
- artist present;
- album present when expected;
- release date valid when present;
- track/disc valid when present;
- standard fields match normalized model.

## ISRC

- `TSRC` matches canonical ISRC when one is available;
- no fake `NULL` string is written.

## Important source/catalog identities

- YT Music ID matches normalized source;
- YouTube selected-video ID/URL match normalized selected result;
- Spotify ID/ISRC match normalized Spotify result when matched.

## Artwork

- APIC exists;
- image is decodable;
- correct provider/bytes/provenance when applicable.

## Lyrics

- synced status matches sidecar;
- SYLT exists for synced songs;
- USLT compatibility projection exists when enabled;
- `.lrc` exists only for synced songs.

## Sidecar

- same basename exists;
- valid JSON;
- references final MP3 path;
- contains file hash/size;
- contains source/catalog provenance.

---

# 28. Hashing

After all metadata, artwork and lyrics embedding are complete:

```text
SHA-256(final MP3 bytes)
```

Store:

```text
songs.mp3_size
songs.mp3_sha256
```

and sidecar JSON file information.

The hash covers the final fully-tagged MP3, not the original `master.mp3`.

---

# 29. Error Handling

## 29.1 Source unavailable

- preserve playlist occurrence;
- status `error`;
- descriptive message;
- no `songs.db` retained row;
- retry later.

## 29.2 yt-dlp failure

- do not mark completed;
- preserve serial;
- clean partial temporary artifacts;
- allow retry.

## 29.3 Spotify failure

Default behavior is nonfatal when `fail_on_error=false`:

- continue without Spotify enrichment;
- continue using source metadata/artwork.

When `fail_on_error=true`, Spotify failure may fail the song entry.

## 29.4 YouTube no match

Nonfatal:

- selected-video fields absent/null;
- song still completes.

## 29.5 LRCLIB no synced lyrics

Nonfatal:

- song completes;
- no `.lrc` file;
- placed in `songs/no_synced_lyrics`;
- sidecar records lookup/result.

## 29.6 Final validation failure

- do not promote final MP3;
- do not insert retained `songs.db` row;
- mark playlist `error`;
- preserve serial;
- clean or retain diagnostics according to recovery policy.

---

# 30. Recovery and Restart

The pipeline is designed to tolerate interruption.

On restart:

1. initialize/migrate databases;
2. inspect playlist state;
3. retry pending entries;
4. optionally retry error entries with `--retry-errors`;
5. detect stale temporary workspaces;
6. never interpret an incomplete `.tmp` file as a completed library file;
7. preserve permanent serials.

For duplicate replacement:

- if crash occurs before commit, previous retained row/file remains the safe fallback;
- if commit succeeds, post-commit cleanup removes old artifacts;
- orphan cleanup must never delete a file still referenced by a committed `songs.db` row.

---

# 31. CLI / Operational Commands

Current main options include:

```text
python main.py
python main.py --config config.json
python main.py --ingest-only
python main.py --no-ingest
python main.py --status
python main.py --doctor
python main.py --retry-errors
python main.py --check-invariants
python main.py --limit N
```

Typical workflow:

```powershell
python main.py --doctor
python main.py
```

Monitoring:

```powershell
python main.py --status
python main.py --check-invariants
```

Retry:

```powershell
python main.py --retry-errors
```

---

# 32. Logging

The application logs important state changes to `logs/phase1.log`.

Useful events:

- playlist ingestion summary;
- serial allocation/reuse;
- unavailable playlist entries;
- source acquisition start/end;
- Spotify match/no-match/error;
- ISRC detection;
- duplicate prompt and decision;
- YouTube search query and selection;
- LRCLIB request/result/status;
- artwork provider and size;
- final validation;
- hash;
- DB commit;
- cleanup.

Credentials/secrets must never be logged.

---

# 33. Security and Credential Handling

- Do not commit actual Spotify credentials.
- Prefer environment variables for credentials.
- `cookies.txt` is a user-local credential artifact and should remain ignored by version control.
- Do not print cookie contents.
- Do not put Spotify client secrets in sidecar JSON.
- Sidecar raw API records must exclude credential headers/tokens.
- Network requests should use configured timeouts.
- File paths are sanitized before final output.
- Temporary directories are scoped by serial number.

---

# 34. Module Responsibilities

## `main.py`

Application entry point and CLI.

Responsibilities:

- parse arguments;
- load config;
- initialize directories/databases;
- run doctor/status/invariant operations;
- start ingestion and processing;
- propagate top-level errors with appropriate exit code.

## `src/playlist_ingest.py`

Responsibilities:

- YTMusic client lifecycle;
- playlist retrieval;
- playlist-item normalization;
- unavailable-entry handling;
- permanent serial allocation/reuse;
- database ingestion.

## `src/downloader.py`

Responsibilities:

- build exact yt-dlp acquisition command;
- invoke yt-dlp;
- set runtime/network arguments;
- validate acquisition artifacts.

## `src/metadata.py`

Responsibilities:

- parse `info.json`;
- normalize fields;
- canonicalize ISRC;
- track/date/duration handling;
- convert raw source data to normalized metadata.

## `src/spotify.py`

Responsibilities:

- client credentials authentication;
- Spotify track search;
- returned-order/duration match;
- track/album retrieval;
- metadata overlay;
- largest artwork selection;
- raw data preservation.

## `src/duplicate_checker.py`

Responsibilities:

- ISRC-only duplicate lookup;
- no fallback heuristic.

## `src/youtube_finder.py`

Responsibilities:

- exact search-query construction;
- result retrieval;
- case-insensitive `lyrics` filtering;
- first acceptable selection;
- selected video metadata extraction.

## `src/lrclib.py`

Responsibilities:

- `/api/get` only;
- throttle/retry;
- synchronized lyric validation;
- LRCLIB result normalization.

## `src/artwork.py`

Responsibilities:

- YT Music thumbnail discovery;
- OpenGraph discovery;
- candidate scoring for square/fallback artwork only;
- YT Music artwork normalization;
- Spotify artwork download with byte preservation.

## `src/embedder.py`

Responsibilities:

- final ID3 creation/writing;
- standard frames;
- concise TXXX;
- UFID/WXXX;
- APIC artwork;
- SYLT/USLT lyrics.

## `src/validator.py`

Responsibilities:

- reopen final MP3;
- validate frames/IDs/artwork/lyrics;
- reject incomplete output before final DB commit.

## `src/sidecar.py`

Responsibilities:

- build same-basename detailed JSON;
- serialize all provenance safely;
- write/re-read sidecar.

## `src/hashing.py`

Responsibilities:

- SHA-256 calculation.

## `src/db_playlist.py`

Responsibilities:

- playlist schema/migrations;
- queries;
- serial integrity;
- status transitions;
- retry/reset.

## `src/db_songs.py`

Responsibilities:

- song schema/migrations;
- canonical ISRC storage/index;
- retained-row operations;
- file metadata persistence;
- song integrity checks.

## `src/pipeline.py`

Responsibilities:

- orchestration;
- per-entry lifecycle;
- duplicate resolution;
- temp workspace management;
- final path calculation;
- transaction coordination;
- overall run/status/invariant logic.

---

# 35. Detailed Data Flow for One Song

Assume:

```text
serial = 001
Title = Urike Urike
Album = Urike Urike (From "Hit 2")
Artist = M.M. Sreelekha, Sid Sriram, Ramya Behara
```

## Step A — Playlist

Create/reuse:

```text
playlist.db
001 | playlist_position=1 | YTM source ID | pending
```

## Step B — Download

Produce:

```text
temp/001/master.mp3
temp/001/master.info.json
thumbnail candidates
```

## Step C — Normalize

Extract title/artist/album/duration/source IDs.

## Step D — Spotify

Search:

```text
Urike Urike Urike Urike (From "Hit 2")
```

Select first duration match within tolerance.

Import Spotify catalog fields, IDs, ISRC, album artwork.

## Step E — Canonical ISRC

If Spotify returns valid ISRC:

```text
canonical_isrc = Spotify ISRC
```

Otherwise use valid source ISRC.

## Step F — Duplicate

Query:

```sql
songs.isrc = canonical_isrc
```

If no result: continue.

If result: prompt operator.

## Step G — YouTube

Search:

```text
Urike Urike Urike Urike (From "Hit 2") official video song
```

Skip results whose titles contain `lyrics`.

Take first remaining result.

## Step H — LRCLIB

Call only:

```text
GET /api/get
```

Use current title/artist/album/duration.

Accept synchronized result only.

## Step I — Artwork

Use largest Spotify artwork if valid; otherwise YT Music fallback artwork.

## Step J — MP3

Write concise standard ID3/custom identity fields, artwork, SYLT and USLT.

## Step K — JSON

Write detailed sidecar.

## Step L — Validate/hash/promote

Reopen → validate → SHA-256 → atomic promotion.

## Step M — Database

Insert `songs.db` row and mark playlist `completed` transactionally.

---

# 36. Sidecar vs MP3 Responsibility Matrix

| Data | MP3 | JSON |
|---|---:|---:|
| Title | Yes | Yes |
| Artist | Yes | Yes |
| Album | Yes | Yes |
| Album artist | Yes | Yes |
| Release date | Yes | Yes |
| Track/disc | Yes | Yes |
| Genre | Yes | Yes |
| Composer | Yes | Yes |
| Publisher/label | Yes | Yes |
| Copyright | Yes | Yes |
| Language | Yes | Yes |
| BPM | Yes | Yes |
| Compilation | Yes | Yes |
| Actual duration | Yes | Yes |
| Canonical ISRC | Yes | Yes |
| YT Music ID | Yes | Yes |
| YouTube video ID | Yes | Yes |
| YouTube video URL/title | Yes | Yes |
| Spotify track/album IDs | Yes | Yes |
| Spotify ISRC | Yes | Yes |
| Artwork | Yes | Yes (provenance) |
| Synced lyrics | Yes | Yes |
| `.lrc` path/status | Small metadata only | Yes |
| Source descriptions | No | Yes |
| Age-limit fields | No | Yes |
| Channel internals | No | Yes |
| Raw yt-dlp JSON | No | Yes |
| Raw YT Music JSON | No | Yes |
| Raw Spotify JSON | No | Yes |
| Raw YouTube JSON | No | Yes |
| Raw LRCLIB JSON | No | Yes |
| Search details | No | Yes |
| File hash | TXXX/sidecar optional; DB authoritative | Yes |

---

# 37. Duplicate Behavior Matrix

| Condition | Action |
|---|---|
| Valid ISRC, no matching song | Process normally |
| Valid ISRC, matching song | Prompt |
| Missing/invalid ISRC | Skip duplicate lookup; process normally |
| Duplicate + keep previous | Current becomes `duplicate`; retained song unchanged |
| Duplicate + keep current | New validated song replaces retained song; old playlist serial returns to `pending` |

---

# 38. Lyrics Output Matrix

| LRCLIB result | MP3 folder | `.lrc` | Embedded lyrics | JSON |
|---|---|---:|---:|---:|
| Valid synced lyrics | `synced_lyrics` | Yes | SYLT + USLT | Yes |
| Plain only | `no_synced_lyrics` | No | No synced lyric embedding | Yes |
| No result | `no_synced_lyrics` | No | No | Yes |
| API error with nonfatal setting | `no_synced_lyrics` | No | No | Yes |

---

# 39. Artwork Output Matrix

| Condition | Artwork source | Transformation |
|---|---|---|
| Spotify matched + valid album images | Spotify largest image | None; bytes preserved |
| Spotify unavailable + valid YT Music artwork | YT Music/yt-dlp | Candidate selection + possible square normalization |
| No usable artwork | None/controlled failure | MP3 completion behavior depends on validation/config |

---

# 40. Testing Strategy

The test suite should be deterministic and offline wherever possible by mocking network boundaries.

Minimum coverage areas:

1. normal playlist ingestion;
2. unavailable playlist entry (`videoId=None`);
3. serial preservation;
4. repeated playlist occurrences;
5. existing database migration;
6. yt-dlp command contract;
7. source validation;
8. metadata normalization;
9. Spotify duration matching;
10. Spotify returned-order selection;
11. Spotify largest artwork selection;
12. Spotify artwork byte-for-byte preservation;
13. Spotify failure nonfatal behavior;
14. ISRC normalization;
15. ISRC duplicate detection;
16. missing ISRC skip;
17. keep-previous duplicate behavior;
18. keep-current replacement safety;
19. YouTube exact query;
20. YouTube lyrics title filtering;
21. all-lyrics/no-result behavior;
22. LRCLIB `/api/get` only;
23. synchronized lyric parsing;
24. plain-only lyric rejection;
25. SYLT/USLT embedding;
26. synced/unsynced output directory rules;
27. complete sidecar creation;
28. metadata validation;
29. artwork validation;
30. hash calculation;
31. Windows filename safety;
32. transaction/recovery behavior;
33. invariant checks;
34. archive extraction/retest.

The latest prepared repository was regression-tested offline after extraction from the release archive.

---

# 41. Acceptance Criteria

The build is considered functionally complete when all of the following are true:

### Playlist

- Complete playlist can be ingested.
- Returned order is preserved.
- Every occurrence has a permanent serial.
- Unavailable entries do not crash the ingestion run.

### Download

- Usable entries download successfully through the YT Music source.
- Complete source JSON is retained.
- Artwork acquisition is available from the same source acquisition phase.

### Spotify

- Can be disabled.
- Correctly authenticates when enabled.
- Searches title + album.
- Uses first duration-matching result.
- Imports catalog identifiers/metadata.
- Extracts ISRC.
- Selects largest album artwork.
- Preserves Spotify artwork bytes unchanged.

### Duplicate

- ISRC-only.
- No fallback matching.
- Missing/invalid ISRC skips check.
- User controls duplicate decision.
- Keep-current is replacement-safe.

### YouTube

- Correct query format.
- Returned order preserved.
- `lyrics` filtering is case-insensitive.
- First acceptable result selected.
- Main MP3 gets YouTube video ID/URL/title.

### Lyrics

- Only `/api/get`.
- Only synchronized lyrics accepted.
- Synced `.lrc` exists with MP3.
- No `.lrc` for unsynced songs.
- Synced lyrics embedded into MP3.

### Metadata

- Main MP3 contains concise player-facing tags.
- Main MP3 contains important external identities.
- Raw/verbose data goes to JSON.
- Sidecar exists for every finalized MP3.

### Finalization

- Final MP3 is reopened and validated.
- Hash is over final MP3 bytes.
- File promotion is atomic.
- Database only reports completed after final artifact is valid.
- Temporary files are cleaned safely.

---

# 42. Known Design Decisions and Their Reasons

## Permanent serial rather than source ID

A playlist occurrence is an occurrence, not just a recording. Repeated source IDs therefore remain independent playlist entries.

## Separate playlist and songs databases

Playlist history/state and retained-library state answer different questions and should not be conflated.

## ISRC as sole duplicate identifier

The design intentionally avoids heuristic duplicate matching. This makes duplicate behavior deterministic and explicitly dependent on one catalog identifier.

## Spotify as enrichment, not audio source

Spotify provides catalog metadata/artwork/ISRC but does not provide the audio used by this downloader.

## YouTube music video is enrichment only

The selected YouTube video does not replace the YT Music audio source and its duration does not replace the audio duration.

## LRCLIB only `/api/get`

The current requirement deliberately prohibits broad `/api/search` discovery and limits lyrics retrieval to metadata-based lookup.

## Raw JSON in sidecar

ID3 is for player-facing metadata. The sidecar preserves complete provenance without polluting the MP3 with raw implementation data.

## Spotify artwork preserved unchanged

Avoids unnecessary transformations and retains the returned catalog artwork as supplied.

## YT Music fallback normalized separately

The YT Music ecosystem can expose padded/widescreen thumbnails, so fallback artwork requires candidate selection and optional square normalization.

---

# 43. Migration / Compatibility Requirements

When an older project database is opened:

- detect schema version;
- add missing columns/indexes safely;
- preserve existing rows and serials;
- migrate Spotify/source ISRC into canonical `songs.isrc` when possible;
- preserve existing retained MP3 paths;
- never recycle serials;
- do not silently discard previous sidecar associations.

When metadata export format changes, increment metadata export version in sidecars and keep migration/re-embedding tools compatible where practical.

---

# 44. Existing-MP3 Re-Embedding

`scripts/reembed_existing.py` exists for rebuilding metadata on already-produced MP3 files without requiring a fresh audio download when sufficient sidecar/database/source information exists.

Recommended safety flow:

```powershell
python scripts/reembed_existing.py --dry-run
python scripts/reembed_existing.py
```

The re-embed process must create a validated replacement before replacing an existing file.

---

# 45. Operational Workflow for a Windows User

## First installation

1. Install Python 3.11+.
2. Install FFmpeg/FFprobe and make sure they are discoverable.
3. Install a supported JavaScript runtime if yt-dlp requires it for the chosen extraction path.
4. Extract the project.
5. Configure `config.json`.
6. Put optional YT Music cookies in `cookies.txt` if needed.
7. Configure Spotify credentials if Spotify enrichment is enabled.

## Initial verification

```powershell
python main.py --doctor
```

## Start pipeline

```powershell
python main.py
```

## Inspect state

```powershell
python main.py --status
python main.py --check-invariants
```

## Retry errors

```powershell
python main.py --retry-errors
```

---

# 46. Example Final Output

For a song with synced lyrics:

```text
songs/
└── synced_lyrics/
    ├── 001_Urike_Urike_M.M._Sreelekha_Sid_Sriram_Ramya_Behara.mp3
    ├── 001_Urike_Urike_M.M._Sreelekha_Sid_Sriram_Ramya_Behara.lrc
    └── 001_Urike_Urike_M.M._Sreelekha_Sid_Sriram_Ramya_Behara.json
```

For a song without synced lyrics:

```text
songs/
└── no_synced_lyrics/
    ├── 002_Another_Song_Artist.mp3
    └── 002_Another_Song_Artist.json
```

The MP3 contains concise metadata/identities/cover/lyrics.

The JSON contains the complete detailed record.

---

# 47. Example Main MP3 Metadata

A representative enriched MP3 can expose:

```text
Title                         Urike Urike
Artist                        M.M. Sreelekha; Sid Sriram; Ramya Behara
Album                         Urike Urike (From "Hit 2")
Album Artist                  catalog/source value
Release Date                  2022-11-10
Genre                         Music
Composer                      M.M. Sreelekha
Publisher                     catalog/source label
Copyright                     catalog/source copyright
Duration                      actual downloaded audio duration
ISRC                          Spotify ISRC when available

YT Music ID                   S072HjMJZY0
YT Music URL                  https://music.youtube.com/watch?v=S072HjMJZY0

YouTube Video ID              A3Im3P0--aE
YouTube Video URL             https://www.youtube.com/watch?v=A3Im3P0--aE
YouTube Video Title           Urike Urike - Video Song ...

Spotify Track ID              <matched Spotify ID>
Spotify Album ID              <matched Spotify album ID>
Spotify Track URL             <matched Spotify URL>

Artwork                       embedded APIC
Lyrics                        synchronized SYLT + USLT
```

The exact values vary by the actual source/API response.

---

# 48. Example Detailed Sidecar Structure

Conceptually:

```json
{
  "schema_version": "...",
  "playlist": {
    "serial_number": 1,
    "playlist_position": 1,
    "ytm_playlist_id": "...",
    "ytm_video_id": "...",
    "ytm_url": "..."
  },
  "song": {
    "title": "...",
    "artist": "...",
    "artists": ["..."],
    "album": "...",
    "album_artist": "...",
    "release_date": "...",
    "duration": 276
  },
  "isrc": {
    "canonical": "...",
    "source": "spotify"
  },
  "spotify": {
    "matched": true,
    "track_id": "...",
    "album_id": "...",
    "isrc": "...",
    "raw_track": {},
    "raw_album": {},
    "artwork": {}
  },
  "youtube_video": {
    "selected": true,
    "video_id": "...",
    "url": "...",
    "title": "...",
    "raw_info": {}
  },
  "lyrics": {
    "status": "synced",
    "lrclib_id": 123,
    "lrc_path": "...",
    "synced_lyrics": "[00:...] ...",
    "raw_response": {}
  },
  "artwork": {
    "provider": "spotify",
    "source_url": "...",
    "width": 640,
    "height": 640,
    "sha256": "..."
  },
  "source": {
    "ytm_playlist_item": {},
    "yt_dlp_info": {}
  },
  "files": {
    "mp3_path": "...",
    "mp3_size": 12345678,
    "mp3_sha256": "...",
    "json_path": "...",
    "lrc_path": "..."
  }
}
```

The exact implementation may include additional fields from the current normalized model.

---

# 49. Full Current Module API Inventory

The current implementation contains these major callable/class responsibilities:

## Artwork module

- `ArtworkError`
- `ArtworkCandidate`
- square/area/provider utilities
- OpenGraph retrieval
- thumbnail candidate discovery
- artwork selection
- normalization
- Spotify artwork download

## Playlist DB

- initialization
- schema migration
- transactions
- max serial
- all rows
- serial lookup
- next pending
- insert/update
- retry errors
- counts
- integrity assertions

## Songs DB

- initialization
- schema migration
- transactions
- insert/update
- ISRC lookup
- serial lookup
- list/count
- integrity assertions

## Downloader

- yt-dlp command builder
- executable/runtime argument handling
- acquisition
- source artifact validation

## Duplicate checker

- ISRC duplicate model
- ISRC lookup

## Embedder

- text conversion
- TXXX
- WXXX
- UFID
- LRC parsing
- lyrics embedding
- core metadata embedding
- final MP3 embedding

## LRCLIB

- GET request
- throttle
- duration comparison
- synced lyric validation
- result normalization
- lookup

## Metadata

- load/dump source JSON
- string/list/date/integer/bool helpers
- ISRC normalization
- album/artist extraction
- URL parsing
- metadata merge
- canonical metadata normalization
- metadata field list

## Pipeline

- duplicate resolver
- project-path resolution
- final filename construction
- playlist record construction
- old serial cleanup
- one-entry processing
- run loop
- invariant checks
- DB coordinator commits

## Playlist ingestion

- artist extraction
- duration conversion
- album extraction
- URL construction
- playlist track extraction
- existing-entry matching
- playlist retrieval
- track retrieval
- ingestion

## Sidecar

- JSON-safe conversion
- sidecar construction
- write/read

## Spotify

- token retrieval
- HTTP request
- artist/album/image helpers
- track search
- metadata overlay

## YouTube finder

- exact search query
- JSON result parsing
- publication fields
- result selection

---

# 50. Quality Gates Before Release

Before calling a build final:

## Source quality

- compile all Python modules;
- no dead/duplicate path handling;
- no accidental `/api/search` usage;
- no accidental non-ISRC duplicate matcher;
- no accidental raw metadata dumping into MP3;
- no credential leakage.

## Tests

- entire test suite passes;
- extracted archive passes tests again;
- current DB schema initializes from empty;
- previous schema migrates;
- invariants pass.

## Manual sample inspection

At least one real MP3 should be inspected using `scripts/inspect_mp3.py` and an external tag viewer/player to confirm:

- title/artist/album display correctly;
- YT Music ID is present;
- YouTube video ID is present;
- Spotify IDs/ISRC are present when matched;
- artwork is correct;
- synchronized lyrics are present when LRCLIB returns them;
- no unwanted verbose fields clutter the main tag display.

## Live integration smoke test

Run on a real Windows machine with:

- valid YTMusic playlist/auth;
- FFmpeg/FFprobe;
- supported yt-dlp JS runtime;
- Spotify credentials if enabled;
- network access to LRCLIB.

---

# 51. Out of Scope

Unless explicitly added later, the following remain outside this phase:

- Demucs vocal separation
- Whisper transcription
- MMS/speech models
- instrumental extraction
- manual metadata editor UI
- audio hashing as duplicate identity
- fuzzy duplicate matching
- title/artist/duration fallback duplicate matching
- generalized YouTube candidate scoring
- automatic editorial judgment about officialness beyond the specified selection rule
- Spotify audio downloading
- LRCLIB `/api/search`
- lyrics other than accepted synchronized lyrics for `.lrc` output

---

# 52. Historical Changes From the Original Plan

The original specification established the permanent serial architecture, two databases, one yt-dlp acquisition, Mutagen-only final tag authority, ISRC duplicate identity, deterministic YouTube filtering, validation, hashing, and cleanup. fileciteturn0file0L15-L38

Subsequent requirements changed/enhanced the system as follows:

1. **Unavailable YTMusic entries:** `videoId=None` is now a recoverable playlist-entry condition rather than an ingestion-fatal exception.
2. **Spotify enrichment:** optional catalog enrichment was added.
3. **Spotify artwork:** largest Spotify album artwork is now preferred and preserved unchanged.
4. **LRCLIB:** only `/api/get` is used and synchronized lyrics are accepted.
5. **Lyrics output:** `.lrc` files are created only for synced lyrics; synced lyrics are also embedded in the MP3.
6. **Sidecar JSON:** every MP3 gets a same-basename detailed JSON record.
7. **MP3 metadata:** verbose source/API material was moved out of the main ID3 tag set; only concise player-facing metadata and important IDs/URLs remain.
8. **ISRC duplicate logic:** the duplicate identifier is restored as ISRC-only, with Spotify ISRC preferred and source ISRC as fallback.

The current build must be understood through the active rules in this document; the original plan is retained below as a historical appendix.

---

# 53. Implementation Principles for Future Changes

Any future modification should preserve these core contracts unless explicitly revising them:

- playlist serials are permanent;
- source identity and playlist occurrence identity remain separate;
- Spotify remains an optional enrichment layer;
- actual audio remains the YT Music source;
- YouTube video remains enrichment only;
- ISRC remains the sole duplicate identifier;
- no `/api/search` for LRCLIB;
- only synchronized lyrics create `.lrc` files;
- the main MP3 remains concise;
- the sidecar remains the detailed provenance store;
- final metadata authority remains Mutagen;
- final MP3 validation occurs before DB completion;
- hashes are computed on final bytes;
- replacement never destroys a previous valid retained song prematurely.

---

# 54. Final Release Checklist

```text
[ ] config.json reviewed
[ ] Spotify credentials configured or disabled intentionally
[ ] cookies configured if needed
[ ] FFmpeg available
[ ] FFprobe available
[ ] JS runtime available/recognized
[ ] python main.py --doctor passes
[ ] databases initialized/migrated
[ ] playlist ingestion tested
[ ] unavailable item handling tested
[ ] Spotify match tested
[ ] Spotify artwork tested
[ ] ISRC duplicate detection tested
[ ] YouTube search tested
[ ] LRCLIB /api/get-only behavior tested
[ ] synced lyrics embedded
[ ] synced .lrc written
[ ] unsynced song correctly routed
[ ] JSON sidecar created
[ ] final MP3 validation passes
[ ] SHA-256 stored
[ ] atomic finalization passes
[ ] DB invariants pass
[ ] extracted release archive passes tests
```

---

# Appendix A — Historical Original Specification

> The following is preserved verbatim from the original `pipeline.md`. It is historical because later user requirements introduced Spotify enrichment, LRCLIB, detailed JSON sidecars, updated artwork behavior, and restored ISRC duplicate detection. The appendix exists so the complete original plan remains available without information loss.

---

# PHASE 1 — YOUTUBE MUSIC PLAYLIST DOWNLOADER & ENRICHER

**Status:** Final project specification

**Purpose:** Implementation-ready specification for Phase 1 of the YouTube Music playlist downloader/enricher.

---

## 0. DOCUMENT PURPOSE

This document is the complete Phase 1 project plan.

It consolidates the final architecture and all decisions established during planning:

- `playlist.db` is the permanent playlist record.
- `songs.db` contains the currently retained/downloaded songs.
- Every playlist entry receives one permanent, unique serial number.
- The serial number never changes and is never reused.
- The same serial number is used in `songs.db` when that playlist entry owns the retained song.
- Playlist order is captured from the YTMusic API in its returned/default order.
- Processing happens one playlist entry at a time.
- The initial acquisition uses one complete `yt-dlp` command to obtain the audio, complete `info.json`, and artwork.
- The initial `yt-dlp` command does **not** use `--add-metadata`.
- Python/Mutagen is the single authority responsible for final ID3 metadata and artwork embedding.
- ISRC is the only duplicate-detection key.
- Missing ISRC is stored as `NULL` and does not trigger duplicate detection.
- Duplicate handling never removes a playlist entry from `playlist.db`.
- When a duplicate is detected, the user chooses whether to keep the previous retained song or the current downloaded song.
- YouTube video discovery uses exactly the query `{title} {album_name} official video song`.
- YouTube results are used in returned order.
- Any result whose title contains the word `lyrics` is skipped, case-insensitively.
- The first remaining result is selected immediately.
- There is no YouTube result scoring, ranking, confidence system, or manual weighting.
- The final MP3 contains rich metadata, artwork, source identity, and selected YouTube music-video metadata.
- The final MP3 is validated before it is committed to `songs.db`.
- The final MP3 receives a SHA-256 hash after all metadata and artwork have been written.
- Temporary files are removed only after successful finalization.
- Lyrics, Demucs, Whisper, MMS, vocal separation, instrumental extraction, and manual metadata editing are outside Phase 1.

This document is intentionally detailed so that the final implementation can be built directly from it without redesigning the architecture during coding.

---

# 1. PROJECT OVERVIEW

## 1.1 Objective

Build a standalone automated pipeline that takes one YouTube Music playlist and produces a local library of richly tagged MP3 files while maintaining a permanent record of every playlist entry.

The project is not simply an audio downloader. It is a playlist ingestion, identity, metadata, duplicate-management, video-enrichment, and MP3 finalization system.

The complete lifecycle is:

```text
YouTube Music Playlist
        |
        v
YTMusic API ingestion
        |
        v
Preserve returned playlist order
        |
        v
Assign permanent serial numbers
        |
        v
playlist.db
        |
        v
Select next pending entry
        |
        v
ONE complete yt-dlp acquisition
        |
        +-------------------+-------------------+
        |                   |                   |
        v                   v                   v
     master.mp3       master.info.json      master.jpg
        |                   |                   |
        +-------------------+-------------------+
                            |
                            v
                  Source validation
                            |
                            v
                  Metadata extraction
                            |
                            v
                    Metadata normalization
                            |
                            v
                       Extract ISRC
                            |
                            v
                    Search songs.db by ISRC
                            |
                 +----------+----------+
                 |                     |
                 v                     v
             no match              duplicate
                 |                     |
                 |                Ask user:
                 |              previous/current
                 |                     |
                 +----------+----------+
                            |
                            v
                 YouTube video search
                            |
                            v
        {title} {album_name} official video song
                            |
                            v
                Skip titles containing lyrics
                            |
                            v
                First remaining result
                            |
                            v
                  Retrieve video metadata
                            |
                            v
                 Use already-downloaded artwork
                            |
                            v
                    Build final MP3
                            |
                            v
                Mutagen writes ALL final tags
                            |
                            v
                     Validate MP3
                            |
                            v
                    Calculate SHA-256
                            |
                            v
                   Atomic final rename
                            |
                            v
                       songs.db
                            |
                            v
                playlist.db -> completed
                            |
                            v
                       Cleanup temp
                            |
                            v
                   Process next pending
```

---

# 2. SCOPE

## 2.1 Phase 1 INCLUDES

- YouTube Music playlist ingestion through `ytmusicapi`.
- Preservation of playlist ordering.
- Permanent serial assignment.
- Two SQLite databases.
- Pending/completed/duplicate/error processing states.
- Direct download of the selected YTMusic source audio.
- Detailed source metadata acquisition using `yt-dlp` `info.json`.
- Artwork acquisition during the same initial `yt-dlp` run.
- ISRC extraction and normalization.
- ISRC-only duplicate detection.
- User-controlled duplicate resolution.
- YouTube official music-video search.
- Simple result filtering based only on the presence of `lyrics` in the result title.
- Selection of the first acceptable result.
- Final metadata normalization.
- Final ID3 tag writing with Mutagen.
- Artwork embedding with Mutagen.
- YouTube metadata embedding using custom ID3 `TXXX` frames.
- Final MP3 validation.
- SHA-256 file hashing.
- SQLite state tracking.
- Temporary working-directory cleanup.
- Recovery from errors through status tracking.

## 2.2 Phase 1 EXCLUDES

- Lyrics retrieval.
- Lyrics embedding.
- Demucs processing.
- Whisper transcription.
- MMS or other speech/audio models.
- Vocal/instrumental separation.
- Manual metadata editing UI.
- Fuzzy duplicate matching.
- Title/artist/duration duplicate matching.
- YouTube candidate scoring.
- YouTube candidate ranking.
- YouTube confidence scoring.
- Automatic editorial judgment about which video is "most official" beyond the specified search rule.

---

# 3. CORE DESIGN PRINCIPLES

## 3.1 Playlist Entry Identity

A playlist entry is a specific occurrence inside the playlist.

Its permanent identity is the serial number.

Example:

```text
001 -> Song A
002 -> Song B
003 -> Song A
```

`001` and `003` are two different playlist entries.

They may refer to the same recording, but they remain different playlist identities.

## 3.2 Serial Number Rules

The serial number:

1. Is assigned once.
2. Is assigned in the order returned by the playlist ingestion process.
3. Is never reused.
4. Is never changed.
5. Is never deleted from `playlist.db`.
6. Is not replaced by ISRC.
7. Is not replaced by YTM video ID.
8. Is used in `songs.db` when the playlist entry owns the current retained song.
9. Is used in the final MP3 filename.
10. Is used when linking physical files back to playlist entries.

## 3.3 Playlist Database vs Song Database

`playlist.db` answers:

> What entries exist in my playlist, and what is their processing state?

`songs.db` answers:

> Which playlist entries currently have retained downloaded songs, and what are the metadata and file details of those retained songs?

They are deliberately separate.

## 3.4 Duplicate Identity

Only ISRC is a duplicate key.

If ISRC is missing:

```text
isrc = NULL
```

No other duplicate matching is attempted.

## 3.5 Final Metadata Authority

`yt-dlp` obtains source material and source metadata.

`yt-dlp` does **not** write the final MP3 metadata.

Mutagen is the single authority for final ID3 metadata.

This prevents competing metadata writers.

---

# 4. SYSTEM ARCHITECTURE

```text
                       +----------------------+
                       | YouTube Music        |
                       | Playlist             |
                       +----------+-----------+
                                  |
                                  v
                       +----------------------+
                       | YTMusic API           |
                       | Playlist ingestion    |
                       +----------+-----------+
                                  |
                                  v
                       +----------------------+
                       | playlist.db           |
                       | Permanent serials     |
                       | Status                |
                       +----------+-----------+
                                  |
                                  v
                       +----------------------+
                       | Processing Queue      |
                       | Next pending serial   |
                       +----------+-----------+
                                  |
                                  v
                       +----------------------+
                       | yt-dlp                |
                       | ONE initial command   |
                       +----------+-----------+
                                  |
                   +--------------+--------------+
                   |              |              |
                   v              v              v
              master.mp3    master.info.json  master.jpg
                   |              |              |
                   +--------------+--------------+
                                  |
                                  v
                       +----------------------+
                       | Metadata Normalizer   |
                       +----------+-----------+
                                  |
                                  v
                       +----------------------+
                       | ISRC Duplicate Check |
                       | songs.db              |
                       +----------+-----------+
                                  |
                         +--------+--------+
                         |                 |
                         v                 v
                       unique          duplicate
                         |                 |
                         |            user decision
                         |                 |
                         +--------+--------+
                                  |
                                  v
                       +----------------------+
                       | YouTube Search       |
                       | title + album +      |
                       | official video song  |
                       +----------+-----------+
                                  |
                                  v
                       +----------------------+
                       | First result whose  |
                       | title lacks lyrics   |
                       +----------+-----------+
                                  |
                                  v
                       +----------------------+
                       | Metadata / Artwork   |
                       | preparation          |
                       +----------+-----------+
                                  |
                                  v
                       +----------------------+
                       | Mutagen              |
                       | Final ID3 writer     |
                       +----------+-----------+
                                  |
                                  v
                       +----------------------+
                       | Final MP3 validation |
                       +----------+-----------+
                                  |
                                  v
                       +----------------------+
                       | SHA-256              |
                       +----------+-----------+
                                  |
                                  v
                       +----------------------+
                       | Atomic finalization  |
                       +----------+-----------+
                                  |
                         +--------+--------+
                         |                 |
                         v                 v
                    songs.db         playlist.db
                                     status=completed
```

---

# 5. PROJECT DIRECTORY STRUCTURE

```text
phase1_project/
│
├── main.py                         # Application entry point
├── config.json                     # User configuration
├── cookies.txt                     # Optional YouTube cookies
├── requirements.txt                # Python dependencies
├── README.md                       # Project documentation
│
├── src/
│   ├── __init__.py
│   ├── db_playlist.py              # playlist.db schema and helpers
│   ├── db_songs.py                 # songs.db schema and helpers
│   ├── playlist_ingest.py          # YTM playlist ingestion
│   ├── downloader.py               # yt-dlp acquisition
│   ├── metadata.py                 # info.json extraction/normalization
│   ├── duplicate_checker.py        # ISRC-only duplicate logic
│   ├── youtube_finder.py           # simple YouTube search/filter
│   ├── embedder.py                 # Mutagen ID3 writer
│   ├── validator.py                # final MP3 validation
│   ├── hashing.py                  # SHA-256 calculation
│   └── pipeline.py                 # end-to-end orchestration
│
├── songs/
│   └── original/                   # Retained final MP3 files
│
├── temp/                            # Per-entry temporary working folders
│
└── db/
    ├── playlist.db
    └── songs.db
```

---

# 6. CONFIGURATION

Suggested `config.json`:

```json
{
    "ytmusic_playlist_id": "YOUR_PLAYLIST_ID",

    "paths": {
        "songs": "songs/original",
        "temp": "temp",
        "database": "db"
    },

    "download": {
        "audio_format": "mp3",
        "audio_quality": "0",
        "write_info_json": true,
        "write_thumbnail": true,
        "convert_thumbnail": "jpg"
    },

    "youtube_video_search": {
        "results_to_fetch": 10,
        "skip_title_keyword": "lyrics"
    },

    "retry": {
        "max_attempts": 3
    }
}
```

Configuration values must not change the architectural rules.

In particular:

- duplicate matching remains ISRC-only;
- YouTube result scoring remains disabled;
- `lyrics` remains the only search-result title exclusion keyword defined by Phase 1;
- final ID3 writing remains Mutagen-only.

---

# 7. REQUIRED SOFTWARE

The implementation requires:

```text
Python
ytmusicapi
yt-dlp
mutagen
requests
FFmpeg
FFprobe
```

The runtime should also include whatever JavaScript-runtime support is required by the installed `yt-dlp` version for current YouTube extraction.

Dependency versions should be pinned in `requirements.txt` once implementation begins.

Example structure:

```text
yt...==...
yt-dlp==...
mutagen==...
requests==...
```

The exact versions should be selected at implementation time and tested together rather than being casually mixed.

---

# 8. DATABASE SCHEMA — `playlist.db`

## 8.1 Table

```sql
CREATE TABLE IF NOT EXISTS playlist_entries (
    serial_number INTEGER PRIMARY KEY,

    playlist_position INTEGER NOT NULL,

    ytm_video_id TEXT NOT NULL,
    ytm_url TEXT NOT NULL,

    title TEXT NOT NULL,
    artist TEXT NOT NULL,
    duration INTEGER,

    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (
            status IN (
                'pending',
                'completed',
                'duplicate',
                'error'
            )
        ),

    error_message TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 8.2 Why `ytm_video_id` is not UNIQUE

The same YTMusic track can appear more than once in a playlist.

Example:

```text
001 | Song A
002 | Song B
003 | Song A
```

Both `001` and `003` must survive as separate playlist entries.

Therefore:

```text
ytm_video_id -> not the permanent identity
serial_number -> permanent identity
```

## 8.3 `playlist_position`

`playlist_position` records the position returned by the playlist ingestion.

It is deliberately different from `serial_number`.

The serial is permanent.

The position describes playlist order.

This allows the project to preserve identity while still recording ordering information.

---

# 9. DATABASE SCHEMA — `songs.db`

## 9.1 Table

```sql
CREATE TABLE IF NOT EXISTS songs (
    serial_number INTEGER PRIMARY KEY,

    -- Core song metadata
    title TEXT NOT NULL,
    title_original TEXT,

    primary_artist TEXT,
    artist TEXT,
    artists_json TEXT,
    album TEXT,
    album_artist TEXT,

    -- Dates
    release_date TEXT,
    release_date_source TEXT,
    upload_date TEXT,

    -- Music identifiers
    isrc TEXT,
    isrc_source TEXT,

    -- Audio information
    duration INTEGER,
    source_duration INTEGER,
    source_codec TEXT,
    source_bitrate INTEGER,
    source_sample_rate INTEGER,
    source_channels INTEGER,

    -- Original YouTube Music source
    ytm_video_id TEXT,
    ytm_url TEXT,

    -- Final retained file
    mp3_path TEXT NOT NULL,
    mp3_size INTEGER,
    mp3_sha256 TEXT,

    -- Selected YouTube music video
    yt_video_id TEXT,
    yt_video_url TEXT,
    yt_video_title TEXT,
    yt_video_channel TEXT,
    yt_video_channel_id TEXT,
    yt_video_views INTEGER,
    yt_video_published_at TEXT,

    -- Search method
    yt_video_match_method TEXT,

    -- Working/source artwork path when retained in metadata
    artwork_path TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 9.2 ISRC Index

```sql
CREATE INDEX IF NOT EXISTS idx_songs_isrc
ON songs(isrc)
WHERE isrc IS NOT NULL;
```

Only non-NULL ISRC values are indexed for duplicate detection.

---

# 10. DATABASE INVARIANTS

The implementation must maintain these rules at all times after a successful commit.

## 10.1 Serial uniqueness

A serial appears at most once in `playlist.db`.

A serial appears at most once in `songs.db`.

## 10.2 Completed relationship

If:

```text
playlist.db.status = completed
```

then there must be:

```text
songs.db.serial_number = same serial
```

and the referenced MP3 must exist and be valid.

## 10.3 Duplicate relationship

If:

```text
playlist.db.status = duplicate
```

then that playlist entry does not own a retained song row in `songs.db`.

## 10.4 Pending relationship

If:

```text
playlist.db.status = pending
```

then it should not currently have a retained `songs.db` row for that serial.

## 10.5 Error relationship

If:

```text
playlist.db.status = error
```

there is no requirement for a retained `songs.db` row for that serial.

---

# 11. STATUS STATE MACHINE

The basic state machine is:

```text
                 +-----------+
                 |  pending  |
                 +-----+-----+
                       |
                 start processing
                       |
                       v
               download/process
                       |
          +------------+-------------+
          |                          |
          v                          v
       success                    failure
          |                          |
          v                          v
     duplicate check              error
          |                          |
    +-----+------+                   |
    |            |                   |
    v            v                   |
  unique      duplicate              |
    |            |                   |
    |        user decision           |
    |         /       \              |
    |        v         v             |
    |   previous     current         |
    |      |           |             |
    |      v           v             |
    |  duplicate   completed         |
    |                  |             |
    v                  |             |
 completed <-----------+-------------+
```

Additional transition:

```text
old completed entry
       |
 current duplicate chooses "keep current"
       |
       v
old entry -> pending
current entry -> completed
```

And retry:

```text
error -> pending
```

---

# 12. STEP 1 — PLAYLIST INGESTION

## 12.1 Read configuration

Read:

```text
yt...music_playlist_id
```

from `config.json`.

## 12.2 Initialize YTMusic

Create the `ytmusicapi.YTMusic` client.

Cookies/authentication may be supplied according to the local configuration if required by the environment.

## 12.3 Retrieve playlist

Retrieve the complete playlist using the YTMusic API.

The project must preserve the order returned by the API.

Do not sort alphabetically.

Do not sort by artist.

Do not sort by duration.

Do not sort by popularity.

Do not sort by ISRC.

The playlist order is authoritative for initial serial assignment.

## 12.4 Extract entry fields

For each returned track, extract at minimum:

```text
video_id
song title
artist(s)
duration
```

Construct:

```text
https://music.youtube.com/watch?v={video_id}
```

## 12.5 Assign serials

Assign serial numbers sequentially in the ingestion order.

Example:

```text
API order:
1. Song A
2. Song B
3. Song C
4. Song D

serials:
001 -> Song A
002 -> Song B
003 -> Song C
004 -> Song D
```

The serial is stored as an integer in SQLite. Zero-padding is a filename/display convention, not a numeric database requirement.

## 12.6 Initial status

New entries receive:

```text
status = pending
```

## 12.7 Existing database behavior

When the application is restarted, existing playlist entries must not be assigned new serials.

Existing serials remain unchanged.

New playlist entries can receive new serials according to the project's append-only serial-allocation policy.

The implementation must never recycle a previously used serial.

## 12.8 Ingestion summary

Print a summary such as:

```text
Playlist ingestion complete.

Total playlist entries: 120
New entries:            14
Existing entries:       106
Pending entries:        12
Completed entries:      91
Duplicate entries:      2
Error entries:          1
```

---

# 13. STEP 2 — SELECT NEXT PENDING ENTRY

Query `playlist.db` for the next entry where:

```text
status = pending
```

Process in playlist order.

Conceptually:

```sql
SELECT *
FROM playlist_entries
WHERE status = 'pending'
ORDER BY playlist_position ASC, serial_number ASC
LIMIT 1;
```

The serial returned becomes the active processing identity.

Example:

```text
003 | Song C | pending
```

The processing directory becomes:

```text
temp/003/
```

---

# 14. STEP 3 — CREATE WORKING DIRECTORY

Create:

```text
temp/{serial_number}/
```

Example:

```text
temp/003/
```

Everything generated for the current processing attempt belongs inside this directory until finalization.

Expected temporary files after acquisition:

```text
temp/003/
├── master.mp3
├── master.info.json
└── master.jpg
```

Additional yt-dlp/FFmpeg temporary files may exist during execution but should be cleaned after successful completion or failure handling.

---

# 15. STEP 4 — ONE COMPLETE YT-DLP ACQUISITION

This step intentionally acquires everything needed from the YTMusic source in one `yt-dlp` operation.

The command is conceptually:

```bash
yt-dlp \
    -x \
    --audio-format mp3 \
    --audio-quality 0 \
    --write-info-json \
    --write-thumbnail \
    --convert-thumbnails jpg \
    -o "temp/{serial_number}/master.%(ext)s" \
    "{ytm_url}"
```

The exact command-line details may be adjusted during implementation to match the installed `yt-dlp`/FFmpeg environment, but the behavior must remain the same.

## 15.1 Acquisition requirements

The single initial command must obtain:

### A. Audio

The exact selected YTMusic source audio.

### B. Complete source metadata

`master.info.json` containing the complete metadata returned by yt-dlp.

### C. Artwork

The highest-quality available thumbnail/artwork selected by yt-dlp from the source.

## 15.2 No general YouTube audio search

The audio is not found by searching general YouTube.

The source audio URL is the stored YTMusic URL belonging to the selected playlist entry.

## 15.3 No `--add-metadata`

Do **not** use:

```text
--add-metadata
```

The initial yt-dlp output is an acquisition artifact, not the final tagged library file.

## 15.4 Why there is no `--add-metadata`

The project intentionally has one final metadata authority:

```text
yt-dlp -> acquisition
Mutagen -> final MP3 metadata
```

This avoids having yt-dlp write one version of tags and Mutagen later overwrite another version.

---

# 16. EXPECTED INITIAL ACQUISITION RESULT

After a successful acquisition:

```text
temp/003/
├── master.mp3
├── master.info.json
└── master.jpg
```

## `master.mp3`

Contains the acquired audio.

It is not yet considered the final library MP3.

## `master.info.json`

Contains the source metadata.

It is parsed by Python.

## `master.jpg`

Contains the acquired artwork.

It is used later by Mutagen.

No second artwork download is performed.

---

# 17. STEP 5 — SOURCE ACQUISITION VALIDATION

Before proceeding, validate the source package.

## 17.1 Required checks

- `master.mp3` exists.
- `master.info.json` exists.
- `master.info.json` is valid JSON.
- `master.mp3` can be opened/read.
- Audio duration can be obtained.
- `master.jpg` exists when the source supplied usable artwork.
- `master.jpg` can be decoded as an image.

## 17.2 Failure

If a required acquisition item is invalid:

1. record the error;
2. set the playlist entry to `error`;
3. do not insert a `songs.db` row;
4. preserve the serial;
5. allow later retry by moving the entry back to `pending`.

---

# 18. STEP 6 — READ `master.info.json`

Parse the complete JSON object.

Do not throw away the source information before the normalized metadata has been built.

The parser should be defensive because individual fields can be absent or `null`.

Important fields to inspect include:

```text
title
artist
artists
album
album_artist
release_date
upload_date
duration
isrc
description
uploader
channel
channel_id
view_count
thumbnails
codec / format data
abr / bitrate
asr / sample rate
channels
```

The exact names/availability depend on the returned yt-dlp metadata.

---

# 19. STEP 7 — METADATA LAYERS

The system should conceptually maintain three metadata layers.

## Layer A — Raw source metadata

Exactly what is supplied by `master.info.json`.

## Layer B — Normalized application metadata

Cleaned fields that are suitable for databases and final tagging.

Examples:

```text
normalized_title
normalized_artist
normalized_album
normalized_isrc
normalized_release_date
```

## Layer C — Final MP3 metadata

The exact ID3 frames written by Mutagen.

This separation makes the system easier to debug.

---

# 20. STEP 8 — CORE SONG METADATA

Extract, where available:

```text
title
title_original
primary_artist
artist
artists_json
album
album_artist
```

## 20.1 Title

`title` is the cleaned display title.

`title_original` preserves the original source title when useful.

## 20.2 Artist

`artist` is the display string written to the main artist field.

`artists_json` can preserve multiple artist contributors without flattening information unnecessarily.

Example:

```json
[
  "Artist A",
  "Artist B"
]
```

## 20.3 Album

Store the album exactly when supplied.

If unavailable:

```text
album = NULL
```

## 20.4 Album Artist

Store album artist separately from track artist when available.

---

# 21. STEP 9 — DATE METADATA

Store:

```text
release_date
release_date_source
upload_date
```

Do not silently treat upload date as release date.

If a real release date is unavailable:

```text
release_date = NULL
```

The source upload date remains separately available as `upload_date`.

---

# 22. STEP 10 — ISRC EXTRACTION

ISRC is extracted from the structured metadata when available.

The application may normalize the representation, for example by trimming whitespace and normalizing case.

If no ISRC is available:

```text
isrc = NULL
isrc_source = NULL
```

Do not invent one.

Do not infer one from unrelated metadata.

Do not generate an internal pseudo-ISRC.

---

# 23. ISRC-ONLY DUPLICATE RULE

This is a locked design rule.

The duplicate checker must only do:

```text
current.isrc != NULL
        |
        v
find songs.db where songs.isrc == current.isrc
```

No other duplicate heuristic is permitted.

Do NOT duplicate-match using:

- title;
- artist;
- album;
- duration;
- YTM video ID;
- YouTube video ID;
- filename;
- audio hash;
- fuzzy title similarity;
- normalized artist/title combinations.

If `isrc = NULL`, the song is simply treated as having no ISRC-based duplicate match.

---

# 24. STEP 11 — DUPLICATE SEARCH

Example current entry:

```text
Serial: 004
Title: Song A
Artist: Artist A
ISRC: USABC1234567
```

Query:

```sql
SELECT *
FROM songs
WHERE isrc = ?
LIMIT 1;
```

If there is no row:

```text
unique -> continue
```

If there is a row:

```text
duplicate -> ask user
```

If the current ISRC is `NULL`:

```text
no duplicate check
```

---

# 25. STEP 12 — DUPLICATE USER DECISION

When a duplicate exists, show both entries clearly.

Example:

```text
DUPLICATE DETECTED

CURRENT ENTRY
Serial: 004
Title: Song A
Artist: Artist A
Album: Album X
ISRC: USABC1234567

EXISTING RETAINED ENTRY
Serial: 001
Title: Song A
Artist: Artist A
Album: Album X
ISRC: USABC1234567

Choose:

1. Keep previous
2. Keep current
```

No automatic winner is chosen.

---

# 26. DUPLICATE OPTION 1 — KEEP PREVIOUS

User selects:

```text
1
```

Actions:

1. Do not modify the previous retained song.
2. Do not delete the previous MP3.
3. Do not modify its `songs.db` row.
4. Delete the current temporary acquisition:
   - `master.mp3`;
   - `master.info.json`;
   - `master.jpg`;
   - any other temporary files.
5. Do not create a current `songs.db` row.
6. Set the current playlist entry to:

```text
status = duplicate
```

Example:

```text
playlist.db

001 | Song A | completed
004 | Song A | duplicate
```

`songs.db`:

```text
001 | Song A
```

Serial `004` remains permanently present in `playlist.db`.

---

# 27. DUPLICATE OPTION 2 — KEEP CURRENT

User selects:

```text
2
```

The current playlist entry becomes the retained song.

Actions:

1. Identify the previous `songs.db` row.
2. Read its `mp3_path`.
3. Delete the previous physical MP3.
4. Delete the previous row from `songs.db`.
5. Continue processing the current temporary acquisition.
6. Search YouTube for the current entry.
7. Build the current final MP3.
8. Validate it.
9. Insert current serial into `songs.db`.
10. Set current playlist entry to `completed`.
11. Set previous playlist entry to `pending`.

Example before:

```text
playlist.db

001 | Song A | completed
004 | Song A | pending
```

`songs.db`:

```text
001 | Song A
```

After choosing current:

```text
playlist.db

001 | Song A | pending
004 | Song A | completed
```

`songs.db`:

```text
004 | Song A
```

The old playlist entry `001` remains permanently assigned to serial `001`.

---

# 28. IMPORTANT DUPLICATE BEHAVIOR

A duplicate decision changes the retained song record, not playlist identity.

The system never does:

```text
rename serial 001 to 004
```

It instead does:

```text
remove retained song 001
retain playlist entry 001 as pending
retain song 004
```

This preserves the playlist history/identity while allowing the currently retained recording to move to the playlist entry chosen by the user.

---

# 29. STEP 13 — YOUTUBE OFFICIAL MUSIC VIDEO SEARCH

After the song has been acquired and duplicate handling has been resolved, perform the YouTube search.

The exact search string is:

```text
{title} {album_name} official video song
```

Use the normalized/current song title and album name being used for enrichment.

If the album is missing, the implementation should follow the exact established query construction rules used by the application rather than inventing a new search strategy.

---

# 30. NO SEARCH SCORING

The video finder must NOT:

- calculate a candidate score;
- compare view counts;
- compare durations;
- compare channels;
- calculate title similarity;
- calculate artist similarity;
- calculate confidence;
- rank candidate videos after retrieval;
- choose the most viewed result;
- choose the closest duration result.

The returned order is authoritative for this Phase 1 selection method.

---

# 31. STEP 14 — YOUTUBE RESULT FILTERING

Retrieve the search results in their returned order.

For each result:

1. Read its title.
2. Convert the title to a case-insensitive comparison form.
3. If the title contains the word:

```text
lyrics
```

skip that result.

4. Otherwise select it immediately.

Example:

```text
1. Song Name - Lyrics Video
2. Song Name - Official Video
3. Song Name - Live Performance
```

Result 1:

```text
lyrics -> skip
```

Result 2:

```text
no lyrics -> select immediately
```

Result 3 is never considered after selection.

---

# 32. NO ACCEPTABLE YOUTUBE RESULT

If all returned results contain `lyrics`, then no acceptable video is selected.

Store:

```text
yt_video_id = NULL
yt_video_url = NULL
yt_video_title = NULL
yt_video_channel = NULL
yt_video_channel_id = NULL
yt_video_views = NULL
yt_video_published_at = NULL
yt_video_match_method = NULL
```

The song can still be successfully completed.

Failure to find an acceptable video is **not** a failure of the song download.

---

# 33. STEP 15 — FETCH SELECTED YOUTUBE VIDEO METADATA

For the selected result, retrieve/store:

```text
yt_video_id
yt_video_url
yt_video_title
yt_video_channel
yt_video_channel_id
yt_video_views
yt_video_published_at
```

Set:

```text
yt_video_match_method = youtube_search
```

No score or confidence field is needed.

---

# 34. STEP 16 — ARTWORK HANDLING

The artwork is already available from the initial yt-dlp command:

```text
temp/{serial_number}/master.jpg
```

Do not download artwork again.

Do not perform a second yt-dlp command just for artwork.

Do not fetch another image source unless the implementation explicitly establishes that the initial acquisition failed to produce usable artwork and a separate fallback is added later as a deliberate scope change.

For the current Phase 1 specification, the intended artwork source is `master.jpg` from the initial acquisition.

---

# 35. STEP 17 — FINAL FILENAME

The final MP3 filename uses the permanent serial number.

Format:

```text
{serial:03d}_{safe_title}_{safe_artist}.mp3
```

Example:

```text
004_Song_A_Artist_A.mp3
```

Directory:

```text
songs/original/
```

Full path:

```text
songs/original/004_Song_A_Artist_A.mp3
```

Filename sanitization must remove or replace filesystem-invalid characters while preserving as much readable information as possible.

The serial number must never be removed.

---

# 36. STEP 18 — FINAL MP3 BUILD STRATEGY

The initial `master.mp3` is the acquired audio source.

The final output should be created as a temporary production file:

```text
songs/original/004_Song_A_Artist_A.mp3.tmp
```

The final metadata-writing stage then writes all desired tags into that file.

After validation:

```text
.mp3.tmp
    |
    | atomic rename
    v
.mp3
```

---

# 37. FINAL METADATA WRITER — MUTAGEN ONLY

Mutagen is the sole final metadata writer.

No `yt-dlp --add-metadata`.

No second metadata utility should overwrite the final tags after Mutagen.

The logical sequence is:

```text
source acquisition
    -> raw metadata
    -> normalization
    -> build final MP3
    -> Mutagen ID3 write
    -> artwork APIC write
    -> custom TXXX write
    -> save
    -> reopen
    -> validate
```

---

# 38. STANDARD ID3 FIELDS

The final MP3 should contain, when values are available:

```text
TIT2 -> Title
TPE1 -> Primary Artist / Track Artist
TPE2 -> Album Artist
TALB -> Album
TDRC -> Release Date
TRCK -> Album Track Number, when actually known
TSRC -> ISRC, when available
```

Do not use playlist serial number as `TRCK`.

The serial number is playlist identity, not album track numbering.

---

# 39. PLAYLIST-SPECIFIC CUSTOM FIELDS

The final MP3 may include playlist/source identity using `TXXX` frames.

Recommended fields:

```text
TXXX:serial_number
TXXX:playlist_position
TXXX:ytm_video_id
TXXX:ytm_url
```

These fields preserve playlist context inside the MP3.

---

# 40. YOUTUBE MUSIC VIDEO CUSTOM FIELDS

Embed selected video details using `TXXX` frames:

```text
TXXX:yt_video_id
TXXX:yt_video_url
TXXX:yt_video_title
TXXX:yt_video_channel
TXXX:yt_video_channel_id
TXXX:yt_video_views
TXXX:yt_video_published_at
```

If no acceptable video is found, those fields should be omitted or left absent rather than being filled with fake values.

---

# 41. ISRC TAGGING

If ISRC exists:

```text
TSRC = normalized ISRC
```

If ISRC is `NULL`:

```text
TSRC is omitted
```

Do not write the string `NULL` into `TSRC`.

---

# 42. ARTWORK EMBEDDING

Use:

```text
temp/{serial_number}/master.jpg
```

Embed it as the front-cover artwork using the ID3 `APIC` frame.

Recommended:

```text
type = 3
```

for front cover.

The artwork becomes physically embedded in the final MP3.

The final MP3 therefore remains usable without the original temporary artwork file.

---

# 43. SOURCE DESCRIPTION

If desired and technically practical, the source description can be stored in a `COMM` frame.

Example:

```text
COMM -> source description
```

Do not blindly embed extremely large or unsuitable text if it would create unnecessary file bloat.

The structured metadata remains in `songs.db`.

---

# 44. STEP 19 — FINAL MP3 VALIDATION

Validation must happen after all final metadata and artwork have been written.

Do not validate only the original `master.mp3`.

The final validation target is:

```text
songs/original/{serial}_{title}_{artist}.mp3.tmp
```

before its atomic rename.

Required checks:

1. File exists.
2. File size is greater than zero.
3. MP3 can be opened.
4. Audio duration can be read.
5. Title tag exists.
6. Artist tag exists.
7. Album tag exists when source metadata supplied it.
8. Release-date tag is valid when present.
9. ISRC is present when expected.
10. ISRC is omitted when source ISRC is `NULL`.
11. Artwork exists inside the final MP3.
12. Artwork can be decoded/read.
13. YouTube fields are correct when a video was found.
14. YouTube fields are absent/empty when no acceptable video was found.
15. The file is readable after closing and reopening it.

---

# 45. STEP 20 — FINAL FILE HASH

After all metadata and artwork have been written and validation succeeds, calculate:

```text
SHA-256(final MP3 bytes)
```

Store:

```text
mp3_size
mp3_sha256
```

The hash must be calculated on the **final fully tagged MP3**, not `master.mp3`.

If metadata is changed later, the file hash will legitimately change.

---

# 46. STEP 21 — ATOMIC FINALIZATION

The finalization sequence should be:

```text
1. Acquire source
2. Extract metadata
3. Resolve duplicate
4. Find YouTube video
5. Prepare final MP3
6. Write Mutagen tags
7. Embed artwork
8. Save temporary final MP3
9. Reopen final MP3
10. Validate final MP3
11. Calculate file size
12. Calculate SHA-256
13. Rename .tmp -> final .mp3
14. Insert/update songs.db
15. Update playlist.db
16. Delete temp directory
```

The physical final rename should occur only after the final MP3 passes validation.

---

# 47. STEP 22 — `songs.db` COMMIT

For a unique/non-duplicate song:

```text
songs.db
INSERT current serial
```

Store all normalized metadata and final file information.

Example conceptual row:

```text
serial_number      = 004
isrc               = USABC1234567
title              = Song A
artist             = Artist A
album              = Album X
release_date       = 2025-01-01
duration           = 243
mp3_path           = songs/original/004_Song_A_Artist_A.mp3
mp3_size           = 8123456
mp3_sha256         = ...
ytm_video_id       = ...
yt_video_id        = ...
yt_video_title     = ...
yt_video_channel   = ...
```

Then:

```text
playlist.db status = completed
```

---

# 48. STEP 23 — SUCCESSFUL COMPLETION

A song is considered successfully completed only when all of the following are true:

- source acquisition succeeded;
- source metadata was successfully parsed;
- duplicate logic was resolved;
- YouTube search completed or was intentionally left without a match;
- artwork handling completed;
- final MP3 was built;
- Mutagen metadata write succeeded;
- final MP3 validation succeeded;
- SHA-256 was calculated;
- final MP3 was atomically finalized;
- `songs.db` commit succeeded;
- `playlist.db` status was updated to `completed`;
- temporary files can be safely deleted.

---

# 49. STEP 24 — ERROR HANDLING

Any unrecoverable processing failure should result in:

```text
playlist.db.status = error
```

and:

```text
playlist.db.error_message = descriptive error
```

The serial remains unchanged.

No serial is reused.

No playlist entry is deleted.

If a final MP3 was only partially created, it must not be registered as a completed `songs.db` record.

Incomplete `.tmp` output must be cleaned or explicitly handled during the next recovery run.

---

# 50. RETRY MODEL

An entry with:

```text
status = error
```

can be returned to:

```text
status = pending
```

for another processing attempt.

The implementation may track retry count separately if desired.

The serial never changes.

---

# 51. TEMP DIRECTORY CLEANUP

For serial `004`:

```text
temp/004/
```

is removed only after finalization succeeds.

Expected cleanup removes:

```text
master.mp3
master.info.json
master.jpg
any other temporary artifacts
```

The retained production MP3 remains:

```text
songs/original/004_....mp3
```

---

# 52. NORMAL NON-DUPLICATE END-TO-END EXAMPLE

Playlist entry:

```text
Serial: 004
Title: Song A
Artist: Artist A
Album: Album X
Status: pending
```

## Acquisition

```text
temp/004/
├── master.mp3
├── master.info.json
└── master.jpg
```

## Metadata extraction

```text
isrc = USABC1234567
```

## Duplicate lookup

No existing `songs.db` row has that ISRC.

## YouTube search

```text
Song A Album X official video song
```

Results:

```text
1. Song A Lyrics Video
2. Song A Official Video
```

Result 1 is skipped.

Result 2 is selected.

## Final MP3

```text
songs/original/004_Song_A_Artist_A.mp3
```

Mutagen writes:

```text
TIT2
TPE1
TPE2
TALB
TDRC
TSRC
APIC
TXXX:serial_number
TXXX:playlist_position
TXXX:ytm_video_id
TXXX:ytm_url
TXXX:yt_video_id
TXXX:yt_video_url
TXXX:yt_video_title
TXXX:yt_video_channel
...
```

## Final result

```text
playlist.db
004 | completed
```

```text
songs.db
004 | Song A | USABC1234567 | songs/original/004_Song_A_Artist_A.mp3
```

---

# 53. DUPLICATE — KEEP PREVIOUS EXAMPLE

Existing:

```text
playlist.db
001 | Song A | completed
004 | Song A | pending
```

`songs.db`:

```text
001 | Song A | USABC1234567
```

Serial `004` is downloaded.

Its ISRC is:

```text
USABC1234567
```

Duplicate found.

User selects:

```text
1. Keep previous
```

Actions:

```text
Delete temp/004/
Keep songs.db/001
Keep MP3 001
Set playlist 004 -> duplicate
```

Final:

```text
playlist.db
001 | completed
004 | duplicate
```

```text
songs.db
001 | Song A
```

---

# 54. DUPLICATE — KEEP CURRENT EXAMPLE

Existing:

```text
playlist.db
001 | Song A | completed
004 | Song A | pending
```

`songs.db`:

```text
001 | Song A | USABC1234567
```

Serial `004` is downloaded.

Its ISRC matches `001`.

User selects:

```text
2. Keep current
```

Actions:

```text
Delete MP3 belonging to 001
Delete songs.db row 001
Finish processing serial 004
Create final MP3 004
Insert songs.db row 004
Set playlist 004 -> completed
Set playlist 001 -> pending
```

Final:

```text
playlist.db
001 | pending
004 | completed
```

```text
songs.db
004 | Song A
```

Serial `001` remains permanent and available for future processing.

---

# 55. MISSING ISRC EXAMPLE

Suppose:

```text
serial = 005
isrc = NULL
```

The system does:

```text
No ISRC
   |
   v
No songs.db duplicate lookup
   |
   v
Continue normally
```

If the song is successfully finalized:

```text
playlist.db
005 | completed
```

and:

```text
songs.db
005 | isrc = NULL
```

Do not write the literal string `NULL` into the MP3 `TSRC` field.

Do not perform title/artist fallback matching.

---

# 56. YOUTUBE SEARCH EXAMPLE

For:

```text
Title = Song A
Album = Album X
```

Search exactly:

```text
Song A Album X official video song
```

Returned:

```text
1. Song A Lyrics Video
2. Song A Official Video
3. Song A Live
4. Song A Cover
```

Processing:

```text
1 -> contains lyrics -> skip
2 -> does not contain lyrics -> select
3 -> not examined
4 -> not examined
```

No view count is compared.

No duration is compared.

No channel is compared.

---

# 57. FILE NAMING RULES

## Final MP3

```text
{serial:03d}_{safe_title}_{safe_artist}.mp3
```

## Temporary working directory

```text
temp/{serial}/
```

## Temporary final file

```text
songs/original/{serial}_{safe_title}_{safe_artist}.mp3.tmp
```

The serial must always be included.

---

# 58. FILESYSTEM SAFETY

Filename sanitization must:

- remove filesystem-invalid characters;
- prevent unintended directory traversal;
- avoid accidental reserved filenames;
- preserve the serial prefix;
- preserve readable title and artist text where possible.

The sanitized filename must never change the database identity.

---

# 59. DATABASE SAFETY

The implementation should use transactions for state changes that must remain consistent.

Examples:

### Normal completion

```text
BEGIN TRANSACTION
    INSERT songs.db row
    UPDATE playlist.db status = completed
COMMIT
```

### Keep previous duplicate

```text
BEGIN TRANSACTION
    UPDATE playlist.db current serial = duplicate
COMMIT
```

### Keep current duplicate

```text
BEGIN TRANSACTION
    DELETE songs.db previous serial
    INSERT songs.db current serial
    UPDATE playlist.db previous serial = pending
    UPDATE playlist.db current serial = completed
COMMIT
```

Filesystem deletions should be coordinated carefully with database transactions because SQLite transactions cannot roll back a physical file deletion.

Therefore, the implementation should structure operations so that a final valid file exists before a successful database commit whenever possible.

---

# 60. KEEP-CURRENT DUPLICATE SAFETY

The most sensitive operation is replacing the existing retained song.

The implementation should not delete the old MP3 until the current song has successfully passed final validation.

Preferred sequence:

```text
1. Current download exists.
2. Current metadata is valid.
3. Current duplicate is confirmed.
4. User chooses current.
5. Current final MP3 is fully built and validated.
6. Current file is ready.
7. Old retained file is removed.
8. Old songs.db row is removed.
9. Current songs.db row is inserted.
10. Current playlist entry becomes completed.
11. Old playlist entry becomes pending.
```

The important principle is:

> Never destroy the previously retained song merely because the replacement download started; replace it only after the new song is valid.

---

# 61. MUTAGEN IMPLEMENTATION RESPONSIBILITY

The embedder module should be the single place responsible for writing final ID3 metadata.

Suggested API concept:

```python
embed_final_mp3(
    source_mp3,
    output_mp3,
    metadata,
    artwork_path,
)
```

It should:

1. open/create ID3 tags;
2. remove or replace the intended application-managed fields;
3. write standard ID3 frames;
4. write custom `TXXX` frames;
5. embed the front-cover `APIC` frame;
6. save;
7. close/reopen if needed for validation.

Do not scatter final tag-writing logic across unrelated modules.

---

# 62. METADATA FIELD OWNERSHIP

## Source-owned

Obtained from yt-dlp/YTMusic:

```text
title
artist
album
duration
release date
upload date
ISRC
source audio information
source video/source IDs
source descriptions
thumbnails
```

## Search-owned

Obtained from the selected YouTube result:

```text
yt_video_id
yt_video_url
yt_video_title
yt_video_channel
yt_video_channel_id
yt_video_views
yt_video_published_at
```

## Application-owned

Generated by the project:

```text
serial_number
playlist_position
status
mp3_path
mp3_size
mp3_sha256
yt_video_match_method
```

---

# 63. SOURCE VS FINAL MP3

The following distinction is important:

```text
master.mp3
```

is the temporary acquired audio.

```text
songs/original/004_....mp3
```

is the final application-owned MP3.

The final MP3 is the file that:

- contains final tags;
- contains embedded artwork;
- contains custom YouTube fields;
- receives the SHA-256 hash;
- is referenced by `songs.db`;
- survives temporary cleanup.

---

# 64. PIPELINE MODULE RESPONSIBILITIES

## `main.py`

Application entry point.

Responsibilities:

- load configuration;
- initialize directories;
- initialize databases;
- start ingestion/processing;
- handle top-level errors.

## `db_playlist.py`

Responsibilities:

- create `playlist.db` schema;
- insert playlist entries;
- allocate/query serials;
- update statuses;
- store errors.

## `db_songs.py`

Responsibilities:

- create `songs.db` schema;
- insert/update/delete song records;
- search by ISRC;
- retrieve retained-song file paths.

## `playlist_ingest.py`

Responsibilities:

- call YTMusic playlist API;
- preserve returned order;
- extract playlist metadata;
- assign serials;
- populate `playlist.db`.

## `downloader.py`

Responsibilities:

- build the single yt-dlp acquisition command;
- execute it;
- locate `master.mp3`;
- locate `master.info.json`;
- locate `master.jpg`;
- validate acquisition output.

## `metadata.py`

Responsibilities:

- parse `master.info.json`;
- normalize metadata;
- extract ISRC;
- derive final structured metadata object.

## `duplicate_checker.py`

Responsibilities:

- accept normalized ISRC;
- query `songs.db` by ISRC;
- trigger duplicate decision when a match exists;
- perform no fallback matching.

## `youtube_finder.py`

Responsibilities:

- construct exact search query;
- retrieve results;
- skip results whose title contains `lyrics`;
- select first remaining result;
- retrieve selected video metadata.

## `embedder.py`

Responsibilities:

- create final MP3 tags;
- embed artwork;
- write custom TXXX fields;
- save final MP3.

## `validator.py`

Responsibilities:

- reopen final MP3;
- validate audio;
- validate tags;
- validate artwork;
- validate expected custom metadata.

## `hashing.py`

Responsibilities:

- calculate SHA-256 of final MP3;
- return byte size and digest.

## `pipeline.py`

Responsibilities:

- orchestrate each stage;
- enforce state transitions;
- coordinate duplicate decisions;
- coordinate finalization;
- guarantee cleanup.

---

# 65. DETAILED SINGLE-SONG EXECUTION ORDER

For one serial, the exact high-level implementation order is:

```text
1. Load playlist row.
2. Confirm status = pending.
3. Create temp/{serial}/.
4. Execute one yt-dlp acquisition.
5. Validate master.mp3/info.json/artwork.
6. Parse info.json.
7. Normalize title/artist/album/dates/ISRC/audio metadata.
8. If ISRC is non-NULL, query songs.db.
9. If duplicate exists, ask user.
10. If user keeps previous:
       delete temp
       mark current duplicate
       finish this serial
11. If user keeps current:
       keep current temporary source
       prepare current final MP3
       only after current is valid, remove old retained MP3
       replace old songs.db record
       mark old playlist entry pending
12. Build YouTube search query.
13. Retrieve YouTube results.
14. Walk results in returned order.
15. Skip titles containing lyrics.
16. Select first remaining result.
17. Retrieve selected video metadata.
18. Use existing master.jpg.
19. Create final .mp3.tmp.
20. Write all final ID3 metadata with Mutagen.
21. Embed APIC artwork with Mutagen.
22. Save.
23. Reopen final file.
24. Validate audio and metadata.
25. Calculate SHA-256 and file size.
26. Atomically rename .tmp -> .mp3.
27. Insert songs.db row.
28. Update playlist.db to completed.
29. Delete temp/{serial}/.
30. Move to next pending playlist entry.
```

---

# 66. COMPLETE PROJECT PIPELINE — EXPANDED

```text
┌──────────────────────────────────────────────────────────────┐
│                    YOUTUBE MUSIC PLAYLIST                   │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               v
┌──────────────────────────────────────────────────────────────┐
│                     YTMUSIC API INGESTION                    │
│                                                              │
│ - read playlist ID                                           │
│ - retrieve complete playlist                                 │
│ - preserve returned/default order                            │
│ - extract video ID/title/artists/duration                    │
│ - assign permanent serial number                             │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               v
┌──────────────────────────────────────────────────────────────┐
│                         playlist.db                           │
│                                                              │
│ serial | position | YTM ID | title | artist | status       │
│                                                              │
│ status = pending                                              │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               v
┌──────────────────────────────────────────────────────────────┐
│                  SELECT NEXT PENDING ENTRY                   │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               v
┌──────────────────────────────────────────────────────────────┐
│                   temp/{serial_number}/                      │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               v
┌──────────────────────────────────────────────────────────────┐
│                   ONE COMPLETE YT-DLP RUN                    │
│                                                              │
│                         yt-dlp                               │
│                                                              │
│                    -x / MP3                                  │
│                    info.json                                 │
│                    thumbnail/artwork                         │
│                                                              │
│                 NO --add-metadata                             │
└───────────────┬────────────────┬────────────────┬────────────┘
                │                │                │
                v                v                v
          master.mp3      master.info.json    master.jpg
                │                │                │
                └────────────────┼────────────────┘
                                 │
                                 v
┌──────────────────────────────────────────────────────────────┐
│                     SOURCE VALIDATION                        │
│                                                              │
│ - audio exists                                              │
│ - JSON valid                                                 │
│ - artwork readable                                           │
│ - duration readable                                          │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               v
┌──────────────────────────────────────────────────────────────┐
│                   METADATA EXTRACTION                        │
│                                                              │
│ title / artists / album / dates / duration                  │
│ ISRC / source audio / source IDs / description              │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               v
┌──────────────────────────────────────────────────────────────┐
│                    METADATA NORMALIZATION                    │
│                                                              │
│ source metadata -> application metadata                      │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               v
                     ┌─────────┴─────────┐
                     │                   │
                 ISRC != NULL        ISRC == NULL
                     │                   │
                     v                   │
             search songs.db             │
                     │                   │
               ┌─────┴──────┐            │
               │            │            │
            no match      match          │
               │            │            │
               │            v            │
               │      DUPLICATE PROMPT   │
               │        /          \     │
               │   previous        current
               │      │                │
               │      v                v
               │  discard current   keep current
               │  temp + mark       replace old
               │  duplicate         retained song
               │                       │
               └──────────┬────────────┘
                          │
                          v
┌──────────────────────────────────────────────────────────────┐
│                 YOUTUBE OFFICIAL VIDEO SEARCH                │
│                                                              │
│ query:                                                       │
│ {title} {album_name} official video song                     │
│                                                              │
│ returned result order is authoritative                       │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               v
┌──────────────────────────────────────────────────────────────┐
│                   SIMPLE RESULT FILTER                       │
│                                                              │
│ If result title contains "lyrics" -> skip                   │
│ Otherwise -> select immediately                              │
│                                                              │
│ No ranking. No scoring. No confidence.                       │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               v
┌──────────────────────────────────────────────────────────────┐
│                  SELECTED VIDEO METADATA                     │
│                                                              │
│ ID / URL / title / channel / channel ID / views / date      │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               v
┌──────────────────────────────────────────────────────────────┐
│                    FINAL MP3 BUILD                           │
│                                                              │
│ source audio + master.jpg                                    │
│                                                              │
│ final file: .mp3.tmp                                         │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               v
┌──────────────────────────────────────────────────────────────┐
│                 MUTAGEN FINAL TAG WRITER                     │
│                                                              │
│ Standard ID3 + custom TXXX + APIC artwork                   │
│                                                              │
│ Mutagen is the sole final metadata authority                 │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               v
┌──────────────────────────────────────────────────────────────┐
│                     FINAL VALIDATION                         │
│                                                              │
│ - audio playable                                             │
│ - duration valid                                             │
│ - tags readable                                               │
│ - artwork embedded                                           │
│ - expected YouTube fields present                            │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               v
┌──────────────────────────────────────────────────────────────┐
│                    HASH + FILE SIZE                          │
│                                                              │
│ SHA-256(final fully-tagged MP3)                              │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               v
┌──────────────────────────────────────────────────────────────┐
│                      ATOMIC RENAME                           │
│                                                              │
│ .mp3.tmp -> final .mp3                                       │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               v
┌──────────────────────────────────────────────────────────────┐
│                         songs.db                             │
│                                                              │
│ current serial + metadata + file path + hash                │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               v
┌──────────────────────────────────────────────────────────────┐
│                       playlist.db                            │
│                                                              │
│ current serial -> completed                                 │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               v
┌──────────────────────────────────────────────────────────────┐
│                      CLEANUP TEMP                            │
│                                                              │
│ delete temp/{serial}/                                        │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               v
                    NEXT PENDING ENTRY
```

---

# 67. COMPLETE STATUS EXAMPLES

## Initial

```text
playlist.db

001 pending
002 pending
003 pending
004 pending
```

## After normal processing

```text
playlist.db

001 completed
002 completed
003 completed
004 completed
```

`songs.db`:

```text
001
002
003
004
```

## After duplicate — keep previous

```text
playlist.db

001 completed
002 completed
003 duplicate
004 pending
```

`songs.db`:

```text
001
002
004
```

## After duplicate — keep current

```text
playlist.db

001 pending
002 completed
003 completed
004 pending
```

`songs.db`:

```text
002
003
```

The old serial still exists in the playlist database.

---

# 68. WHAT `playlist.db` MUST NEVER DO

`playlist.db` must never:

- delete a playlist entry because of duplicate detection;
- change a serial number;
- recycle a serial number;
- replace one playlist entry with another;
- use ISRC as its primary identity;
- use YouTube video ID as its primary identity.

---

# 69. WHAT `songs.db` MUST NEVER DO

`songs.db` must never:

- contain two rows with the same serial;
- contain the discarded current duplicate when the user chose previous;
- retain an old row after its MP3 has been intentionally replaced by the current duplicate;
- invent ISRC values;
- use fallback duplicate matching when ISRC is `NULL`.

---

# 70. WHAT YT-DLP MUST DO

The initial yt-dlp stage must:

- use the selected YTM source URL;
- download the source audio;
- write `info.json`;
- write thumbnail/artwork;
- convert the artwork to the selected image type when necessary;
- not perform final ID3 tagging;
- not be called a second time for artwork only.

---

# 71. WHAT MUTAGEN MUST DO

Mutagen must:

- write standard ID3 tags;
- write ISRC when present;
- write custom source/YouTube fields;
- embed artwork;
- save the final MP3;
- provide the final metadata state that is subsequently validated.

---

# 72. WHAT THE VIDEO FINDER MUST DO

It must:

1. construct the exact query;
2. retrieve results;
3. inspect titles in returned order;
4. skip titles containing `lyrics`;
5. select the first remaining result;
6. stop immediately after selection;
7. retrieve that video's metadata.

It must not:

- score;
- rank;
- compare views;
- compare durations;
- compare channels;
- calculate confidence.

---

# 73. RESTART / RESUME BEHAVIOR

The application must be restart-safe.

If it exits unexpectedly:

- already finalized `completed` rows remain completed;
- duplicate decisions already committed remain committed;
- permanent serials remain unchanged;
- new processing continues from the next `pending` entry;
- `error` entries can be retried.

If a temporary directory remains after a crash, startup/recovery logic should inspect and clean stale temporary directories as appropriate rather than assuming they represent completed songs.

---

# 74. LOGGING REQUIREMENTS

The application should log enough information to understand every processing attempt.

Minimum useful information per serial:

```text
serial
playlist position
title
artist
status before processing
status after processing
ISRC
whether duplicate detected
existing duplicate serial when applicable
user duplicate decision
YouTube search query
selected YouTube video ID when applicable
final MP3 path
final MP3 size
SHA-256
error message when applicable
```

Logs must not replace the databases.

The databases remain authoritative for persistent state.

---

# 75. USER PROMPTS

Normal successful processing should be automatic.

The only required interactive prompt is duplicate handling.

Example:

```text
[DUPLICATE]
Current: 004 - Song A - Artist A
Existing: 001 - Song A - Artist A
ISRC: USABC1234567

1) Keep previous
2) Keep current
Selection:
```

No prompt is required for ordinary YouTube video selection.

The YouTube selection rule is deterministic:

```text
first result whose title does not contain lyrics
```

---

# 76. TEST PLAN

The final implementation should test at least the following cases.

## Test 1 — New unique song

Expected:

```text
pending -> completed
songs.db row created
MP3 created
```

## Test 2 — Duplicate with keep previous

Expected:

```text
current -> duplicate
old song retained
current songs.db row absent
```

## Test 3 — Duplicate with keep current

Expected:

```text
old playlist entry -> pending
current playlist entry -> completed
old songs.db row deleted
current songs.db row created
old MP3 deleted
current MP3 retained
```

## Test 4 — NULL ISRC

Expected:

```text
isrc = NULL
no duplicate query
song processes normally
```

## Test 5 — YouTube result with lyrics first

Expected:

```text
result 1 skipped
result 2 selected
```

## Test 6 — All YouTube results contain lyrics

Expected:

```text
yt_video fields = NULL
song can still complete
```

## Test 7 — YouTube search returns an acceptable result first

Expected:

```text
result 1 selected immediately
```

## Test 8 — Source acquisition fails

Expected:

```text
status = error
no completed songs.db row
serial preserved
```

## Test 9 — Final MP3 validation fails

Expected:

```text
no completed songs.db commit
no playlist completed state
```

## Test 10 — Restart after error

Expected:

```text
error -> pending
retry uses same serial
```

## Test 11 — Duplicate replacement after current file validation

Expected:

```text
old MP3 is not deleted until replacement MP3 validates successfully
```

## Test 12 — Playlist contains same YTM entry twice

Expected:

```text
separate serials
separate playlist rows
no serial collision
```

---

# 77. FINAL ACCEPTANCE CRITERIA

Phase 1 is complete when the system can demonstrate all of the following:

## Playlist identity

- complete playlist is ingested;
- returned order is preserved;
- every playlist entry gets a permanent serial;
- serials never collide;
- serials are never reused.

## Source acquisition

- the exact YTM source is downloaded;
- one yt-dlp command obtains audio + info.json + artwork;
- `--add-metadata` is not used;
- acquisition artifacts are validated.

## Metadata

- detailed source metadata is parsed;
- ISRC is extracted when available;
- missing ISRC is stored as NULL;
- no fallback duplicate match is used.

## Duplicate handling

- ISRC match is found in `songs.db`;
- user chooses previous/current;
- keep previous marks current playlist entry duplicate;
- keep current deletes the old retained song and changes old playlist entry to pending;
- playlist entries are never deleted.

## YouTube video discovery

- exact search query is used;
- results are processed in returned order;
- `lyrics` results are skipped;
- first remaining result is selected;
- no scoring/ranking is used;
- no acceptable result is allowed to leave the song otherwise incomplete.

## Final MP3

- final MP3 is created;
- Mutagen writes all final metadata;
- artwork is embedded;
- YouTube metadata is embedded;
- final file validates after writing;
- SHA-256 is calculated;
- final filename contains permanent serial.

## Persistence

- `songs.db` accurately reflects retained files;
- `playlist.db` accurately reflects processing status;
- completed records point to existing valid MP3 files;
- temporary directories are cleaned after finalization.

---

# 78. FINAL LOCKED RULES

These are the final rules for implementation and should not be changed casually during coding.

1. `playlist.db` is the permanent playlist database.
2. `songs.db` is the retained-song database.
3. Every playlist entry receives one permanent serial number.
4. Serial numbers are unique.
5. Serial numbers are never reused.
6. Serial numbers never change.
7. Serial numbers are assigned according to playlist ingestion order.
8. The API/default playlist order is preserved.
9. `playlist_position` is stored separately from the permanent serial.
10. `ytm_video_id` is not the permanent playlist identity.
11. The same YTM entry can appear multiple times in a playlist.
12. Such repeated entries receive different serial numbers.
13. `pending`, `completed`, `duplicate`, and `error` are the playlist processing statuses.
14. `completed` requires a retained song in `songs.db`.
15. `duplicate` means the entry was processed but the previous retained song was kept.
16. `error` means processing failed and may later be retried.
17. ISRC is the only duplicate key.
18. Missing ISRC is stored as `NULL`.
19. Missing ISRC does not trigger duplicate detection.
20. No fallback duplicate matching is permitted.
21. Duplicate detection is performed against `songs.db`.
22. The user decides whether to keep previous or current duplicate.
23. Keep previous -> current playlist entry becomes `duplicate`.
24. Keep previous -> previous song remains unchanged.
25. Keep current -> previous physical MP3 is deleted only after current replacement is valid.
26. Keep current -> previous `songs.db` row is deleted.
27. Keep current -> previous playlist entry becomes `pending`.
28. Keep current -> current playlist entry becomes `completed`.
29. Playlist entries are never deleted because of duplicates.
30. Initial source acquisition uses one complete yt-dlp command.
31. That acquisition gets audio.
32. That acquisition gets `info.json`.
33. That acquisition gets artwork.
34. No second artwork download is performed.
35. yt-dlp does not write final ID3 metadata.
36. `--add-metadata` is not used.
37. Mutagen is the single final metadata writer.
38. Mutagen writes standard ID3 fields.
39. Mutagen writes custom TXXX source/YouTube fields.
40. Mutagen embeds front-cover artwork.
41. The final MP3 is validated after metadata writing.
42. SHA-256 is calculated after final metadata writing.
43. The final MP3 is atomically renamed after successful validation.
44. YouTube search query is exactly `{title} {album_name} official video song`.
45. Results remain in returned order.
46. Titles containing `lyrics` are skipped case-insensitively.
47. The first remaining result is selected.
48. No YouTube scoring exists.
49. No YouTube ranking exists.
50. No YouTube confidence score exists.
51. No view-count ranking exists.
52. No duration ranking exists.
53. No channel ranking exists.
54. If no acceptable YouTube result exists, the YouTube video fields remain NULL/absent.
55. The song can still complete without an acceptable YouTube video.
56. Final MP3 filename uses the permanent serial.
57. Temporary files are deleted only after successful finalization.
58. Database state must reflect physical file state.
59. A failed processing attempt must never be marked `completed`.
60. Lyrics and Phase 2 audio-analysis features remain outside the Phase 1 scope.

---

# 79. FINAL ONE-PAGE SUMMARY

```text
PLAYLIST
   |
   | YTMusic API
   v
playlist.db
   |
   | permanent serial
   v
PENDING ENTRY
   |
   | ONE yt-dlp command
   +-------------------------------+
   |               |               |
   v               v               v
audio.mp3      info.json       artwork.jpg
   |               |               |
   +---------------+---------------+
                   |
                   v
          metadata normalization
                   |
                   v
              ISRC check
                   |
          +--------+--------+
          |                 |
       NULL/unique       duplicate
          |                 |
          |             ask user
          |             /      \
          |       previous     current
          |          |            |
          |          v            v
          |       duplicate   replace old
          |                       |
          +-----------+-----------+
                      |
                      v
           YouTube search
                      |
       title + album + official video song
                      |
                      v
          skip title containing lyrics
                      |
                      v
          first remaining result
                      |
                      v
         selected video metadata
                      |
                      v
             use master.jpg
                      |
                      v
              final MP3.tmp
                      |
                      v
             Mutagen writes tags
                      |
                      v
              validate final MP3
                      |
                      v
                 SHA-256
                      |
                      v
              atomic final MP3
                      |
                      v
                  songs.db
                      |
                      v
          playlist.db -> completed
                      |
                      v
                cleanup temp
                      |
                      v
              NEXT PENDING ENTRY
```

---

# 80. END STATE

At the end of a successful full run, the project contains:

```text
phase1_project/
│
├── db/
│   ├── playlist.db
│   └── songs.db
│
├── songs/
│   └── original/
│       ├── 001_....mp3
│       ├── 002_....mp3
│       ├── 003_....mp3
│       └── ...
│
├── temp/
│   └── empty after successful cleanup
│
├── config.json
├── cookies.txt
├── requirements.txt
├── main.py
└── src/
```

`playlist.db` preserves the complete playlist-entry identity and status history required by Phase 1.

`songs.db` contains only the currently retained song assets.

Each retained MP3 is self-contained with its final ID3 metadata and embedded artwork.

This is the complete Phase 1 architecture and implementation specification.

---

# APPENDIX B — PHASE 2 ORIGINAL SPECIFICATION

The complete Phase 2 source document follows verbatim below.

# PHASE 2 — STANDALONE WORD-LEVEL TELUGU LYRIC SYNCING

## Ultra-Detailed Production Project Plan

**Document status:** Implementation blueprint / engineering specification  
**Project:** Phase 2 only — standalone word-level lyric synchronization  
**Input model:** MP3 + sidecar LRC + sidecar cumulative JSON  
**Output model:** MP3 + LRC + cumulative JSON  
**Language focus:** Telugu (`te` / ISO-639-3 `tel`)  
**Primary alignment model:** Meta MMS (`facebook/mms-1b-all`) with Telugu adapter  
**Primary alignment method:** Reference-driven CTC forced alignment  
**Original files:** Never modified  
**Phase 1 integration:** None; Phase 2 consumes files only

---

# 1. EXECUTIVE DEFINITION

Phase 2 is a completely independent project that takes an already prepared music collection and upgrades the lyric timing from line-level synchronization to word-level synchronization.

The project must not import, call, modify, or depend on Phase 1's Python code, Phase 1's SQLite database, or Phase 1's processing state machine.

Phase 2 may consume information that was previously generated by Phase 1 because that information is physically present in the input MP3/LRC/JSON package, but this is a **file-level handoff**, not a software integration.

The fundamental input unit is a basename-matched three-file package:

```text
songs/original/
├── SongName.mp3
├── SongName.lrc
└── SongName.json
```

The fundamental output unit is another three-file package with the same basename:

```text
songs/final/
├── SongName.mp3
├── SongName.lrc
└── SongName.json
```

The original source package remains untouched.

The final package contains:

1. The original MP3 audio and all previous MP3 metadata, plus the new Phase 2 word-level synchronized lyrics frame.
2. A newly generated word-level LRC export using the original lyric wording and Phase 2 timing.
3. The original JSON object, completely preserved, with a new `phase2` namespace containing every new Phase 2 detail.

The canonical timing representation is the Phase 2 word alignment stored in the database and inside the final JSON. The final LRC is an export, and the embedded SYLT is another export of the same canonical timing result.

---

# 2. NON-NEGOTIABLE REQUIREMENTS

These are architectural invariants. The implementation must not violate them.

## 2.1 Original directory is read-only

```text
songs/original/
```

must be treated as read-only by the entire application.

No Phase 2 code path may:

- save an MP3 over an input MP3
- rewrite the original LRC
- rewrite the original JSON
- change file permissions unnecessarily
- rename source files
- move source files
- delete source files
- write temporary files beside the source files unless explicitly inside a separate temp directory

## 2.2 Phase 2 does not require embedded lyrics

The authoritative lyric input is:

```text
SongName.lrc
```

The implementation must not require `SYLT` or `USLT` to exist inside the MP3.

The sample MP3 used during planning happens to contain existing `SYLT` and `USLT` frames, but this must not become a hidden dependency. Existing embedded lyric frames are treated as existing MP3 metadata and are preserved rather than becoming the lyric source of truth.

## 2.3 Sidecar matching is by exact basename

Given:

```text
001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.mp3
```

the associated files are exactly:

```text
001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.lrc
001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.json
```

No fuzzy matching is allowed.

## 2.4 Existing JSON must be preserved completely

The original JSON is treated as a cumulative historical record.

Phase 2 must load the entire JSON object and write the final JSON as:

```text
original JSON object
    +
phase2 namespace
```

No previous top-level key may be silently removed, renamed, flattened, overwritten, or reconstructed.

Unknown keys must survive unchanged.

## 2.5 Existing MP3 metadata must be preserved

Phase 2 must modify the output MP3 surgically.

It must not:

```text
remove all ID3 frames
rebuild only a few known fields
save a reduced tag set
```

Instead:

```text
copy original MP3
    -> open existing tags
    -> preserve all existing frames
    -> add/update only the Phase 2-owned synchronized lyric frame
    -> save
```

## 2.6 Exactly three user-facing final files per song

The planned final user-facing package is:

```text
songs/final/SongName.mp3
songs/final/SongName.lrc
songs/final/SongName.json
```

Temporary files, SQLite, logs, model cache, and debugging artifacts may exist elsewhere but are not part of the final song package.

## 2.7 No destructive normalization

Text normalization must be reversible.

The original lyric wording must remain available after normalization.

## 2.8 MMS is an acoustic evidence generator, not the final transcript

The final system must not use:

```text
MMS ASR decode -> predicted words -> predicted timestamps
```

as its word-level lyric alignment method.

The supplied LRC text is the reference transcript. MMS produces frame-level acoustic emissions. The reference transcript is then explicitly aligned against those emissions using a CTC forced-alignment algorithm.

## 2.9 LRC is an anchor, not unquestionable ground truth

Existing LRC line timestamps are coarse timing information.

They are used to:

- constrain search regions
- create chunks
- detect long lyric-free gaps
- validate the new timing

but the exact word timing comes from acoustic alignment.

## 2.10 Word-level timing must have start and end

The canonical representation must keep:

```text
word
start_ms
end_ms
score
source
```

A timestamp-only representation is insufficient for validation and high-quality downstream processing.

---

# 3. REAL SAMPLE INPUT CONTRACT

The sample supplied for planning is:

```text
001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.mp3
001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.lrc
001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.json
```

The sample JSON is a large cumulative record rather than a minimal song description. It contains top-level sections including:

```text
artwork
files
generated_at
lyrics
playlist
project_version
schema_version
song
sources
spotify
youtube_video
```

The existing JSON records, among other things, artwork information, source paths/hashes, lyric provenance, playlist identity, normalized song metadata, raw source metadata, Spotify information, and YouTube information.

The sample JSON also records a 318-second song duration and the synchronized lyric content.

The sample LRC contains:

- 42 timestamp entries
- 39 non-empty lyric entries
- 3 blank timestamp markers

The two major blank-timestamp regions are approximately:

```text
01:37.29 -> 02:12.94 = 35.65 seconds
03:11.72 -> 04:12.82 = 61.10 seconds
```

These are strong candidate non-lyric boundaries and must be treated as important chunking/validation information.

The sample MP3 currently contains 42 ID3 frame keys, including existing `TXXX`, `UFID`, `WXXX`, `USLT`, `SYLT`, and `APIC` data. The existing synchronized lyric frame and artwork must survive Phase 2. A new Phase 2 word-level SYLT frame should be added under its own descriptor rather than deleting the existing lyric frame.

The exact sample is therefore an excellent acceptance test for the implementation.

---

# 4. PROJECT OBJECTIVES

## 4.1 Primary objective

Produce trustworthy word-level timing for every lyric word that can be acoustically aligned.

## 4.2 Secondary objectives

- Preserve all existing song metadata.
- Preserve all previous JSON information.
- Preserve original MP3 audio.
- Preserve the original LRC file as input-only data.
- Produce a clean final LRC.
- Embed word-level synchronization into the final MP3.
- Make the process resumable.
- Make processing idempotent.
- Make every output traceable to exact input hashes, model revision, configuration, and pipeline version.
- Support partial results without pretending that interpolated timing is equivalent to directly aligned timing.
- Support batch processing at large scale.

## 4.3 Non-objectives

Phase 2 does not:

- discover new songs
- download audio
- download lyrics
- search external lyric databases
- change the source MP3
- edit Phase 1's database
- regenerate historical metadata
- replace the existing artwork
- use a transcription-first Whisper workflow

---

# 5. END-TO-END PIPELINE

The full pipeline is:

```text
songs/original/Song.mp3
songs/original/Song.lrc
songs/original/Song.json
          |
          v
[1] FILE MATCHING + INVENTORY
          |
          v
[2] INPUT HASHING + SNAPSHOT
          |
          v
[3] JSON LOAD + PRESERVE
          |
          v
[4] LRC PARSE
          |
          v
[5] AUDIO VALIDATION / DECODE
          |
          v
[6] VOCAL ISOLATION — DEMUCS
          |
          v
[7] VOCAL ACTIVITY — VAD + ENERGY
          |
          v
[8] REVERSIBLE TELUGU NORMALIZATION
          |
          v
[9] LRC ANCHOR MODEL
          |
          v
[10] REFERENCE-AWARE CHUNKING
          |
          v
[11] MMS MODEL INITIALIZATION
          |
          v
[12] MMS FRAME-LEVEL EMISSIONS
          |
          v
[13] CTC REFERENCE FORCED ALIGNMENT
          |
          v
[14] TOKEN -> WORD SPANS
          |
          v
[15] CHUNK QUALITY ANALYSIS
          |
          v
[16] OVERLAP DEDUPLICATION
          |
          v
[17] GLOBAL MERGE
          |
          v
[18] ALIGNMENT VALIDATION
          |
          v
[19] INSTRUMENTAL / GAP ANALYSIS
          |
          v
[20] CANONICAL PHASE2 DATA
          |
          +-----------------------------+
          |                             |
          v                             v
[21] FINAL LRC EXPORT             [22] FINAL MP3 + SYLT
          |                             |
          +-------------+---------------+
                        |
                        v
                [23] FINAL JSON UPDATE
                        |
                        v
                [24] OUTPUT VALIDATION
                        |
                        v
                [25] ATOMIC/STAGED PROMOTION
                        |
                        v
                songs/final/Song.mp3
                songs/final/Song.lrc
                songs/final/Song.json
```

---

# 6. DIRECTORY STRUCTURE

```text
phase2_project/
│
├── main.py
├── config.json
├── requirements.lock
├── README.md
├── CHANGELOG.md
│
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── db.py
│   ├── scanner.py
│   ├── json_manager.py
│   ├── lrc_reader.py
│   ├── audio.py
│   ├── demucs_isolator.py
│   ├── activity_detector.py
│   ├── telugu_normalizer.py
│   ├── tokenizer.py
│   ├── chunker.py
│   ├── mms_model.py
│   ├── ctc_aligner.py
│   ├── word_builder.py
│   ├── merger.py
│   ├── validator.py
│   ├── lrc_generator.py
│   ├── embedder.py
│   ├── json_updater.py
│   ├── recovery.py
│   ├── pipeline.py
│   └── utils.py
│
├── songs/
│   ├── original/
│   │   ├── Song.mp3
│   │   ├── Song.lrc
│   │   └── Song.json
│   │
│   └── final/
│       ├── Song.mp3
│       ├── Song.lrc
│       └── Song.json
│
├── temp/
│   └── {song_key}/
│       ├── input/
│       │   ├── source.mp3
│       │   ├── source.lrc
│       │   └── source.json
│       │
│       ├── audio/
│       │   ├── source_16k.wav
│       │   └── vocals_16k.wav
│       │
│       ├── chunks/
│       │   ├── chunk_000.wav
│       │   ├── chunk_000.json
│       │   ├── chunk_001.wav
│       │   └── ...
│       │
│       ├── stage_final/
│       │   ├── Song.mp3
│       │   ├── Song.lrc
│       │   └── Song.json
│       │
│       └── logs/
│
├── models/
│   └── mms/
│
└── db/
    └── phase2.db
```

The source files are not copied here for editing; the temp copy is strictly a working snapshot used for processing and debugging.

---

# 7. FILE MATCHING RULES

## 7.1 Scan scope

Default scan:

```text
songs/original/*.mp3
```

The implementation may offer an optional recursive mode, but the default corpus contract should be a flat directory because the user-defined structure is flat.

## 7.2 Basename derivation

Given:

```text
SongName.mp3
```

derive:

```text
SongName
```

Then require:

```text
SongName.lrc
SongName.json
```

## 7.3 Missing LRC

A missing LRC is a hard input failure because Phase 2's task is based on the provided LRC reference.

Set:

```text
quality_status = failed
error_code = LRC_MISSING
```

Do not fetch a replacement lyric source.

## 7.4 Missing JSON

A missing JSON is not necessarily a reason to abandon alignment, but it means the cumulative metadata contract is incomplete.

Preferred policy:

```text
process alignment only if explicitly allowed by configuration
```

Default policy:

```text
missing JSON -> needs_review / skipped
```

because the user's stated input contract includes the JSON historical record.

Do not fabricate historical metadata.

## 7.5 Duplicate basenames

If the scanner encounters duplicate basenames that would collide into the same final filename, stop those records with a clear error.

---

# 8. SOURCE FINGERPRINTING

For every input file calculate SHA-256:

```text
mp3_sha256
lrc_sha256
json_sha256
```

Also store:

```text
file_size
mtime
```

The SHA-256 is the authoritative content identity.

This lets the system distinguish:

```text
same filename, same file
```

from:

```text
same filename, different file
```

---

# 9. IDENTITY MODEL

A processing identity should be derived from:

```text
basename
+
mp3_sha256
+
lrc_sha256
+
json_sha256
+
pipeline_version
+
config_hash
+
model_name
+
model_revision
+
normalizer_version
```

If the same exact input and processing environment already produced valid final outputs, the song can be skipped safely.

If any relevant identity component changes, the song is eligible for reprocessing.

---

# 10. JSON HANDLING

## 10.1 Load the complete JSON

The JSON manager must parse the entire JSON document.

Do not use a schema that only allows known Phase 1 fields.

Unknown data must survive.

## 10.2 Preserve arbitrary top-level keys

The output must preserve every original top-level key:

```text
artwork
files
generated_at
lyrics
playlist
project_version
schema_version
song
sources
spotify
youtube_video
```

as present in the source sample.

Other songs may contain additional keys. Those keys must also survive.

## 10.3 Phase 2 namespace

Phase 2 owns exactly one new top-level namespace:

```json
"phase2": { ... }
```

This namespace is the only location Phase 2 is allowed to mutate in the JSON.

## 10.4 Existing phase2 namespace

If `phase2` already exists, update it in place while retaining historical subfields when possible.

Record:

```text
phase2.previous_run
phase2.current_run
```

or maintain a controlled run history array if the user wants complete historical attempts.

Recommended structure:

```json
"phase2": {
  "current": { ... },
  "history": [ ... ]
}
```

The first implementation may keep only `current` plus a compact `history` summary to avoid unnecessary JSON growth.

---

# 11. JSON PHASE 2 SCHEMA

The final JSON should contain a `phase2` object conceptually like:

```json
{
  "phase2": {
    "schema_version": 1,
    "pipeline_version": "1.0.0",
    "status": "finished",
    "quality_status": "good",

    "input": {
      "basename": "SongName",
      "mp3_filename": "SongName.mp3",
      "lrc_filename": "SongName.lrc",
      "json_filename": "SongName.json",
      "mp3_sha256": "...",
      "lrc_sha256": "...",
      "json_sha256": "..."
    },

    "model": {
      "name": "facebook/mms-1b-all",
      "language_iso1": "te",
      "language_iso3": "tel",
      "revision": "..."
    },

    "audio": {
      "source_duration_ms": 0,
      "alignment_sample_rate": 16000,
      "channels": 1
    },

    "vocal_isolation": {
      "model": "htdemucs",
      "device": "cuda",
      "status": "success"
    },

    "lyrics": {
      "source": "external_lrc",
      "line_count": 0,
      "blank_timing_markers": 0,
      "normalizer_version": "1.0"
    },

    "alignment": {
      "method": "ctc_forced_alignment",
      "word_count": 0,
      "aligned_word_count": 0,
      "missing_word_count": 0,
      "interpolated_word_count": 0,
      "lines": []
    },

    "quality": {
      "mean_score": null,
      "p10_score": null,
      "minimum_score": null,
      "low_score_word_percent": 0,
      "interpolated_word_percent": 0,
      "median_anchor_shift_ms": null,
      "max_anchor_shift_ms": null
    },

    "chunks": {
      "total": 0,
      "aligned": 0,
      "low_confidence": 0,
      "failed": 0
    },

    "instrumental_sections": [],

    "outputs": {
      "mp3": "songs/final/SongName.mp3",
      "lrc": "songs/final/SongName.lrc",
      "json": "songs/final/SongName.json"
    }
  }
}
```

This is an example contract rather than a rigid requirement that every field be populated for every song.

---

# 12. LRC PARSING

## 12.1 Supported timestamp forms

At minimum support:

```text
[mm:ss.xx]
[mm:ss.xxx]
```

Optionally support:

```text
[mm:ss]
```

with exact deterministic conversion.

## 12.2 Metadata tags

Recognize common LRC metadata such as:

```text
[ar:]
[ti:]
[al:]
[by:]
```

but keep them as source metadata rather than treating them as lyric text.

## 12.3 Blank timestamp lines

A line such as:

```text
[01:37.29]
```

with no lyric text is a meaningful source event.

Store it as:

```text
kind = blank_marker
start_ms = 97290
text = ""
```

Do not discard it during parsing.

## 12.4 Duplicate timestamps

If multiple text lines have exactly the same LRC timestamp, preserve order and create separate line records.

## 12.5 Original text preservation

Store the source line exactly enough to reproduce the original visible lyric wording.

Do not normalize the original LRC in place.

---

# 13. LRC INTERNAL DATA MODEL

Each parsed line should conceptually contain:

```text
line_index
original_timestamp_ms
original_text
kind
normalization_record
word_records[]
```

Possible line kinds:

```text
lyric
blank_marker
metadata
```

Only `lyric` and `blank_marker` participate in timing alignment.

---

# 14. AUDIO VALIDATION

Read the MP3 and determine:

```text
duration_ms
sample_rate
channels
bitrate if available
codec
```

The source MP3 remains untouched.

The working alignment representation should be:

```text
16 kHz
mono
float PCM
lossless WAV
```

Example:

```text
temp/{song_key}/audio/source_16k.wav
```

The source MP3 itself should not be repeatedly decoded and re-encoded between stages.

---

# 15. AUDIO DURATION CONSISTENCY

Compare:

```text
MP3 duration
LRC source metadata duration if available
JSON recorded duration if available
```

Do not require exact equality because metadata may differ by a small amount.

Record:

```text
audio.duration_delta_ms
```

Use the actual decoded MP3 duration as the authoritative audio boundary.

---

# 16. DEMUCS VOCAL ISOLATION

## 16.1 Purpose

Provide a cleaner vocal-bearing signal for alignment.

The user-facing output remains the original music mix.

Demucs is only a temporary processing stage.

## 16.2 Model

Default:

```text
htdemucs
```

Prefer a vocals-only separation path where supported.

Do not assume it is computationally cheaper simply because the requested output is one stem; the selected Demucs mode may still perform the underlying separation computation.

## 16.3 Working output

Preferred:

```text
temp/{song_key}/audio/vocals_16k.wav
```

or generate the lossless vocal stem first and resample once.

Avoid MP3 compression in the working vocal path.

## 16.4 GPU-first policy

Attempt:

```text
CUDA
```

first if configured.

On an out-of-memory or compatible runtime failure:

```text
CPU fallback
```

Record the actual device used.

## 16.5 GPU memory recovery

If CUDA OOM occurs:

1. release model/tensor references where safe
2. clear cached CUDA memory
3. reduce Demucs segment size if configured
4. retry
5. fall back to CPU if the retry fails

Do not pretend that "smaller batch size" solves a single-file Demucs invocation when batch size is already one.

## 16.6 Duration alignment

The vocal stem must be normalized to the source time axis.

If the stem is a few samples shorter/longer due to processing, pad or trim deterministically to the exact source sample count before converting to 16 kHz.

## 16.7 Validation

Require:

```text
vocals file exists
vocals readable
finite samples
non-zero usable signal
expected duration within tolerance
```

---

# 17. DUAL AUDIO ALIGNMENT STRATEGY

The primary alignment signal is:

```text
vocals stem
```

However, the original mix should remain available as a fallback.

For a low-confidence vocal-stem alignment:

```text
vocal result low confidence
        |
        v
try original-mix alignment for the same reference region
        |
        v
compare quality
        |
        v
retain better validated result
```

This protects against unusual Demucs artifacts, vocal bleed, whispering, background vocals, or songs where separation reduces useful acoustic information.

---

# 18. VOCAL ACTIVITY ANALYSIS

Use both:

```text
Silero VAD
+
audio energy/RMS activity
```

The output is an activity map rather than a claim of semantic "instrumental truth".

Silero VAD provides speech/activity intervals based on a threshold and related duration/padding parameters.

Suggested starting values:

```text
threshold = 0.50
min_speech_duration_ms = 250
min_silence_duration_ms = 300
speech_pad_ms = 150
```

These values must remain configurable and benchmarked.

---

# 19. WHAT VAD MEANS IN THIS PROJECT

VAD output means approximately:

```text
speech-like activity detected
```

It does not automatically mean:

```text
singing definitely exists
```

and lack of VAD activity does not automatically prove:

```text
instrumental section
```

Therefore VAD is used for:

- chunk boundary refinement
- pause detection
- non-lyric candidate identification
- alignment troubleshooting

It is not the sole source of instrumental markers.

---

# 20. LRC GAP MODEL

The existing LRC provides an especially valuable signal.

For consecutive lyric lines:

```text
line_i.start_ms
line_{i+1}.start_ms
```

compute:

```text
gap = line_{i+1}.start_ms - line_i.start_ms
```

For blank markers, additionally preserve the blank marker timestamp.

A long blank marker interval such as:

```text
01:37.29 -> 02:12.94
```

should become a strong candidate boundary.

The final classifier uses:

```text
LRC blank marker
+
next lyric start
+
VAD activity
+
energy
+
absence of aligned lyric words
```

to classify the region.

---

# 21. TELUGU NORMALIZATION

Normalization must produce two parallel representations.

```text
ORIGINAL TEXT
     |
     +--> display_text
     |
     `--> alignment_text
```

The final LRC and final JSON retain the original wording.

The alignment engine operates on normalized reference text.

---

# 22. NORMALIZATION PIPELINE

Preferred order:

```text
raw line
  |
  v
Unicode NFC
  |
  v
whitespace normalization
  |
  v
number normalization if configured
  |
  v
known abbreviation normalization if configured
  |
  v
alignment-token compatibility normalization
  |
  v
alignment text
```

Do not delete characters before a rule that needs those characters has had a chance to process them.

---

# 23. ORIGINAL WORD RECORD

Each original lyric word should have an internal mapping like:

```text
line_index
word_index
original_word
alignment_word
original_character_start
original_character_end
normalization_operations[]
```

Example:

```text
original_word = "1"
alignment_word = "ఒకటి"
normalization_operations = ["numeric_to_telugu"]
```

The output still displays the original word unless the user configuration explicitly specifies otherwise.

---

# 24. UNSUPPORTED TEXT

The Telugu MMS adapter may not represent every character or Latin word in the input.

Do not silently delete unsupported words.

For every unsupported word classify it as:

```text
alignment_status = unsupported
```

and preserve:

```text
original_word
```

If a timestamp can be inferred from neighboring aligned words, the word may receive:

```text
source = interpolated
```

otherwise:

```text
source = missing
```

This creates an honest distinction between:

```text
direct acoustic alignment
```

and:

```text
estimated timing
```

---

# 25. NORMALIZATION VERSIONING

The normalization algorithm must have a version.

Example:

```text
normalizer_version = 1.0.0
```

Any meaningful normalization rule change should increment this version.

The version must be stored in:

- database
- final JSON
- processing logs

so that later reruns can be compared.

---

# 26. LRC AS COARSE ALIGNMENT SCAFFOLD

For each lyric line, define:

```text
anchor_ms = original LRC timestamp
```

The anchor is used as a soft timing constraint.

A line should normally align close to its anchor unless the acoustic evidence strongly supports another position.

The allowed deviation should be configurable.

Suggested initial search behavior:

```text
normal line:
anchor ± 2.5 seconds
```

but the implementation should expand this window when neighboring anchors and long pauses make the broader region more plausible.

Do not use a hard-coded universal window without benchmarking.

---

# 27. ANCHOR-AWARE CHUNKING

Chunking is not merely slicing the audio every N seconds.

The chunker must consider:

1. LRC line boundaries
2. LRC anchor timestamps
3. blank markers
4. large gaps
5. VAD activity boundaries
6. energy minima
7. lyric word density
8. maximum model context
9. overlap context

---

# 28. CHUNK DURATION POLICY

Default guidance:

```text
minimum useful target: 4 sec
preferred target:       ~12 sec
maximum preferred:      20 sec
```

These are soft goals.

A natural phrase may be shorter than 4 seconds and should not be stretched artificially.

A dense phrase may need to remain slightly longer if splitting would destroy alignment coherence.

---

# 29. CHUNK PRIORITY ORDER

When choosing a boundary, use the following preference order:

```text
1. explicit blank LRC boundary
2. large lyric gap
3. strong LRC line boundary
4. strong vocal pause
5. energy minimum
6. word boundary
7. nearest practical fallback
```

Avoid splitting in the middle of a lyric phrase whenever possible.

---

# 30. OVERLAPPING CONTEXT

Each chunk has two ranges.

### Logical range

The part whose results are eligible for the final merged alignment.

### Model audio range

The larger region actually supplied to MMS.

Example:

```text
logical:
10.000 -> 22.000 sec

model audio:
 9.500 -> 22.500 sec
```

The extra context reduces boundary clipping.

---

# 31. CHUNK DATABASE FIELDS

Each chunk should store:

```text
song_id
chunk_index
logical_start_ms
logical_end_ms
audio_start_ms
audio_end_ms
line_start_index
line_end_index
text_content
normalized_text
word_count
status
attempt_count
audio_path
result_json_path
alignment_score
p10_score
minimum_score
error_code
error_remark
```

---

# 32. MMS MODEL INITIALIZATION

The implementation should use a pinned, tested MMS/Transformers environment.

Conceptually:

```text
model = facebook/mms-1b-all
language adapter = tel
processor = matching MMS processor
```

The current MMS documentation describes loading the processor/model for a target language and switching language adapters with the corresponding target language. The implementation must use the exact API compatible with the pinned Transformers version.

Important:

```text
ISO-639-1 = te
ISO-639-3 = tel
```

Use `tel` for the MMS language adapter where required by the model.

---

# 33. MODEL ADAPTER REQUIREMENT

Do not implement:

```text
set vocab size manually
and assume Telugu is active
```

The correct language-specific MMS configuration must be explicitly loaded using the model's supported target-language/adapter mechanism.

The exact initialization path must be tested against the pinned Transformers version before the full batch run.

---

# 34. MODEL CACHE

The model should be cached under:

```text
models/mms/
```

Cache metadata should include:

```text
model_name
model_revision
files_present
file_sizes
sha256 where practical
language_adapter
```

If a required model file is missing or corrupt, the application should refuse to continue with a false-success state.

---

# 35. MODEL LOADING STRATEGY

Load MMS once per worker process.

Do not load it once for every chunk.

Preferred lifecycle:

```text
start process
  |
  v
load MMS
  |
  v
load Telugu adapter
  |
  v
process many chunks
  |
  v
unload at process exit
```

If the application eventually supports multiple language models, model lifetime should remain worker-scoped.

---

# 36. MMS INPUT

For every chunk:

```text
16 kHz mono float waveform
```

The processor prepares the waveform for the model.

The application should record the exact number of audio samples and the resulting emission frame count.

---

# 37. MMS OUTPUT

The alignment engine needs:

```text
frame-level logits
```

then:

```text
log_probs = log_softmax(logits)
```

Do not immediately take `argmax` and throw away the distribution.

The alignment engine requires the full per-frame probability information.

---

# 38. WHY ARGMAX DECODING IS NOT THE ALIGNMENT

Argmax decoding answers approximately:

```text
what token did the model prefer at each frame?
```

Forced alignment answers:

```text
where does this supplied reference token sequence best fit the acoustic evidence?
```

The Phase 2 objective requires the second behavior.

Therefore the reference text is a direct input to the alignment algorithm.

---

# 39. CTC REFERENCE PREPARATION

For each chunk:

```text
normalized lyric text
       |
       v
MMS tokenizer
       |
       v
reference token IDs
```

The system must also create a mapping from:

```text
token positions
```

to:

```text
word positions
```

because the tokenizer's units and human word boundaries are not necessarily identical.

---

# 40. TOKENIZATION MAPPING

Maintain:

```text
reference_token_index
word_index
line_index
original_word_index
```

A token may map to:

- one word
- a repeated sub-token/character sequence belonging to one word
- a special/blank-compatible element

The token-to-word mapping must be deterministic and unit-tested.

---

# 41. CTC ALIGNMENT ALGORITHM

Implement the actual forced alignment behind:

```text
src/ctc_aligner.py
```

The algorithm should be isolated from MMS loading and LRC parsing.

Inputs:

```text
log_probs[T, C]
reference_tokens[U]
blank_token_id
```

Output:

```text
token spans
path scores
```

---

# 42. CTC TRELLIS CONCEPT

The forced-alignment implementation should use a dynamic-programming/Viterbi-style CTC path search.

Conceptually expand the target:

```text
blank, token1, blank, token2, blank, ..., tokenU, blank
```

At each frame, evaluate the permitted CTC transitions.

The implementation must handle repeated target tokens correctly.

For repeated neighboring tokens, the skip transition must respect CTC's repeated-label rules.

---

# 43. CTC ALIGNMENT OUTPUT

For every target token that receives an aligned span, produce:

```text
token_id
token_start_frame
token_end_frame
mean_log_probability
geometric_mean_probability
```

Frame indices are then converted to absolute milliseconds using the actual model emission frame rate derived for the exact implementation.

Do not hard-code an assumed frame stride without measuring/deriving it from the model configuration.

---

# 44. TOKEN TIMESTAMP CONVERSION

Each token span is initially local to the chunk.

Example:

```text
local_start_ms = 742
local_end_ms = 1038
```

Then convert to song time using the chunk's model-audio origin:

```text
absolute_start_ms = audio_start_ms + local_start_ms
absolute_end_ms   = audio_start_ms + local_end_ms
```

After that, logical-range filtering decides whether the token is retained.

---

# 45. WORD SPAN CONSTRUCTION

Group token spans according to the original reference word boundaries.

For each word:

```text
word_start_ms = first aligned token start
word_end_ms   = last aligned token end
```

If internal tokens contain gaps, preserve the overall word span while recording the alignment score.

---

# 46. WORD ALIGNMENT SCORE

The score should be derived from the CTC alignment path, not from an arbitrary single-frame maximum.

Recommended internal measures:

```text
mean_log_prob
geomean_prob
min_frame_prob
```

A convenience field:

```text
alignment_score
```

may be normalized to a 0–1 range, but it must be documented as a heuristic quality score rather than a calibrated probability of correctness.

---

# 47. LOW-CONFIDENCE WORDS

A word becomes low-confidence if its alignment score falls below the configured threshold or if its span is structurally suspicious.

Potential reasons:

```text
low acoustic score
very short span
very long span
unexpected gap
anchor drift
unsupported tokenization
```

Do not automatically delete a low-confidence word.

Keep it and mark it.

---

# 48. MISSING WORDS

A missing word means the reference word could not be assigned a trustworthy direct acoustic span.

It must remain in the reference order.

Possible final states:

```text
aligned
interpolated
missing
unsupported
```

---

# 49. INTERPOLATED WORDS

Interpolation is allowed only as a fallback.

If:

```text
previous trustworthy word = A
next trustworthy word = D
missing = B, C
```

the system may estimate B/C positions within the gap.

The method must be deterministic.

Every interpolated word must contain:

```text
source = interpolated
is_interpolated = true
```

and an interpolation reason.

Never report an interpolated timestamp as though it came directly from MMS/CTC.

---

# 50. CHUNK RETRIES

Every chunk should have an attempt count.

Recommended maximum:

```text
2 attempts
```

Attempt 1:

```text
standard model audio
```

Attempt 2 may change:

- model-audio overlap
- search window
- alignment audio source
- device
- chunk split

Do not simply rerun the exact same failed computation without changing a known failure condition.

---

# 51. LOW-CONFIDENCE CHUNK RETRY STRATEGY

When a chunk is low-confidence:

```text
1. inspect boundary/anchor drift
2. expand or contract model context
3. try original mix if vocal stem is suspicious
4. if the chunk contains multiple weak lines, split at a safe boundary
5. rerun CTC alignment
6. retain the best validated result
```

This is preferable to blindly averaging poor outputs.

---

# 52. OVERLAP DEDUPLICATION

Because chunks overlap, the same word can appear more than once in different local results.

For each duplicate candidate group:

1. prefer the candidate inside the chunk's logical region
2. then prefer the candidate with higher score
3. then prefer the candidate closer to the original LRC anchor structure
4. then use deterministic tie-breaking by chunk index

Only one word record survives into the canonical song alignment.

---

# 53. GLOBAL MERGE

The merge stage performs:

```text
local token spans
      |
      v
absolute timestamps
      |
      v
word construction
      |
      v
overlap deduplication
      |
      v
line assignment
      |
      v
song-wide chronological ordering
```

The merge must be deterministic.

Given the same inputs, model revision, configuration, and code version, the resulting ordering should be reproducible within the limits of the pinned runtime.

---

# 54. LINE-LEVEL RECONSTRUCTION

For every source LRC lyric line:

```text
original line text
```

remains authoritative for display.

The newly aligned word spans are mapped back into that line.

The new line start is:

```text
start of first directly or acceptably inferred word
```

This becomes the line-level anchor used inside the final JSON and word-level LRC export.

---

# 55. ORIGINAL LRC ANCHOR COMPARISON

For each line compare:

```text
source_lrc_start_ms
new_aligned_line_start_ms
```

Compute:

```text
shift_ms = new - original
absolute_shift_ms
```

Song-level metrics:

```text
median_anchor_shift_ms
mean_absolute_anchor_shift_ms
p90_anchor_shift_ms
max_anchor_shift_ms
```

These are valuable because the LRC already provides coarse timing information.

---

# 56. ANCHOR DRIFT DETECTION

Possible warning conditions:

```text
many consecutive lines shift in the same wrong direction
large unexplained shift at one line
sudden discontinuity between neighboring line shifts
alignment collapses into a neighboring verse/chorus
```

If severe:

```text
quality_status = needs_review
```

Do not fail every small anchor deviation. The purpose is to detect obvious alignment mistakes, not to force identical timestamps.

---

# 57. INSTRUMENTAL SECTION INFERENCE

An instrumental section is a region with:

```text
no reliable aligned lyric words
+
weak vocal/speech activity
+
large LRC gap or blank marker
```

Use evidence from:

- LRC gaps
- blank markers
- VAD
- energy
- final word spans

rather than VAD alone.

---

# 58. INSTRUMENTAL SECTION OUTPUT

The database and final JSON may contain:

```text
start_ms
end_ms
section_type
source_evidence
confidence
```

Possible `section_type` values:

```text
candidate_instrumental
confirmed_instrumental
silence
unknown_non_lyric
```

---

# 59. SAMPLE SONG GAP HANDLING

For the sample song, the two long blank regions should be recognized as high-value boundaries:

```text
97.290 -> 132.940 sec
191.720 -> 252.820 sec
```

The system should not try to force lyric words into those long empty regions.

Instead they should strongly influence:

- chunk boundaries
- model search windows
- validation
- instrumental candidate detection

---

# 60. CANONICAL WORD RECORD

Each final word should conceptually contain:

```json
{
  "line_index": 0,
  "word_index": 0,
  "original": "గెలుపు",
  "normalized": "గెలుపు",
  "start_ms": 25020,
  "end_ms": 25400,
  "score": 0.91,
  "source": "aligned",
  "interpolated": false
}
```

Optional fields:

```text
chunk_index
alignment_token_start
alignment_token_end
mean_log_probability
```

These optional diagnostic fields can remain in the database while the final JSON keeps the most useful subset.

---

# 61. CANONICAL LINE RECORD

Conceptually:

```json
{
  "line_index": 0,
  "source_lrc_start_ms": 25020,
  "aligned_start_ms": 25020,
  "original_text": "గెలుపు తలుపులే తీసే ఆకాశమే",
  "words": [
    {
      "original": "గెలుపు",
      "normalized": "గెలుపు",
      "start_ms": 25020,
      "end_ms": 25400,
      "score": 0.91,
      "source": "aligned"
    }
  ]
}
```

---

# 62. FINAL LRC DESIGN

The user has requested one final `.lrc` per song.

Therefore Phase 2 should not produce three separate LRC files by default.

The single final LRC should be the **word-level project LRC export**.

Recommended syntax:

```text
[00:25.02] ગెలుపు [00:25.40] తలుపులే [00:25.92] తీసే [00:26.20] ఆకాశమే
```

The first timestamp is also the line's start.

Each following word has its own timestamp.

Important:

This is an enhanced/project-specific word-level LRC representation, not something every basic LRC player is guaranteed to parse word-by-word.

The MP3 SYLT and final JSON are the authoritative machine-readable word-level forms.

---

# 63. LRC WORD TIMESTAMP PRECISION

The canonical database and JSON retain integer milliseconds.

The LRC renderer may use centiseconds because conventional LRC syntax is commonly represented to hundredths of a second.

Example:

```text
canonical: 25123 ms
LRC:       00:25.12
```

The rounding rule must be deterministic.

Do not use the rounded LRC timestamps to reconstruct the canonical word timing.

---

# 64. BLANK MARKERS IN FINAL LRC

The final LRC may preserve source blank-marker timestamps where they represent meaningful non-lyric boundaries.

Example:

```text
[01:37.29]
...
[03:11.72]
```

The rendering policy should be configured so that blank markers are either preserved or omitted consistently.

Recommended default:

```text
preserve source blank markers
```

because they can be useful to downstream players and preserve the original synchronization structure.

---

# 65. FINAL MP3 STRATEGY

The output MP3 is created from a direct copy of the original MP3.

Conceptually:

```text
original MP3
   |
   v
byte-for-byte copy
   |
   v
open ID3
   |
   v
add Phase 2 word-level SYLT
   |
   v
save
```

The audio payload must not be recompressed or transcoded by Phase 2 merely to change lyrics metadata.

---

# 66. METADATA PRESERVATION STRATEGY

Before modifying the output MP3, snapshot:

```text
frame keys
frame counts
important frame payload hashes
artwork hash/size
```

After modification, verify that all pre-existing metadata remains present unless the frame is explicitly the Phase 2 target frame.

The sample has existing metadata such as:

```text
TIT2
TPE1
TRCK
TALB
TPOS
TDRC
TCON
TLEN
TSRC
TPE2
TXXX:* custom fields
UFID:* identifiers
WXXX:* URLs
USLT
SYLT
APIC
```

The exact set may differ by song. The code must preserve whatever the input actually contains.

---

# 67. EXISTING SYLT MUST BE PRESERVED

The sample input already contains an existing SYLT frame.

Therefore the Phase 2 embedder must not do:

```python
if "SYLT" in tags:
    delete all SYLT
```

Instead the embedder should target its own unique descriptor.

Example conceptual descriptor:

```text
Phase2-WordLevel
```

Keep the pre-existing SYLT frame untouched.

---

# 68. PHASE 2 SYLT DESIGN

Create a synchronized lyrics frame using:

```text
language = tel
format = milliseconds
content type = lyrics
```

Use Unicode encoding supported by the chosen Mutagen/ID3 configuration.

The text entries should follow the canonical word-level timeline.

The exact SYLT descriptor must be unique and stable so that future Phase 2 reruns can replace only the previous Phase 2 frame.

---

# 69. PHASE 2 SYLT REPLACEMENT RULE

On rerun:

```text
find existing SYLT with Phase2 descriptor
     |
     v
replace only that frame
```

Do not replace:

- unrelated language frames
- unrelated descriptors
- existing lyric frames
- event frames
- other synchronization data

---

# 70. MP3 POST-EMBED VALIDATION

After saving the final-stage MP3:

1. Re-open the file.
2. Read its audio duration.
3. Confirm the audio still decodes.
4. Confirm the new Phase 2 SYLT exists.
5. Confirm the expected number of word entries.
6. Confirm timestamps are sorted.
7. Confirm timestamps are within duration.
8. Confirm the original metadata snapshot still matches.
9. Confirm artwork is still present when it was present before.
10. Confirm the file is not truncated or corrupt.

---

# 71. JSON OUTPUT GENERATION

The final JSON must be created from:

```text
original JSON object
```

plus:

```text
phase2
```

It must not be created from only a subset of the original data.

Recommended serialization:

```text
UTF-8
pretty-printed or consistently indented
ensure_ascii=false
```

so Telugu remains readable.

Do not alter numeric types unnecessarily.

Do not convert every number to strings merely for convenience.

---

# 72. PHASE 2 JSON ALIGNMENT CONTENT

The final JSON should contain enough word-level data to reconstruct the final LRC and inspect alignment without opening SQLite.

Recommended:

```text
phase2.alignment.lines[].words[]
```

For every word:

```text
original
normalized
start_ms
end_ms
score
source
```

This makes the final JSON self-contained.

---

# 73. JSON SIZE MANAGEMENT

The sample JSON is already large because it contains raw metadata.

Adding a few hundred word records is acceptable.

However, avoid duplicating:

- complete MMS logits
- complete chunk audio
- huge intermediate arrays
- entire model metadata blobs

inside the final JSON.

Those belong in temp/debug or logs if needed.

Final JSON should contain results and provenance, not raw inference tensors.

---

# 74. QUALITY METRICS

The final song should record at least:

```text
expected_lines
aligned_lines
expected_words
aligned_words
interpolated_words
missing_words
unsupported_words

total_chunks
successful_chunks
low_confidence_chunks
failed_chunks

mean_alignment_score
p10_alignment_score
minimum_alignment_score
low_score_word_percent
interpolated_word_percent
failed_audio_percent

median_anchor_shift_ms
p90_anchor_shift_ms
max_anchor_shift_ms
```

---

# 75. QUALITY METRIC PRINCIPLE

Never rely on a single average score.

Example:

```text
95% of words excellent
5% of words unusable
```

could still have a high mean.

Therefore use distribution metrics such as:

```text
mean
p10
minimum
low-score fraction
```

The lower tail is important.

---

# 76. VALIDATION — TIMING BOUNDS

Every canonical word must satisfy:

```text
0 <= start_ms < end_ms <= source_duration_ms
```

Any violation is a validation error.

---

# 77. VALIDATION — CHRONOLOGICAL ORDER

Within a line:

```text
word[n].start_ms <= word[n+1].start_ms
```

and generally:

```text
word[n].end_ms <= word[n+1].end_ms
```

Allow exact boundary equality if quantization causes it and the internal continuous representation remains valid.

Do not require every LRC timestamp to be strictly increasing because LRC export precision may collapse nearby millisecond values into the same centisecond.

---

# 78. VALIDATION — WORD DURATION

Every aligned word should have:

```text
end_ms > start_ms
```

Suspicious conditions:

```text
very tiny duration
very long duration
```

should produce warnings or low-confidence status rather than an immediate hard failure unless the span is structurally impossible.

---

# 79. VALIDATION — REFERENCE PRESERVATION

The expected reference sequence is derived from the LRC.

The final word sequence should preserve:

- line order
- word order
- original wording

Any difference must be explicitly classified as:

```text
normalized-only
unsupported
missing
interpolated
```

There should not be silent substitutions.

---

# 80. VALIDATION — ANCHOR DRIFT

Compare every aligned line with its source LRC anchor.

Recommended initial warning threshold:

```text
2500 ms
```

but use aggregate metrics rather than a simplistic rule that every line must be within exactly one threshold.

A song may have one slightly shifted line without being unusable.

A coherent large-scale drift is more serious.

---

# 81. VALIDATION — LRC/JSON CONSISTENCY

The final LRC and final JSON must be generated from the exact same canonical word data.

After generation, test:

```text
number of lines matches
word order matches
line words match
LRC timestamps correspond to JSON start_ms after documented rounding
```

Do not generate the JSON and LRC through independent timing calculations.

---

# 82. VALIDATION — MP3/JSON CONSISTENCY

The final JSON should state the final MP3 path and its final SHA-256 after embedding.

The final output file hash should be computed after the last modification.

This should be different from the original MP3 hash in the normal case because the MP3 metadata changed.

The original hash remains stored under:

```text
phase2.input.mp3_sha256
```

---

# 83. VALIDATION — SOURCE INTEGRITY

Before processing:

```text
source_hash = H(original MP3)
```

After all processing:

```text
source_hash_after = H(original MP3)
```

Require:

```text
source_hash_after == source_hash
```

This is one of the most important safety checks for the project.

---

# 84. PARTIAL RESULT POLICY

A song can be complete as a processing artifact while having some partial alignment.

Therefore classify separately:

```text
pipeline_status
quality_status
```

Example:

```text
pipeline_status = finished
quality_status = partial
```

This means the pipeline finished and produced valid files, but some timing was interpolated or unresolved.

---

# 85. RECOMMENDED QUALITY STATES

```text
good
partial
needs_review
failed
```

### good

Direct alignment is generally strong, outputs validate, and no major drift is detected.

### partial

Some words/chunks required interpolation/fallback but the package is still usable.

### needs_review

Processing completed but validation found suspicious timing or quality.

### failed

A trustworthy final package could not be produced.

---

# 86. DO NOT CLASSIFY ONLY BY FAILED-CHUNK PERCENTAGE

A failed chunk containing an entire chorus can be much more important than several short failed chunks.

Quality should therefore consider:

```text
failed word count
failed audio duration
interpolated word count
low-score word concentration
anchor drift
```

rather than only:

```text
failed_chunks / total_chunks
```

---

# 87. DATABASE ARCHITECTURE

The Phase 2 database is independent:

```text
db/phase2.db
```

It must not modify or attach to the Phase 1 database.

Recommended tables:

```text
songs
chunks
words
instrumental_sections
processing_log
runs
```

---

# 88. `songs` TABLE

Recommended schema:

```sql
CREATE TABLE songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    basename TEXT NOT NULL UNIQUE,

    original_mp3_path TEXT NOT NULL,
    original_lrc_path TEXT NOT NULL,
    original_json_path TEXT,

    original_mp3_sha256 TEXT NOT NULL,
    original_lrc_sha256 TEXT NOT NULL,
    original_json_sha256 TEXT,

    final_mp3_path TEXT,
    final_lrc_path TEXT,
    final_json_path TEXT,

    title TEXT,
    artist TEXT,
    album TEXT,

    duration_ms INTEGER,

    expected_lines INTEGER DEFAULT 0,
    aligned_lines INTEGER DEFAULT 0,

    expected_words INTEGER DEFAULT 0,
    aligned_words INTEGER DEFAULT 0,
    interpolated_words INTEGER DEFAULT 0,
    missing_words INTEGER DEFAULT 0,
    unsupported_words INTEGER DEFAULT 0,

    total_chunks INTEGER DEFAULT 0,
    successful_chunks INTEGER DEFAULT 0,
    low_confidence_chunks INTEGER DEFAULT 0,
    failed_chunks INTEGER DEFAULT 0,

    mean_alignment_score REAL,
    p10_alignment_score REAL,
    minimum_alignment_score REAL,

    low_score_word_percent REAL,
    interpolated_word_percent REAL,
    failed_audio_percent REAL,

    median_anchor_shift_ms REAL,
    p90_anchor_shift_ms REAL,
    max_anchor_shift_ms REAL,

    pipeline_status TEXT NOT NULL DEFAULT 'pending',
    quality_status TEXT NOT NULL DEFAULT 'unknown',

    retry_count INTEGER DEFAULT 0,
    error_code TEXT,
    error_remark TEXT,

    pipeline_version TEXT,
    model_name TEXT,
    model_revision TEXT,
    normalizer_version TEXT,
    config_hash TEXT,

    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

# 89. `chunks` TABLE

```sql
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    song_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,

    logical_start_ms INTEGER NOT NULL,
    logical_end_ms INTEGER NOT NULL,

    audio_start_ms INTEGER NOT NULL,
    audio_end_ms INTEGER NOT NULL,

    line_start_index INTEGER,
    line_end_index INTEGER,

    text_content TEXT NOT NULL,
    normalized_text TEXT NOT NULL,

    word_count INTEGER DEFAULT 0,

    alignment_score REAL,
    p10_alignment_score REAL,
    minimum_alignment_score REAL,

    status TEXT NOT NULL DEFAULT 'pending',

    audio_path TEXT,
    result_json_path TEXT,

    attempt_count INTEGER DEFAULT 0,

    error_code TEXT,
    error_remark TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(song_id) REFERENCES songs(id),
    UNIQUE(song_id, chunk_index)
);
```

---

# 90. `words` TABLE

```sql
CREATE TABLE words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    song_id INTEGER NOT NULL,
    chunk_id INTEGER,

    line_index INTEGER NOT NULL,
    word_index INTEGER NOT NULL,

    original_word TEXT NOT NULL,
    normalized_word TEXT NOT NULL,

    start_ms INTEGER,
    end_ms INTEGER,

    alignment_score REAL,

    source TEXT NOT NULL,
    -- aligned / interpolated / missing / unsupported

    is_interpolated INTEGER NOT NULL DEFAULT 0,

    FOREIGN KEY(song_id) REFERENCES songs(id),
    FOREIGN KEY(chunk_id) REFERENCES chunks(id)
);
```

---

# 91. `instrumental_sections` TABLE

```sql
CREATE TABLE instrumental_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    song_id INTEGER NOT NULL,

    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,

    section_type TEXT NOT NULL,

    detector TEXT,
    confidence REAL,
    evidence_json TEXT,

    FOREIGN KEY(song_id) REFERENCES songs(id)
);
```

---

# 92. `processing_log` TABLE

```sql
CREATE TABLE processing_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    song_id INTEGER,

    step TEXT NOT NULL,
    level TEXT NOT NULL,

    attempt INTEGER DEFAULT 1,

    message TEXT,
    metadata_json TEXT,

    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

# 93. `runs` TABLE

```sql
CREATE TABLE runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,

    pipeline_version TEXT NOT NULL,
    config_hash TEXT NOT NULL,

    model_name TEXT NOT NULL,
    model_revision TEXT,
    language_code TEXT NOT NULL,
    normalizer_version TEXT NOT NULL
);
```

---

# 94. PIPELINE STATUS STATE MACHINE

Processing state:

```text
pending
   ↓
scanning
   ↓
lyrics_loaded
   ↓
isolating
   ↓
isolated
   ↓
chunking
   ↓
chunked
   ↓
aligning
   ↓
aligned
   ↓
merging
   ↓
merged
   ↓
validating
   ↓
validated
   ↓
embedding
   ↓
finalizing
   ↓
finished
```

Terminal error state can be represented separately by `quality_status` or an explicit error code.

---

# 95. QUALITY STATE MACHINE

Separate field:

```text
unknown
   ↓
good / partial / needs_review / failed
```

This separation prevents ambiguous states such as one string simultaneously meaning "processing stopped" and "output quality is questionable."

---

# 96. RESUME MODEL

On program restart:

```text
open DB
   |
   v
inspect unfinished songs
   |
   v
inspect last safe stage
   |
   v
resume from checkpoint
```

Examples:

```text
isolated
-> resume chunking
```

```text
chunked
-> resume alignment
```

```text
aligned
-> resume merge
```

```text
merged
-> resume validation
```

```text
validated
-> resume embedding/finalization
```

---

# 97. STALE JOB RECOVERY

If a process crashes while a song is marked:

```text
aligning
```

the program must not assume that another process is still working.

Use:

```text
updated_at
started_at
attempt_count
```

and a configurable stale timeout.

A stale record becomes resumable.

---

# 98. IDEMPOTENT RE-RUN

On a new run, if:

```text
original MP3 hash unchanged
original LRC hash unchanged
original JSON hash unchanged
pipeline version unchanged
config hash unchanged
model revision unchanged
final outputs exist
final outputs validate
```

then skip processing.

If any of those change, process again.

---

# 99. FORCE REPROCESS

Recommended CLI mode:

```text
--force
```

This must not edit source files.

It should simply rebuild a new final package and replace the previous final package only after validation succeeds.

---

# 100. RECOVERY AFTER PARTIAL FINALIZATION

A crash could occur after:

```text
final MP3 written
```

but before:

```text
final JSON updated
```

Therefore startup should check:

```text
final MP3 exists
final LRC exists
final JSON exists
DB says finished?
```

If DB does not confirm a successful package, validate the files and either:

```text
complete the database record
```

or:

```text
discard/replace the incomplete staged package
```

Do not mark success solely because files happen to exist.

---

# 101. STAGING FINAL OUTPUTS

Do not write directly into `songs/final/` during processing.

Use:

```text
temp/{song_key}/stage_final/
```

Create and validate:

```text
stage_final/Song.mp3
stage_final/Song.lrc
stage_final/Song.json
```

Only after all three are valid should they be promoted to `songs/final/`.

---

# 102. FINALIZATION ORDER

Recommended order:

```text
1. build final JSON in stage
2. build final LRC in stage
3. build final MP3 in stage
4. validate all three
5. validate source unchanged
6. compute output hashes
7. promote final files
8. record final database state
```

If any validation fails, keep the stage files for debugging and do not claim success.

---

# 103. FINAL OUTPUT FILE NAMES

The basename must not change.

Example:

```text
input:
001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.mp3

output:
001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.mp3
```

Likewise for `.lrc` and `.json`.

No title normalization should change filenames during Phase 2.

---

# 104. FINAL LRC GENERATOR MODULE

`src/lrc_generator.py` responsibilities:

- consume canonical word records
- keep original lyric text
- round canonical milliseconds for LRC
- emit line-level first timestamp
- emit word timestamps
- preserve blank marker policy
- preserve relevant LRC metadata if desired
- generate deterministic output

It must not perform fresh alignment calculations.

---

# 105. EMBEDDER MODULE

`src/embedder.py` responsibilities:

- copy source MP3 into staging
- open existing tags
- identify Phase 2-owned SYLT descriptor
- replace only the old Phase 2 frame if present
- add the new Phase 2 SYLT
- save
- reopen
- validate

No audio transcoding.

---

# 106. JSON UPDATER MODULE

`src/json_updater.py` responsibilities:

- deep-copy source JSON structure
- add/update `phase2`
- preserve unknown fields
- include input hashes
- include model provenance
- include output paths
- include final quality results
- include word-level alignment
- serialize UTF-8 safely

---

# 107. SCANNER MODULE

`src/scanner.py` responsibilities:

- scan input directory
- identify basename packages
- detect missing sidecars
- calculate hashes
- detect duplicates
- create/update song rows
- produce scan summary

It should not perform heavy ML work.

---

# 108. JSON MANAGER MODULE

`src/json_manager.py` responsibilities:

- parse JSON
- deep-copy original data
- provide metadata accessors
- compute source JSON hash
- protect unknown fields
- provide a controlled phase2 namespace updater

---

# 109. LRC READER MODULE

`src/lrc_reader.py` responsibilities:

- parse timestamps
- preserve text
- detect blank markers
- detect metadata tags
- construct ordered lyric lines
- calculate source timing intervals

---

# 110. AUDIO MODULE

`src/audio.py` responsibilities:

- inspect MP3
- decode source audio
- resample
- mono conversion
- slice audio for chunks
- validate duration
- support deterministic sample indexing

---

# 111. DEMUCS MODULE

`src/demucs_isolator.py` responsibilities:

- Demucs model execution
- GPU/CPU fallback
- memory management
- vocal stem extraction
- duration normalization
- output validation

---

# 112. ACTIVITY MODULE

`src/activity_detector.py` responsibilities:

- load Silero VAD
- compute speech/activity timestamps
- compute energy map
- merge activity signals
- expose pause candidates

It should not directly modify chunk or song DB rows outside controlled pipeline calls.

---

# 113. NORMALIZER MODULE

`src/telugu_normalizer.py` responsibilities:

- NFC normalization
- whitespace normalization
- optional numeric conversion
- optional abbreviation expansion
- token compatibility normalization
- original-to-normalized mapping
- normalization versioning

---

# 114. TOKENIZER MODULE

`src/tokenizer.py` responsibilities:

- interface with the pinned MMS tokenizer
- tokenize normalized reference text
- map token indices to word indices
- expose blank token ID
- expose vocabulary metadata

---

# 115. CHUNKER MODULE

`src/chunker.py` responsibilities:

- construct logical lyric chunks
- add model context overlap
- use LRC anchors
- use VAD/energy boundaries
- avoid lyric phrase splitting
- generate chunk text
- write chunk DB records

---

# 116. MMS MODEL MODULE

`src/mms_model.py` responsibilities:

- load MMS
- load Telugu adapter
- manage model device
- generate frame-level emissions
- keep model loaded
- provide a narrow interface to CTC aligner

The module must not convert emissions into final words.

---

# 117. CTC ALIGNER MODULE

`src/ctc_aligner.py` responsibilities:

- accept frame-level log probabilities
- accept reference token sequence
- perform reference-driven forced alignment
- return token spans and path scores
- handle repeated target tokens correctly
- handle impossible alignments gracefully

This is the core research/algorithmic module of the project.

---

# 118. WORD BUILDER MODULE

`src/word_builder.py` responsibilities:

- map token spans to reference words
- derive word start/end
- calculate word scores
- map normalized words back to originals
- classify aligned/interpolated/missing/unsupported

---

# 119. MERGER MODULE

`src/merger.py` responsibilities:

- local -> absolute timestamp conversion
- overlap deduplication
- line association
- global ordering
- canonical song alignment creation
- gap/instrumental candidate construction

---

# 120. VALIDATOR MODULE

`src/validator.py` responsibilities:

- timing bounds
- chronological checks
- word-span checks
- reference preservation
- score distribution
- anchor drift
- LRC/JSON consistency
- MP3 metadata preservation
- final output validity

---

# 121. RECOVERY MODULE

`src/recovery.py` responsibilities:

- stale job detection
- retry selection
- checkpoint selection
- cleanup decisions
- idempotency checks
- incomplete-final-package recovery

---

# 122. PIPELINE ORCHESTRATOR

`src/pipeline.py` should be orchestration only.

It should not contain detailed CTC math, LRC parsing, metadata logic, or Demucs commands.

Conceptually:

```text
scan
-> load
-> isolate
-> detect
-> normalize
-> chunk
-> infer
-> align
-> merge
-> validate
-> render
-> embed
-> update JSON
-> validate final package
-> promote
```

---

# 123. CONFIGURATION

Recommended `config.json` sections:

```json
{
  "paths": {
    "original_dir": "songs/original",
    "final_dir": "songs/final",
    "temp_dir": "temp",
    "models_dir": "models",
    "db_path": "db/phase2.db"
  },

  "models": {
    "demucs_model": "htdemucs",
    "mms_model": "facebook/mms-1b-all",
    "language_iso1": "te",
    "language_iso3": "tel"
  },

  "audio": {
    "sample_rate": 16000,
    "channels": 1
  },

  "vad": {
    "enabled": true,
    "threshold": 0.50,
    "min_speech_duration_ms": 250,
    "min_silence_duration_ms": 300,
    "speech_pad_ms": 150
  },

  "chunking": {
    "min_seconds": 4,
    "target_seconds": 12,
    "max_seconds": 20,
    "context_before_ms": 500,
    "context_after_ms": 500,
    "pause_threshold_ms": 1500,
    "large_gap_threshold_ms": 3000,
    "anchor_search_ms": 2500
  },

  "alignment": {
    "word_score_min": 0.40,
    "song_mean_score_min": 0.50,
    "max_low_score_word_percent": 20,
    "max_interpolated_word_percent": 20
  },

  "runtime": {
    "device": "cuda",
    "fallback_device": "cpu",
    "workers": 1
  },

  "recovery": {
    "max_chunk_attempts": 2,
    "max_song_attempts": 3,
    "stale_after_minutes": 30
  }
}
```

All thresholds are configurable and benchmark targets, not universal truths.

---

# 124. DEPENDENCY STRATEGY

The implementation should use an exact lockfile rather than only minimum versions.

Core functional categories:

```text
transformers
PyTorch
audio I/O / decoding
Demucs
Silero VAD
librosa or equivalent analysis utilities
soundfile
Mutagen
NumPy
```

Do not rely on deprecated TorchAudio forced-alignment APIs as the core implementation.

Current TorchAudio documentation states that the forced-alignment APIs discussed in older tutorials were deprecated and removed as TorchAudio moved into maintenance mode. Therefore the project should isolate its own CTC aligner and use it independently of deprecated `torchaudio.functional.forced_align` behavior.

Audio I/O should be compatible with the pinned environment and may use current TorchCodec-backed facilities where appropriate.

---

# 125. MMS LICENSE / PROVENANCE

The `facebook/mms-1b-all` model card currently identifies the model as CC-BY-NC-4.0.

The project documentation should record the model license and model revision used.

This does not change the processing design but is important provenance information.

---

# 126. PERFORMANCE DESIGN

The project is intended for long-running batch processing.

Primary performance costs:

```text
Demucs
MMS inference
CTC dynamic programming
audio I/O
```

LRC parsing, normalization, SQLite updates, and JSON augmentation should be comparatively inexpensive.

---

# 127. MODEL MEMORY POLICY

Do not run Demucs and MMS concurrently on the same GPU by default.

Preferred:

```text
Demucs
   |
   v
release Demucs GPU resources
   |
   v
MMS alignment
```

This minimizes VRAM contention.

---

# 128. WORKER POLICY

Default:

```text
1 GPU worker
```

This is the safest initial production configuration.

Parallelism can be added later after memory and throughput benchmarks.

Do not launch many MMS instances against one GPU simply because multiple CPU workers are available.

---

# 129. PERFORMANCE BENCHMARKING PLAN

Before the full corpus run, benchmark at least:

```text
1 short song
1 medium song
1 long song
1 song with heavy instrumental sections
1 song with dense Telugu lyrics
1 song with difficult/low-volume vocals
```

Measure:

```text
Demucs seconds/song
MMS seconds/chunk
CTC seconds/chunk
peak VRAM
peak RAM
I/O throughput
failure rate
```

Use observed results for final throughput estimates.

---

# 130. BATCH PROGRESS REPORTING

The application should periodically print:

```text
processed
finished
good
partial
needs_review
failed
remaining
average processing time
estimated throughput
```

Do not display speculative completion times as guarantees.

---

# 131. LOGGING LEVELS

Support:

```text
INFO
WARNING
ERROR
DEBUG
```

Every major processing step should produce an INFO event.

Every retry should produce a WARNING.

Every unrecoverable failure should produce an ERROR.

---

# 132. STRUCTURED LOGGING

Prefer structured JSON metadata in `processing_log` rather than putting every detail into a long free-text message.

Example:

```json
{
  "step": "ctc_alignment",
  "chunk_index": 7,
  "attempt": 2,
  "device": "cuda",
  "frame_count": 936,
  "token_count": 52,
  "score": 0.74
}
```

---

# 133. ERROR CODES

Use stable error codes.

Recommended:

```text
MP3_MISSING
LRC_MISSING
JSON_MISSING
JSON_INVALID
MP3_INVALID
LRC_INVALID
HASH_ERROR
AUDIO_DECODE_FAILED
DEMUCS_FAILED
VOCALS_INVALID
VAD_FAILED
NORMALIZATION_FAILED
TOKENIZATION_FAILED
MMS_LOAD_FAILED
MMS_INFERENCE_FAILED
CTC_ALIGNMENT_FAILED
TOO_MANY_FAILED_CHUNKS
TIMESTAMP_INVALID
ANCHOR_DRIFT
LRC_GENERATION_FAILED
SYLT_EMBED_FAILED
MP3_VALIDATION_FAILED
JSON_WRITE_FAILED
FINAL_PROMOTION_FAILED
SOURCE_MODIFIED
```

---

# 134. RETRY CLASSIFICATION

Not every error deserves a retry.

### Retryable examples

```text
CUDA OOM
transient file access
temporary model runtime failure
chunk too large
```

### Usually non-retryable

```text
missing LRC
invalid JSON
unsupported audio
corrupt source file
```

### Review-worthy

```text
low confidence
anchor drift
high interpolation rate
unexpected word-span structure
```

---

# 135. SOURCE FILE SAFETY CHECK

At startup and shutdown for a song:

```text
hash original MP3
hash original LRC
hash original JSON
```

The hashes must remain unchanged during Phase 2.

This should be tested automatically, not assumed.

---

# 136. JSON MERGE SAFETY TEST

Before writing the final JSON:

```text
original = deep copy(input_json)
final = deep copy(input_json)
update(final["phase2"])
```

Then verify:

```text
all original top-level keys still exist
all non-phase2 values are unchanged
```

A regression test should compare the original and final JSON after removing only the intentionally added `phase2` subtree.

---

# 137. MP3 METADATA SAFETY TEST

Before embedding:

```text
snapshot frame structure
```

After embedding:

```text
snapshot frame structure
```

Verify:

```text
all pre-existing frame keys remain
all important frame payloads remain equivalent
APIC remains
UFID remains
WXXX remains
custom TXXX remains
existing USLT remains
existing SYLT remains
```

The only expected new/changed data should be the Phase 2-owned SYLT.

---

# 138. FINAL JSON EXAMPLE FOR THE SAMPLE SONG

Conceptually the existing large JSON remains intact and gains:

```json
"phase2": {
  "schema_version": 1,
  "pipeline_version": "1.0.0",
  "status": "finished",
  "quality_status": "good",

  "input": {
    "basename": "001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra",
    "source_type": "external_lrc_plus_json",
    "mp3_sha256": "<original hash>",
    "lrc_sha256": "<original hash>",
    "json_sha256": "<original hash>"
  },

  "audio": {
    "duration_ms": 317592,
    "sample_rate": 16000,
    "channels": 1
  },

  "lyrics": {
    "line_count": 42,
    "lyric_line_count": 39,
    "blank_timing_markers": 3,
    "source": "external_lrc"
  },

  "model": {
    "name": "facebook/mms-1b-all",
    "language": "tel",
    "revision": "<pinned revision>"
  },

  "vocal_isolation": {
    "model": "htdemucs",
    "device": "cuda",
    "status": "success"
  },

  "alignment": {
    "method": "ctc_forced_alignment",
    "lines": []
  },

  "instrumental_sections": [
    {
      "start_ms": 97290,
      "end_ms": 132940,
      "type": "candidate_instrumental",
      "evidence": ["lrc_blank_marker", "lrc_gap", "activity_gap"]
    },
    {
      "start_ms": 191720,
      "end_ms": 252820,
      "type": "candidate_instrumental",
      "evidence": ["lrc_blank_marker", "lrc_gap", "activity_gap"]
    }
  ],

  "quality": {
    "mean_alignment_score": null,
    "p10_alignment_score": null,
    "minimum_alignment_score": null,
    "interpolated_word_percent": null,
    "median_anchor_shift_ms": null,
    "max_anchor_shift_ms": null
  },

  "outputs": {
    "mp3": "songs/final/001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.mp3",
    "lrc": "songs/final/001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.lrc",
    "json": "songs/final/001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.json"
  }
}
```

The actual final JSON should also contain the complete aligned line/word data.

---

# 139. FINAL JSON WORD-LEVEL EXAMPLE

Inside:

```text
phase2.alignment.lines[]
```

an aligned line should look like:

```json
{
  "line_index": 0,
  "source_lrc_start_ms": 25020,
  "aligned_start_ms": 25020,
  "original_text": "గెలుపు తలుపులే తీసే ఆకాశమే",
  "words": [
    {
      "word_index": 0,
      "original": "గెలుపు",
      "normalized": "గెలుపు",
      "start_ms": 25020,
      "end_ms": 25450,
      "score": 0.89,
      "source": "aligned"
    },
    {
      "word_index": 1,
      "original": "తలుపులే",
      "normalized": "తలుపులే",
      "start_ms": 25480,
      "end_ms": 26110,
      "score": 0.92,
      "source": "aligned"
    }
  ]
}
```

These numbers are illustrative. The actual system must derive them from the model alignment.

---

# 140. FINAL LRC EXAMPLE

For the same illustrative result:

```text
[00:25.02] గెలుపు [00:25.48] తలుపులే [00:26.11] తీసే [00:26.68] ఆకాశమే
```

Do not hard-code example times into the implementation.

---

# 141. FINAL MP3 SYLT EXAMPLE

Canonical data:

```text
(
  "గెలుపు", 25020
)
(
  "తలుపులే", 25480
)
(
  "తీసే", 26110
)
(
  "ఆకాశమే", 26680
)
```

This same timing is stored in the Phase 2-owned SYLT frame.

---

# 142. ONE SOURCE OF TRUTH

The following must all derive from the same canonical word data:

```text
final JSON
final LRC
final MP3 SYLT
SQLite words table
```

There must not be independent timing calculations in each exporter.

---

# 143. EXPORT ORDER

Recommended internal flow:

```text
canonical alignment
       |
       +--> database words
       |
       +--> JSON alignment
       |
       +--> LRC export
       |
       `--> SYLT export
```

---

# 144. VALIDATION BEFORE EXPORT

Do not generate final outputs from an invalid canonical alignment.

Order:

```text
merge
  |
  v
canonical validation
  |
  +-- fail -> review/debug
  |
  `-- pass -> exporters
```

---

# 145. VALIDATION AFTER EXPORT

After all outputs are built:

```text
validate JSON
validate LRC
validate MP3
validate metadata preservation
validate cross-file consistency
```

Only then promote.

---

# 146. LRC VALIDATION

Check:

```text
timestamps parse
words are present
word order is preserved
line order is preserved
timestamps are non-decreasing
all times are within song duration
blank marker policy is respected
```

---

# 147. JSON VALIDATION

Check:

```text
valid UTF-8
valid JSON syntax
all original top-level keys exist
phase2 exists
alignment word count consistent
outputs paths correct
source hashes correct
status correct
```

---

# 148. MP3 VALIDATION

Check:

```text
file exists
file decodes
ID3 loads
new Phase2 SYLT exists
old metadata still exists
artwork still exists where originally present
source audio duration unchanged
```

---

# 149. CROSS-FILE VALIDATION

The three final files should agree on:

```text
basename
title where applicable
duration
line count
word count
processing version
output identity
```

The MP3 and JSON should also agree on the existence of the Phase 2 word-level SYLT output.

---

# 150. FINAL OUTPUT HASHES

Record final hashes:

```text
final_mp3_sha256
final_lrc_sha256
final_json_sha256
```

Store these in the database and in:

```text
phase2.outputs
```

inside the final JSON.

---

# 151. OUTPUT PATHS IN JSON

Always use the actual final relative paths:

```text
songs/final/SongName.mp3
songs/final/SongName.lrc
songs/final/SongName.json
```

Do not store temporary absolute paths in the final JSON unless a dedicated debug field is explicitly desired.

---

# 152. TEMP CLEANUP POLICY

After successful finalization:

```text
remove temp/{song_key}/
```

After `needs_review` or `failed`:

```text
retain temp/{song_key}/
```

This keeps debugging artifacts only when they are useful.

---

# 153. TEMP RETENTION POLICY

Retained failed/review artifacts should include:

```text
source snapshot metadata
source_16k.wav
vocals_16k.wav
chunk audio
chunk normalized text
chunk alignment results
processing logs
```

Do not retain gigantic raw model logits by default.

They may optionally be enabled with a debug flag for one song.

---

# 154. DEBUG MODE

Recommended:

```text
--debug
--keep-temp
--song <basename>
```

Debug mode should make it easy to inspect one problematic song without changing batch behavior.

---

# 155. DRY RUN

Recommended:

```text
--dry-run
```

Dry run should:

- scan files
- verify matching
- hash inputs
- validate JSON
- parse LRC
- inspect audio metadata
- report expected work

It must not run Demucs, MMS, or modify outputs.

---

# 156. SINGLE-SONG MODE

Required for development and acceptance testing:

```text
--song "001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra"
```

The exact CLI syntax can be adjusted during implementation.

---

# 157. BATCH MODES

Recommended operations:

```text
--all
--failed
--needs-review
--missing-output
--song <basename>
--force
```

---

# 158. TESTING STRATEGY

The project must not start with the full corpus.

Test in layers.

---

# 159. UNIT TESTS — FILE MATCHING

Test:

```text
Song.mp3 + Song.lrc + Song.json
```

Also:

```text
Song.mp3 only
Song.mp3 + Song.lrc
Song.mp3 + Song.json
```

and duplicate basenames.

---

# 160. UNIT TESTS — LRC PARSER

Test:

```text
[00:25.02] Telugu line
```

```text
[01:37.29]
```

```text
[00:25.020] line
```

```text
multiple same timestamps
```

Test malformed timestamps.

---

# 161. UNIT TESTS — JSON PRESERVATION

Create a fixture containing:

```text
known keys
unknown keys
nested objects
nested arrays
null values
Unicode Telugu text
```

After Phase 2 update, verify all original values remain identical outside `phase2`.

---

# 162. UNIT TESTS — NORMALIZATION

Test:

```text
Telugu Unicode normalization
multiple spaces
leading/trailing whitespace
numbers
Latin fragments
punctuation
abbreviations
```

Verify the original word remains recoverable.

---

# 163. UNIT TESTS — CTC ALIGNER

Create synthetic emissions where the correct token sequence has an obvious best path.

Test:

```text
single token
multiple tokens
repeated token
blank-heavy region
short reference
long reference
impossible reference
```

The repeated-token test is especially important because CTC transition rules are easy to implement incorrectly.

---

# 164. UNIT TESTS — TOKEN TO WORD MAPPING

Test:

```text
one token per word
multiple tokens per word
repeated characters
blank-separated units
```

Verify word spans map back to correct original words.

---

# 165. UNIT TESTS — LRC RENDERER

Given a known canonical alignment, expected LRC output should be exact.

Test rounding at:

```text
124 ms
125 ms
129 ms
130 ms
```

and near second/minute boundaries.

---

# 166. UNIT TESTS — SYLT EMBEDDING

Use a fixture MP3 containing many different metadata frames.

Before:

```text
snapshot
```

After embedding:

```text
verify old metadata
verify new SYLT
```

This protects the most important metadata-preservation requirement.

---

# 167. INTEGRATION TEST — SAMPLE SONG

Use:

```text
001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.mp3
001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.lrc
001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.json
```

Expected input characteristics:

```text
song duration ~318 sec
39 lyric lines
3 blank markers
2 major blank regions
large metadata JSON
many existing MP3 ID3 frames
existing SYLT/USLT/APIC
```

---

# 168. SAMPLE SONG ACCEPTANCE TESTS

For the sample song, verify:

1. All three source files are matched by basename.
2. Source SHA-256 values are captured.
3. Source JSON loads.
4. Source LRC produces 42 timestamp entries.
5. 39 lyric lines are recognized.
6. 3 blank markers are recognized.
7. The two large lyric-free gaps are detected as candidate boundaries.
8. Demucs produces a valid vocal stem.
9. MMS loads with Telugu adapter.
10. At least one real CTC reference alignment completes.
11. Final word count is recorded.
12. Existing JSON top-level keys survive unchanged.
13. Final JSON gains `phase2`.
14. Existing MP3 artwork survives.
15. Existing MP3 custom TXXX/UFID/WXXX data survives.
16. Existing SYLT/USLT survive.
17. New Phase2 SYLT exists.
18. Final LRC exists.
19. Final JSON exists.
20. All three files share the same basename.
21. Source MP3/LRC/JSON hashes remain unchanged.

---

# 169. FAILURE-INJECTION TESTS

Deliberately test:

```text
missing LRC
invalid JSON
corrupt MP3
Demucs failure
CUDA unavailable
MMS loading failure
MMS OOM
CTC alignment failure
one failed chunk
multiple failed chunks
JSON write interruption
MP3 embed failure
process kill during alignment
process kill during finalization
```

The system must recover or fail cleanly according to its documented state.

---

# 170. METADATA-LOSS REGRESSION TEST

This test is mandatory.

Take the real sample MP3.

Record every existing frame key and a stable representation of each frame.

Run Phase 2.

Reopen the final MP3.

Verify that pre-existing metadata remains.

This test should run automatically before the project is considered production-ready.

---

# 171. JSON-LOSS REGRESSION TEST

Take the real sample JSON.

Run Phase 2.

Remove the `phase2` subtree from the final JSON.

Compare the result to the original JSON semantically.

Expected:

```text
identical
```

If anything else changed, the JSON updater has violated the preservation rule.

---

# 172. ORIGINAL-FILE PROTECTION TEST

Hash the original files before the full run.

Run Phase 2.

Hash the original files afterward.

Expected:

```text
same hashes
```

A changed source hash is a critical failure.

---

# 173. RESUME TEST

Start a song.

Interrupt the process during:

```text
Demucs
chunking
MMS alignment
merge
embedding
```

Restart.

Verify that the pipeline resumes from the appropriate checkpoint rather than restarting the entire song unnecessarily.

---

# 174. IDPOTENCY TEST

Run Phase 2 twice against the same input/config/model.

Expected second run:

```text
skip
```

or safely rebuild only if forced.

No duplicate metadata frame should be created.

No duplicate words should appear.

---

# 175. REPROCESSING TEST

Change one of:

```text
LRC hash
config hash
model revision
pipeline version
```

Then run again.

Expected:

```text
new processing run
```

not a stale skip.

---

# 176. QUALITY REVIEW WORKFLOW

For songs marked `needs_review`, the final JSON should tell the operator why.

Example:

```json
"quality": {
  "status": "needs_review",
  "reasons": [
    "anchor_drift",
    "high_low_score_word_percent"
  ]
}
```

No manual review should be required for normal processing, but the result must contain enough information to inspect problematic songs later.

---

# 177. OPTIONAL ALIGNMENT DEBUG REPORT

For debug mode only, generate a text/JSON report containing:

```text
line
word
source anchor
aligned start
aligned end
score
source type
```

This is not a required final output file.

---

# 178. OPTIONAL AUDIO DEBUG PLOTS

For a future debug tool, one can generate a timeline containing:

```text
original LRC anchors
VAD regions
aligned word spans
instrumental candidates
```

This should remain outside the production final package.

---

# 179. DATA LINEAGE

Every final word should be traceable through:

```text
final JSON word
    -> chunk
    -> normalized reference word
    -> source LRC line
    -> source LRC timestamp
    -> audio segment
    -> MMS emissions
    -> CTC alignment path
```

This is important for future troubleshooting.

---

# 180. PROVENANCE FIELDS

Record:

```text
pipeline_version
schema_version
config_hash
model_name
model_revision
language
normalizer_version
source hashes
run ID
```

This should appear at least in the database and final JSON.

---

# 181. CONFIG HASH

Compute a deterministic SHA-256 of the normalized configuration.

Store:

```text
config_hash
```

This prevents two runs with visibly similar but technically different thresholds from being treated as identical.

---

# 182. PIPELINE VERSION

Use semantic-style versioning:

```text
MAJOR.MINOR.PATCH
```

Examples:

```text
1.0.0
1.1.0
2.0.0
```

A timing algorithm change that can change word boundaries should increment at least the minor version and may warrant a major version depending on scope.

---

# 183. MODEL REVISION

Do not store only:

```text
facebook/mms-1b-all
```

Also store the exact model revision/commit used by the run where possible.

This supports reproducibility.

---

# 184. NORMALIZER REVISION

Do not change normalization rules silently.

Store:

```text
normalizer_version
```

and include it in processing identity.

---

# 185. LRC FORMAT VERSION

The final LRC export should have a format version in JSON:

```text
phase2.outputs.lrc_format = "phase2-wordlevel-lrc-v1"
```

This makes downstream consumers aware of the custom word-level syntax.

---

# 186. CANONICAL TIME UNIT

Internal authoritative time unit:

```text
integer milliseconds
```

Use integer milliseconds in:

- SQLite
- final JSON
- SYLT

Only the LRC renderer converts to display syntax.

---

# 187. FLOATING-POINT POLICY

Do not store canonical timestamps as floating-point seconds when integer milliseconds are sufficient.

Floating-point values may be used internally for signal processing, but final time records should be integer milliseconds.

---

# 188. AUDIO SAMPLE INDEX POLICY

Where precise audio slicing matters, maintain sample indices in addition to milliseconds internally.

Example:

```text
start_sample
end_sample
```

at 16 kHz.

Convert to milliseconds only when creating timing outputs.

This reduces repeated rounding drift.

---

# 189. CHUNK ROUNDING POLICY

Chunk boundaries should be represented internally by sample indices or integer milliseconds consistently.

Do not independently round the same boundary three times in three modules.

The canonical chunk boundaries are created once and passed downstream.

---

# 190. TOKEN FRAME RATE POLICY

Do not assume the emission frame rate based on a generic Wav2Vec2 rule without verifying the exact model configuration.

The implementation should derive the mapping from audio samples to model frames using the actual model's downsampling behavior/configuration.

Store the resulting frame-to-time mapping in the chunk diagnostic data.

---

# 191. CTC MEMORY POLICY

CTC dynamic programming memory is roughly proportional to:

```text
frames × target-state-count
```

Therefore chunking exists not only for Demucs/MMS but also to keep forced alignment computationally manageable.

If a chunk's reference is too large, split it before attempting an alignment that would exceed memory limits.

---

# 192. CTC FAILURE CASES

Possible impossible alignment causes:

```text
reference too long for available frames
empty target token sequence
unsupported target token
corrupt emission shape
model returned invalid values
```

The aligner should return a typed failure rather than raising an opaque exception wherever possible.

---

# 193. NaN / INF DEFENSE

After MMS inference and before CTC alignment, check:

```text
no NaN
no +INF
no -INF
```

If present:

```text
MMS_INFERENCE_FAILED
```

and retry appropriately.

---

# 194. SILENCE / EMPTY REFERENCE CHUNKS

A blank-marker gap must never generate a fake reference alignment.

Do not call the CTC aligner with an empty transcript simply to fill time.

Instead record the region as:

```text
non_lyric candidate
```

and use it for instrumental inference.

---

# 195. LONG INSTRUMENTAL REGIONS

Long gaps are important for processing efficiency.

Do not run MMS on a 60-second purely instrumental region with no reference text.

The chunker should assign chunks around lyric-bearing regions and leave confirmed non-lyric regions out of reference alignment.

This reduces unnecessary GPU work.

---

# 196. LYRIC START / END DETECTION

The song may contain long intro/outro sections.

Do not require the first lyric timestamp to be near zero.

Do not require the last lyric timestamp to be near song duration.

The sample demonstrates this pattern, with the final lyric timing well before the end of the ~318-second audio.

---

# 197. DURATION VALIDATION RULE

The correct rule is:

```text
all aligned timestamps must be within source duration
```

not:

```text
last lyric must be within ±10% of song duration
```

Intros and outros are valid.

---

# 198. WORD COUNT VALIDATION RULE

The expected word sequence comes from the source LRC.

Do not use a broad rule such as:

```text
final word count ±20%
```

as the main validity criterion.

Instead explicitly record:

```text
expected
aligned
interpolated
missing
unsupported
```

This is far more informative.

---

# 199. LINE COUNT VALIDATION

The final alignment must preserve the number and order of source lyric lines except for explicitly classified blank markers.

The sample input has 39 lyric lines and 3 blank timing markers.

The final JSON should retain that structure.

---

# 200. DUPLICATED LYRIC LINES

Repeated chorus lines are valid.

Do not deduplicate them by text.

Each occurrence must retain its own line index and timing.

Example:

```text
గెలుపు తలుపులే...
```

may occur multiple times and each occurrence is a separate alignment event.

---

# 201. CHORUS / VERSE REPETITIONS

The alignment model must use temporal context, not text uniqueness.

The same lyric phrase appearing at:

```text
00:25
01:25
03:00
05:00
```

must remain four separate occurrences.

---

# 202. WORD BOUNDARY POLICY

Word boundaries come from the source lyric text, not from whatever word segmentation MMS happens to predict.

This is an important distinction.

The supplied lyric wording defines the final words.

CTC only determines where the reference tokens associated with those words occur acoustically.

---

# 203. PUNCTUATION POLICY

Punctuation may be omitted from the acoustic token reference if the tokenizer does not support it, but it must not be silently lost from the display text.

Therefore:

```text
original = display form
normalized = alignment form
```

---

# 204. ENGLISH / LATIN WORD POLICY

If the lyric contains English or Latin words inside a Telugu song:

1. Preserve the original word.
2. Determine whether the Telugu MMS tokenizer can represent it.
3. If yes, align normally.
4. If not, classify as unsupported.
5. Attempt a controlled fallback only if explicitly configured.
6. Never silently delete it from the final display.

---

# 205. NUMBER POLICY

Numbers may be handled by one of three modes:

```text
preserve
convert_to_telugu
unsupported
```

Default should be conservative and deterministic.

If conversion is enabled, record the transformation in the normalization mapping.

---

# 206. ABBREVIATION POLICY

Maintain a small versioned dictionary.

Example concept:

```text
"Sr." -> "శ్రీ"
```

The dictionary must not be hard-coded without versioning.

Record:

```text
normalization operation
```

when applied.

---

# 207. ORIGINAL TEXT IS USER-FACING

Every output visible to the user should default to the source LRC's original wording.

Normalization is an internal alignment convenience.

Do not silently replace lyrics with model-spelled variants.

---

# 208. NO ASR SUBSTITUTION

MMS may internally produce a likely transcription that differs from the source lyric.

The system must not overwrite the source lyric with MMS's guessed spelling.

That would defeat the purpose of reference alignment.

---

# 209. OPTIONAL ASR DIAGNOSTIC

For research/debugging, the system may calculate an MMS argmax transcription for diagnostics.

If enabled:

```text
store as diagnostic only
```

Do not use it as the production lyric output unless a future explicitly approved alternate mode is implemented.

---

# 210. CHUNK ALIGNMENT SEARCH WINDOW

For an LRC-anchored chunk, define an expected time window.

The chunk's reference lines should fall generally inside:

```text
logical_start_ms
logical_end_ms
```

The model audio includes overlap.

If alignment lands entirely outside the logical region, treat it as suspicious and retry or subdivide.

---

# 211. SOFT ANCHOR CHECK

Rather than modifying the CTC score too aggressively in the first implementation, use the LRC anchor primarily as a search constraint and post-alignment validator.

Later versions may add soft temporal penalties.

This keeps the first production implementation understandable and testable.

---

# 212. GLOBAL ALIGNMENT VS CHUNK ALIGNMENT

The project uses chunk-level alignment for computational practicality.

However, correctness must be song-aware.

The merger should validate the complete sequence globally after local alignments are produced.

Do not assume independently successful chunks imply a globally correct song.

---

# 213. CHUNK QUALITY AGGREGATION

Song-level score can be weighted by word duration or word count.

Recommended primary weighting:

```text
word-count weighted
```

with additional reporting by audio duration.

Do not let a tiny two-word chunk dominate the overall mean.

---

# 214. P10 SCORE

The 10th percentile of word scores is particularly useful.

If the mean is high but P10 is very low, the song contains a long tail of questionable words.

This should be reflected in `quality_status`.

---

# 215. INTERPOLATION LIMIT

A configurable default can be:

```text
interpolated_word_percent <= 20%
```

but this should be a quality rule rather than an absolute processing failure.

Also report interpolation by line and by gap.

---

# 216. LARGE FAILED GAP POLICY

If a single failed region spans a large portion of the song, classify accordingly even if the total failed-chunk count is small.

Record:

```text
failed_audio_ms
```

and:

```text
failed_word_count
```

---

# 217. QUALITY REASONS

Recommended machine-readable reasons:

```text
LOW_MEAN_SCORE
LOW_P10_SCORE
MANY_LOW_SCORE_WORDS
HIGH_INTERPOLATION
MISSING_WORDS
ANCHOR_DRIFT
TIMESTAMP_ERROR
CHUNK_FAILURE
VOCAL_STEM_QUALITY
```

---

# 218. OUTPUT STATUS IN JSON

The final JSON should contain:

```text
phase2.status
phase2.quality_status
phase2.quality.reasons[]
```

so a downstream consumer can understand both completion and quality.

---

# 219. MP3 METADATA OWNERSHIP

Phase 2 owns only:

```text
Phase2-WordLevel SYLT
```

and optionally a small number of Phase 2-specific TXXX fields if useful.

If Phase 2 adds such fields, their ownership must be namespaced/documented.

Do not overwrite Phase 1 custom TXXX fields.

---

# 220. OPTIONAL PHASE 2 TXXX FIELDS

If desired, add:

```text
TXXX:phase2_version
TXXX:phase2_status
TXXX:phase2_model
TXXX:phase2_alignment_method
```

but keep these additions minimal.

The detailed history belongs in JSON.

---

# 221. ARTWORK PRESERVATION

If the original MP3 has an APIC artwork frame, it must remain unchanged unless the user explicitly asks otherwise.

The sample already contains a front-cover APIC with the artwork referenced in the JSON.

Phase 2 must never re-download or replace artwork as part of word synchronization.

---

# 222. URL / IDENTIFIER PRESERVATION

Existing:

```text
UFID
WXXX
TXXX
```

data must remain intact.

The sample already contains YouTube Music/YouTube/Open Spotify-related identifiers and URLs.

These are historical metadata, not alignment inputs, and must not be discarded.

---

# 223. FINAL JSON ARTWORK / SOURCE DATA

Phase 2 should not duplicate existing artwork/source structures into the `phase2` namespace unless necessary.

It should reference them conceptually through existing JSON sections and add only Phase 2-specific data.

---

# 224. MODEL DOWNLOAD POLICY

The model can be downloaded/cached as part of environment setup or first-run initialization.

The song input pipeline itself must not use external lyric searching or audio downloading.

If model files are unavailable and network access is disabled, the run should fail clearly rather than silently substituting another model.

---

# 225. NETWORK POLICY

No network access should be required for processing a song once:

```text
MMS model is cached
Demucs model is cached
Silero model is cached
```

This is desirable for reproducible batch runs.

---

# 226. MODEL VERSION LOCK

Before the 1,892-song batch, freeze:

```text
Python version
PyTorch version
Transformers version
Demucs version
Silero VAD version
Mutagen version
NumPy version
audio I/O dependencies
model revision
```

Do not upgrade packages halfway through a batch.

---

# 227. BATCH RUN MANIFEST

At batch start, create a run record containing:

```text
run_id
start_time
pipeline_version
config_hash
model revision
language
environment versions
```

At batch end:

```text
finish_time
counts by status
```

This run data should be linked to individual songs.

---

# 228. BATCH SUMMARY

At completion, report:

```text
Total songs discovered
Songs processable
Finished-good
Finished-partial
Needs-review
Failed
Skipped
Total words aligned
Total words interpolated
Average score
Median score where tracked
Total processing time
```

---

# 229. SAFE INTERRUPTION

A Ctrl+C or process termination should:

1. stop launching new work
2. finish current safe DB transaction if possible
3. leave current chunk/song state resumable
4. preserve temp data for incomplete work
5. never modify source files

---

# 230. SQLITE TRANSACTION POLICY

Use transactions for state changes.

For example:

```text
chunk result written
+
chunk status updated
```

should be committed together.

This prevents a chunk from being marked successful when its output row was never saved.

---

# 231. DATABASE FOREIGN KEYS

Enable SQLite foreign keys explicitly.

Use:

```sql
PRAGMA foreign_keys = ON;
```

This protects chunk/word relationships.

---

# 232. DATABASE INDEXES

Recommended indexes:

```text
songs(pipeline_status)
songs(quality_status)
songs(original_mp3_sha256)
chunks(song_id, status)
words(song_id, line_index, word_index)
```

These improve batch resume and inspection.

---

# 233. DATABASE BACKUP

Because the database tracks long-running work, provide a simple backup mechanism.

Recommended:

```text
copy phase2.db before major schema migrations
```

and document migration versions.

---

# 234. DATABASE SCHEMA VERSION

Maintain:

```text
PRAGMA user_version
```

or an explicit schema metadata table.

Never silently change schema during a batch.

---

# 235. MIGRATION STRATEGY

Schema changes should use versioned migrations:

```text
001_initial.sql
002_add_provenance.sql
003_add_quality_metrics.sql
```

This is especially important if the project is developed iteratively during a long corpus run.

---

# 236. OUTPUT DIRECTORY POLICY

If `songs/final/` does not exist:

```text
create it
```

If files already exist:

```text
do not blindly overwrite
```

Use validation plus input/config identity to decide whether to skip or force reprocess.

---

# 237. FINAL REPLACEMENT SAFETY

If an old final package exists and a new package is being generated:

```text
old final files remain untouched during processing
```

Only after the new staged package validates should replacement occur.

This prevents a failed rerun from destroying a previously good result.

---

# 238. PACKAGE CONSISTENCY TOKEN

The final JSON should contain:

```text
phase2.run_id
```

and optionally:

```text
phase2.package_id
```

This identifies which processing result produced all three final files.

---

# 239. PACKAGE ID

A package ID can be derived from:

```text
source hashes
+
run ID
```

or simply use a UUID generated at processing start.

Store it in JSON and DB.

The MP3 need not contain this unless desired.

---

# 240. FINAL JSON COMPLETENESS RULE

The final JSON should never report:

```text
status = finished
```

until:

```text
final MP3 exists
final LRC exists
final JSON exists
final MP3 validates
final LRC validates
final JSON validates
```

---

# 241. FINALIZATION ORDER DETAIL

A robust finalization process:

```text
A. Build canonical alignment
B. Validate canonical alignment
C. Generate staged LRC
D. Generate staged MP3
E. Generate staged JSON
F. Validate each staged output
G. Validate cross-output consistency
H. Validate source hashes unchanged
I. Compute staged output hashes
J. Promote staged files
K. Commit DB final status
L. Cleanup temp
```

---

# 242. IF PROMOTION FAILS

If a file move fails:

```text
final package is not considered complete
```

Do not update the DB to `finished`.

Keep staged files and logs for recovery.

---

# 243. IF JSON PROMOTION SUCCEEDS BUT DB UPDATE FAILS

On restart:

```text
validate final package
compare run/package metadata
reconcile DB
```

The database should be repairable from the final outputs.

---

# 244. RECONCILIATION COMMAND

Recommended:

```text
--repair-state
```

It should inspect:

```text
songs/final/
phase2.db
```

and repair obvious state mismatches without touching source files.

---

# 245. FINAL DIRECTORY SHOULD BE USER-FRIENDLY

The user should only need to look at:

```text
songs/final/
```

for finished results.

Everything else is implementation detail.

---

# 246. EXPLICITLY NO EXTRA PER-SONG FINAL FILES

Do not place these in `songs/final/` by default:

```text
alignment.json
vocals.wav
debug.json
chunk files
log files
model outputs
```

Those belong in temp/debug storage.

The user's requested final package stays exactly three files.

---

# 247. OPTIONAL FUTURE EXPORTS

Future versions may offer:

```text
CSV word timing
WebVTT
JSON-only export
SRT
```

but these are out of scope for the first implementation and must not complicate the final directory now.

---

# 248. CORE IMPLEMENTATION ORDER

Recommended build order:

```text
1. config
2. database
3. scanner
4. JSON preservation layer
5. LRC parser
6. audio decoder
7. Demucs wrapper
8. VAD/activity
9. Telugu normalizer
10. tokenizer mapping
11. independent CTC aligner
12. MMS wrapper
13. word builder
14. merger
15. validator
16. LRC exporter
17. SYLT embedder
18. JSON updater
19. recovery
20. pipeline orchestrator
21. end-to-end sample test
22. batch mode
```

---

# 249. WHY CTC ALIGNER ISOLATION IS CRITICAL

The biggest algorithmic risk is the alignment engine.

By putting it behind:

```text
src/ctc_aligner.py
```

we can replace or improve the actual dynamic-programming implementation later without rewriting:

- LRC parsing
- metadata handling
- Demucs
- database
- exports
- resume logic

---

# 250. CTC ALIGNER ACCEPTANCE CRITERIA

Before full-batch processing, the CTC aligner must demonstrate:

```text
reference text is actually used
repeated tokens align correctly
blank transitions work
word boundaries are preserved
spans are chronological
scores are finite
impossible references fail cleanly
```

This is the primary algorithm gate.

---

# 251. MODEL ADAPTER ACCEPTANCE CRITERIA

Before full-batch processing, verify:

```text
MMS base model loads
Telugu adapter loads
processor vocabulary matches model head
inference returns expected logits shape
```

The exact initialization code must match the pinned Transformers version.

---

# 252. DEMUCS ACCEPTANCE CRITERIA

Before full batch:

```text
GPU path works
CPU fallback works
vocals duration aligns
output is readable
working audio is lossless
```

---

# 253. LRC INPUT ACCEPTANCE CRITERIA

Before full batch:

```text
all source LRC lines parse
blank markers survive
Telugu UTF-8 survives
line order survives
```

---

# 254. JSON ACCEPTANCE CRITERIA

Before full batch:

```text
full input JSON loads
all source keys preserved
phase2 can be added
Unicode survives
unknown nested structures survive
```

---

# 255. MP3 ACCEPTANCE CRITERIA

Before full batch:

```text
existing ID3 reads
artwork preserved
custom frames preserved
existing lyric frames preserved
new Phase2 SYLT writes
file still decodes
```

---

# 256. FULL SAMPLE GATE

The real sample song should be processed successfully from:

```text
songs/original/
```

to:

```text
songs/final/
```

with the source hashes unchanged and no metadata loss.

The sample is the first production-style golden test.

---

# 257. BATCH ROLLOUT PLAN

Do not immediately process the entire corpus.

Use stages:

```text
Stage 1: 1 sample
Stage 2: 5 songs
Stage 3: 25 songs
Stage 4: 100 songs
Stage 5: 500 songs
Stage 6: full corpus
```

At each stage inspect:

```text
failure rate
quality distribution
GPU memory
runtime
metadata preservation
JSON growth
```

---

# 258. GO/NO-GO GATES

Do not increase batch size if any of these are unresolved:

```text
metadata loss
source file mutation
incorrect JSON merge
CTC alignment corruption
systematic anchor drift
frequent GPU OOM
unrecoverable resume bugs
```

---

# 259. QUALITY SAMPLING

Even if automatic validation passes, sample a subset of finished songs for manual listening/inspection.

Recommended sampling:

```text
random songs
lowest-score songs
highest-interpolation songs
largest-anchor-drift songs
longest songs
songs with large instrumental gaps
```

This is a validation strategy, not a requirement for routine user interaction.

---

# 260. REVIEW QUEUE

The DB should make it possible to query:

```sql
SELECT *
FROM songs
WHERE quality_status = 'needs_review';
```

and:

```sql
SELECT *
FROM songs
WHERE quality_status = 'partial';
```

This supports targeted inspection.

---

# 261. REVIEW REASON SUMMARY

For every review song, produce a compact reason string such as:

```text
anchor_drift; low_p10_score
```

rather than only:

```text
needs_review
```

---

# 262. ERROR MESSAGE QUALITY

Error messages should answer:

```text
what failed?
where?
why?
which attempt?
can it retry?
```

Example:

```text
CTC_ALIGNMENT_FAILED: song=187 chunk=12 attempt=2; reference token sequence could not be fit within emission frames; retry budget exhausted
```

---

# 263. NO SILENT FALLBACKS

Do not silently:

- switch languages
- switch models
- use a different lyric source
- drop unsupported words
- discard existing metadata
- replace original text

Every fallback must be recorded.

---

# 264. FALLBACK HIERARCHY

For alignment:

```text
1. normal vocals + CTC reference alignment
2. adjusted chunk/context + CTC
3. original mix + CTC
4. interpolation where neighboring aligned words support it
5. missing/needs_review
```

Do not jump directly from a failed chunk to an unrelated transcription method.

---

# 265. NO WHISPER

Whisper is explicitly outside the Phase 2 architecture.

The system does not need a transcription model to discover the lyrics because the lyric reference already exists in the sidecar LRC.

This is precisely why reference-driven forced alignment is appropriate.

---

# 266. WHY REFERENCE ALIGNMENT IS PREFERRED

The source LRC already tells us:

```text
what the words are
line order
approximate timing
```

The acoustic model only needs to answer:

```text
where those known words occur in the audio
```

That is a better fit than asking a speech recognizer to guess the lyric text from scratch.

---

# 267. MODEL OUTPUT AS EVIDENCE

The MMS model should be thought of as an acoustic scorer.

The lyric text remains the reference.

The CTC aligner connects the two.

This separation makes the architecture easier to reason about and validate.

---

# 268. FINAL CANONICAL DATA FLOW

```text
LRC text
  |
  v
normalized reference
  |
  v
tokens
  |
  +--------------------+
                       |
Audio -> MMS -> emissions
                       |
                       v
                CTC forced alignment
                       |
                       v
                  token spans
                       |
                       v
                  word spans
                       |
                       v
              canonical alignment
```

---

# 269. OUTPUT CANONICAL DATA FLOW

```text
canonical alignment
       |
       +--> SQLite words
       |
       +--> final JSON phase2.alignment
       |
       +--> final word-level LRC
       |
       `--> final MP3 Phase2 SYLT
```

---

# 270. COMPLETE SONG LIFECYCLE

```text
DISCOVER
  |
  v
MATCH MP3/LRC/JSON
  |
  v
HASH SOURCE FILES
  |
  v
LOAD JSON
  |
  v
PARSE LRC
  |
  v
VALIDATE AUDIO
  |
  v
DEMUCS
  |
  v
ACTIVITY MAP
  |
  v
NORMALIZE REFERENCE
  |
  v
ANCHOR MAP
  |
  v
CHUNK
  |
  v
MMS EMISSIONS
  |
  v
CTC FORCED ALIGNMENT
  |
  v
TOKEN -> WORD
  |
  v
QUALITY
  |
  v
MERGE
  |
  v
VALIDATE
  |
  v
LRC EXPORT
  |
  v
MP3 SYLT EMBED
  |
  v
JSON UPDATE
  |
  v
FINAL VALIDATION
  |
  v
ATOMIC/STAGED PROMOTION
  |
  v
DATABASE COMPLETE
  |
  v
CLEANUP
```

---

# 271. FINAL CONTRACT — INPUT

For each song:

```text
songs/original/SongName.mp3
songs/original/SongName.lrc
songs/original/SongName.json
```

The basename must match exactly.

---

# 272. FINAL CONTRACT — PROCESSING

Phase 2:

```text
reads source files
isolates vocals
analyzes activity
normalizes reference text
uses LRC anchors
chunks reference/audio
runs MMS
performs true CTC reference alignment
creates word timestamps
validates result
embeds SYLT
updates cumulative JSON
```

---

# 273. FINAL CONTRACT — OUTPUT

```text
songs/final/SongName.mp3
songs/final/SongName.lrc
songs/final/SongName.json
```

The final JSON contains all previous JSON data plus Phase 2 details.

The final MP3 contains all previous metadata plus the Phase 2 word-level SYLT.

The final LRC contains the original lyric wording with Phase 2 word-level timing.

---

# 274. FINAL CONTRACT — SOURCE PRESERVATION

After completion:

```text
original MP3 unchanged
original LRC unchanged
original JSON unchanged
```

This must be automatically verified.

---

# 275. FINAL CONTRACT — METADATA PRESERVATION

The final MP3 must retain:

```text
existing title
existing artist
existing album
existing track/disc data
existing artwork
existing IDs
existing URLs
existing custom TXXX frames
existing USLT
existing SYLT
```

plus the new Phase 2 word-level SYLT.

---

# 276. FINAL CONTRACT — JSON PRESERVATION

The final JSON must retain:

```text
all original keys
all original nested data
all previous source metadata
all previous processing history
```

and add:

```text
phase2
```

---

# 277. FINAL CONTRACT — TIMING

Canonical timing unit:

```text
milliseconds
```

Canonical word data:

```text
start_ms
end_ms
```

LRC is rounded only at export time.

SYLT uses the canonical millisecond timestamps.

---

# 278. FINAL CONTRACT — ALIGNMENT METHOD

Canonical alignment method:

```text
MMS frame-level acoustic emissions
+
source LRC reference tokens
+
CTC forced alignment
```

Not:

```text
MMS ASR transcription offsets
```

---

# 279. FINAL CONTRACT — RESUME

A stopped run must continue from the last completed safe stage.

Successful chunks must not be recomputed unnecessarily.

Source files must remain untouched.

---

# 280. FINAL CONTRACT — REPRODUCIBILITY

Every output should be traceable to:

```text
source MP3 hash
source LRC hash
source JSON hash
pipeline version
config hash
model name
model revision
normalizer version
run ID
```

---

# 281. PRODUCTION READINESS CHECKLIST

Before processing the entire collection, all must be true:

```text
[ ] File matching works
[ ] Source hashing works
[ ] Original files remain unchanged in tests
[ ] Full JSON preservation test passes
[ ] MP3 metadata preservation test passes
[ ] LRC parser passes fixtures
[ ] Telugu normalization mapping passes
[ ] MMS Telugu adapter loads
[ ] CTC aligner passes synthetic tests
[ ] Token -> word mapping passes
[ ] Chunking passes sample tests
[ ] Overlap dedup passes
[ ] Anchor drift validation passes
[ ] LRC exporter passes
[ ] SYLT embedder passes
[ ] Final JSON updater passes
[ ] Final package validation passes
[ ] Resume test passes
[ ] Idempotency test passes
[ ] Failure recovery tests pass
[ ] Sample song completes
[ ] 5-song pilot completes
[ ] 25-song pilot reviewed
[ ] Environment is locked
[ ] Model revision is recorded
```

---

# 282. FIRST IMPLEMENTATION MILESTONE

Milestone 1 should **not** be the full pipeline.

Build and prove:

```text
scanner
+
LRC parser
+
JSON preservation
+
MP3 metadata snapshot
+
CTC aligner synthetic tests
```

This creates a safe foundation before expensive GPU work is introduced.

---

# 283. SECOND IMPLEMENTATION MILESTONE

Build:

```text
Demucs
VAD/activity
Telugu normalization
MMS emissions
CTC forced alignment
```

Test only on one song.

---

# 284. THIRD IMPLEMENTATION MILESTONE

Build:

```text
merge
validation
LRC export
SYLT embedding
JSON update
```

Run end-to-end on the sample song.

---

# 285. FOURTH IMPLEMENTATION MILESTONE

Add:

```text
resume
retry
stale recovery
idempotency
batch mode
```

Then run the 5-song pilot.

---

# 286. FIFTH IMPLEMENTATION MILESTONE

Scale carefully:

```text
25
-> 100
-> 500
-> full corpus
```

Only advance when quality and metadata-preservation metrics remain stable.

---

# 287. TROUBLESHOOTING PRIORITY

When a result is bad, inspect in this order:

```text
1. source LRC correctness
2. audio duration alignment
3. Demucs stem quality
4. chunk boundaries
5. MMS language adapter
6. CTC reference tokenization
7. CTC alignment path
8. word grouping
9. overlap merge
10. validation/renderer
```

Do not immediately blame MMS if the reference-to-token mapping is wrong.

---

# 288. MOST IMPORTANT ENGINEERING RISKS

The main risks are:

```text
1. incorrect CTC forced alignment implementation
2. wrong MMS language adapter configuration
3. destructive JSON update
4. destructive MP3 tag update
5. chunk boundary errors
6. over-trusting VAD
7. normalization destroying reference wording
8. incorrect token-to-word mapping
9. overlap duplication
10. resume state inconsistencies
```

These receive the strongest tests.

---

# 289. MOST IMPORTANT DATA RISKS

The project must guard against:

```text
wrong MP3/LRC/JSON pairing
wrong basename
changed source file
lost metadata
lost JSON history
wrong repeated chorus assignment
missing words
silent unsupported words
false instrumental classification
```

---

# 290. MOST IMPORTANT ALIGNMENT RISKS

Alignment can fail because:

```text
lyrics differ slightly from sung version
MMS model mishears Telugu
vocal stem contains artifacts
LRC anchor is inaccurate
words are very fast
words overlap musically
background vocals interfere
chunk cuts a phrase
unsupported symbols disrupt tokenization
```

The architecture addresses these through reference alignment, overlap, normalization mapping, retries, and validation.

---

# 291. DO NOT FORCE FALSE PRECISION

A word-level timestamp is only useful if it is reasonably trustworthy.

When the system cannot establish a good direct alignment, it must say:

```text
interpolated
missing
needs_review
```

rather than creating a visually precise but unsupported number and calling it exact.

---

# 292. QUALITY SHOULD BE TRANSPARENT

Every word can be thought of as having:

```text
text
start
end
confidence
provenance
```

This makes the result inspectable rather than magical.

---

# 293. FINAL JSON AS CUMULATIVE SONG RECORD

The final JSON becomes the long-term record for the song.

It contains:

```text
previous source metadata
previous processing information
Phase 2 alignment
Phase 2 quality
Phase 2 provenance
final output paths
```

A later phase or tool can therefore read one final JSON file and understand the song's processing history without needing Phase 1's database.

---

# 294. NO HIDDEN DEPENDENCY ON PHASE 1

Even if Phase 1 originally created:

```text
video_id
playlist position
Spotify IDs
YouTube metadata
artwork data
LRCLIB information
```

Phase 2 must treat these only as data already present in the JSON/MP3.

Phase 2 must still work if the same JSON structure were produced by another project.

---

# 295. FILE-LEVEL CONTRACT OVER PROJECT-LEVEL CONTRACT

The correct dependency is:

```text
Phase 1 (or previous work)
        |
        v
MP3 + LRC + JSON
        |
        v
Phase 2
```

not:

```text
Phase 2
   -> import Phase 1 modules
   -> query Phase 1 DB
```

This keeps Phase 2 portable.

---

# 296. PORTABILITY GOAL

Phase 2 should be movable to another machine by copying:

```text
phase2_project/
songs/original/
models/
```

plus the locked environment.

It should not require the original Phase 1 repository.

---

# 297. REBUILDABILITY GOAL

If `db/phase2.db` is lost, the project should still be able to rescan:

```text
songs/original/
```

and recover the input inventory.

The final JSON also contains enough provenance to understand completed outputs.

---

# 298. FINAL JSON AS RECOVERY SOURCE

If a song has:

```text
final MP3
final LRC
final JSON
```

but its DB row is missing, a future reconciliation command should be able to inspect the final JSON's `phase2` section and reconstruct a completed state.

---

# 299. CUMULATIVE JSON VERSIONING

The existing JSON already contains its own historical project/schema information.

Phase 2 should not rewrite those version fields merely because Phase 2 exists.

Instead add:

```text
phase2.pipeline_version
phase2.schema_version
```

so historical versioning remains understandable.

---

# 300. PROJECT-SCOPE SUMMARY

This project is intentionally narrow:

```text
INPUT
MP3 + LRC + JSON

TRANSFORM
line-level reference -> word-level timing

OUTPUT
MP3 + LRC + JSON

PRESERVE
all original source information

MODEL
MMS Telugu

ALIGNMENT
CTC forced alignment

AUDIO
Demucs vocal isolation

ACTIVITY
Silero VAD + energy

STATE
SQLite

RECOVERY
checkpointed/resumable
```

---

# 301. FINAL REFERENCE PIPELINE

The final architecture, without omissions, is:

```text
                    songs/original/
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
       Song.mp3         Song.lrc         Song.json
          |                |                |
          |                +-------> parse |
          |                                 |
          +-----------> inventory <---------+
                           |
                           v
                    source fingerprints
                           |
                           v
                    JSON preservation
                           |
                           v
                       LRC model
                           |
                           +--------------------+
                           |                    |
                           v                    v
                     line anchors          blank markers
                           |                    |
                           +---------+----------+
                                     |
                                     v
                             audio preparation
                                     |
                                     v
                               Demucs vocals
                                     |
                                     v
                              VAD + energy map
                                     |
                                     v
                         reversible normalization
                                     |
                                     v
                            reference chunking
                                     |
                                     v
                              MMS Telugu adapter
                                     |
                                     v
                           frame-level emissions
                                     |
                                     v
                         CTC forced alignment
                                     |
                                     v
                             token time spans
                                     |
                                     v
                              word time spans
                                     |
                                     v
                       chunk quality / confidence
                                     |
                                     v
                        overlap deduplication
                                     |
                                     v
                             global merge
                                     |
                                     v
                          canonical alignment
                                     |
                 +-------------------+------------------+
                 |                   |                  |
                 v                   v                  v
           SQLite words       final JSON          final LRC
                                     |
                                     v
                              final MP3 copy
                                     |
                                     v
                             Phase 2 SYLT add
                                     |
                                     v
                        final output validation
                                     |
                                     v
                           staged promotion
                                     |
                                     v
                         songs/final/Song.*
```

---

# 302. ABSOLUTE DO-NOT-DO LIST

The implementation must never:

```text
1. Modify songs/original/*.mp3
2. Modify songs/original/*.lrc
3. Modify songs/original/*.json
4. Delete all ID3 tags
5. Delete existing artwork
6. Delete existing custom metadata
7. Delete existing SYLT without ownership checks
8. Replace source lyrics with MMS transcription
9. Treat VAD silence as guaranteed instrumental truth
10. Use argmax ASR offsets as forced alignment
11. Delete unsupported words silently
12. Reconstruct the old JSON from selected fields
13. Require Phase 1's database
14. Require Phase 1's code
15. Depend on video_id for temporary directory identity
16. Hard-code a false last-lyric-near-duration rule
17. Declare quality based only on average confidence
18. Mark interpolated words as directly aligned
19. Generate final LRC from a separate timing calculation
20. Generate final SYLT by reparsing rounded LRC
21. Mark output finished before validating it
22. Overwrite good final files before the replacement package is validated
```

---

# 303. ABSOLUTE MUST-DO LIST

The implementation must:

```text
1. Match MP3/LRC/JSON by basename
2. Hash all input files
3. Preserve full original JSON
4. Preserve all existing MP3 metadata
5. Use external LRC as the lyric reference
6. Treat LRC timestamps as coarse anchors
7. Use Demucs for vocal isolation
8. Use VAD/activity as supporting evidence
9. Normalize Telugu reversibly
10. Use MMS Telugu adapter explicitly
11. Generate frame-level MMS emissions
12. Perform true CTC reference alignment
13. Convert token spans to word spans
14. Keep integer millisecond timestamps
15. Deduplicate overlapping chunks
16. Validate word and line ordering
17. Validate anchor drift
18. Track interpolation separately
19. Generate one final word-level LRC
20. Add a dedicated Phase 2 SYLT frame
21. Validate final MP3
22. Update final JSON with all Phase 2 details
23. Validate cross-file consistency
24. Support resume
25. Support idempotent reruns
26. Verify source files remained unchanged
27. Keep temp files for failures/reviews
28. Clean temp files after success
29. Record exact provenance
30. Process the full corpus only after staged acceptance tests
```

---

# 304. TECHNICAL BASIS USED FOR THIS PLAN

The architecture deliberately reflects current documented behavior of the major technologies used by the project.

## MMS

The current Hugging Face MMS documentation/model card describes language-specific adapter loading and the use of `target_lang` / `load_adapter` together with the MMS tokenizer/model. The model card also documents `facebook/mms-1b-all` and its supported multilingual architecture.

## CTC forced alignment

The current PyTorch documentation demonstrates forced alignment as aligning a supplied transcript against frame-level CTC emissions. Older TorchAudio forced-alignment APIs were deprecated and removed as TorchAudio moved into maintenance mode, so Phase 2 should isolate its own CTC alignment algorithm rather than depend on the deprecated API.

## Silero VAD

Silero VAD exposes speech timestamps based on configurable speech thresholds and related duration/padding parameters. Phase 2 uses those timestamps as activity/boundary evidence, not as definitive semantic instrumental detection.

## Demucs

Demucs documentation supports vocals-only separation mode and provides guidance for GPU memory pressure and segment sizing. Phase 2 uses a lossless working vocal stem for alignment rather than repeatedly encoding intermediate MP3 files.

## Mutagen / ID3 SYLT

The ID3 SYLT specification defines synchronized text entries with absolute timestamps and supports milliseconds as a timestamp unit. Mutagen exposes the SYLT frame and its fields. Phase 2 therefore embeds canonical millisecond word timing directly into SYLT instead of rebuilding it from rounded LRC.

---

# 305. ENGINEERING PRINCIPLE — SEPARATE DATA LAYERS

The project should maintain a clean separation:

```text
SOURCE DATA
    |
    +--> MP3
    +--> LRC
    `--> JSON

PROCESSING DATA
    |
    +--> decoded audio
    +--> vocals
    +--> chunks
    +--> emissions
    +--> alignment

CANONICAL RESULT
    |
    +--> SQLite words
    `--> JSON phase2.alignment

EXPORTS
    |
    +--> final LRC
    `--> final MP3 SYLT
```

This separation prevents export formats from becoming hidden processing dependencies.

---

# 306. ENGINEERING PRINCIPLE — PRESERVE, THEN ADD

For both JSON and MP3:

```text
preserve existing
        |
        v
add Phase 2 data
```

Never:

```text
extract a few fields
        |
        v
rebuild everything
```

---

# 307. ENGINEERING PRINCIPLE — REFERENCE FIRST

The source lyric reference is authoritative for wording.

MMS is authoritative only as acoustic evidence.

CTC alignment is the bridge.

This prevents transcription drift.

---

# 308. ENGINEERING PRINCIPLE — HONEST UNCERTAINTY

When direct timing is uncertain, preserve that uncertainty:

```text
score
source
quality status
interpolation flag
review reason
```

This is preferable to false precision.

---

# 309. ENGINEERING PRINCIPLE — DETERMINISM

Given identical:

```text
source files
models
versions
configuration
```

the pipeline should produce the same logical result as closely as the pinned runtime permits.

Avoid uncontrolled randomness.

If any model stage exposes randomness that is not needed, disable it.

---

# 310. ENGINEERING PRINCIPLE — VERSION EVERYTHING IMPORTANT

Version:

```text
pipeline
schema
normalizer
config
model
model revision
LRC export format
```

---

# 311. ENGINEERING PRINCIPLE — CHECKPOINT EXPENSIVE WORK

Demucs and MMS are expensive.

SQLite should ensure their work is not repeated after a crash unless necessary.

---

# 312. ENGINEERING PRINCIPLE — FINAL OUTPUTS ARE DERIVED

`Songs/final/` is a published-output area.

It is not a scratch area.

Nothing should be placed there until it is validated.

---

# 313. ENGINEERING PRINCIPLE — ONE CANONICAL TIMELINE

There must be exactly one canonical Phase 2 timing result per successful run.

LRC and SYLT are projections of that timeline.

JSON contains that timeline.

SQLite indexes that timeline.

---

# 314. FINAL SAMPLE PACKAGE TARGET

For the supplied sample, the final directory should eventually be:

```text
songs/final/
├── 001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.mp3
├── 001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.lrc
└── 001_Gelupu Thalupule_Mani Sharma, Sreerama Chandra.json
```

The original directory remains exactly as supplied.

---

# 315. FINAL SAMPLE JSON TARGET

The sample final JSON must still contain its previous top-level data and gain:

```text
phase2
```

with at minimum:

```text
input hashes
model information
processing status
alignment method
line/word alignment
quality metrics
instrumental/gap candidates
output paths
final output hashes
provenance
```

---

# 316. FINAL SAMPLE MP3 TARGET

The sample final MP3 must retain its original metadata and contain a new Phase 2 word-level SYLT.

The existing lyric frames must remain intact unless an explicit ownership rule says otherwise.

---

# 317. FINAL SAMPLE LRC TARGET

The sample final LRC must retain the same lyric wording and lyric order as the source LRC, but the timing representation is upgraded to word-level timing.

The long blank regions remain represented according to the configured blank-marker policy.

---

# 318. FINAL PROJECT SUCCESS DEFINITION

Phase 2 is successful when the following is true:

```text
For every processable source package:

Song.mp3 + Song.lrc + Song.json
              |
              v
        Phase 2 processing
              |
              v
Song.mp3 + Song.lrc + Song.json
```

with:

```text
source files unchanged
existing JSON preserved
existing MP3 metadata preserved
word-level timing generated
MMS reference alignment performed
outputs validated
database state recorded
resume supported
provenance recorded
```

---

# 319. FINAL IMPLEMENTATION MESSAGE

When this plan is implemented, the project should be thought of as a **word-level timing engine**, not a lyric downloader and not a transcription system.

Its job is:

```text
TAKE KNOWN LYRICS
        +
TAKE KNOWN AUDIO
        |
        v
FIND WHERE EACH KNOWN WORD OCCURS
IN THE AUDIO
```

The source LRC supplies the known words and coarse line timing.

Demucs supplies a cleaner vocal signal.

VAD and energy provide activity/boundary evidence.

MMS supplies frame-level acoustic evidence.

CTC forced alignment connects the supplied lyric reference to that evidence.

The canonical result becomes word start/end timing.

That timing is exported to one final LRC, embedded into a new Phase 2 SYLT frame in a copy of the original MP3, and written into the existing JSON under `phase2` without destroying anything already there.

---

# 320. FINAL DIRECTORY GUARANTEE

```text
songs/original/
    [INPUT — NEVER MODIFIED]

songs/final/
    [PUBLISHED OUTPUT]

    SongName.mp3
    SongName.lrc
    SongName.json
```

That is the final user-facing architecture.

---

# 321. FINAL ONE-LINE ARCHITECTURE

```text
MP3 + external LRC + cumulative JSON -> Demucs -> activity analysis -> reversible Telugu normalization -> LRC-anchored chunks -> MMS Telugu emissions -> true CTC forced alignment -> word spans -> validation -> one word-level LRC + metadata-preserving MP3/SYLT + cumulative JSON -> songs/final/
```

---

# 322. DOCUMENT END STATE

This document is the implementation contract for the standalone Phase 2 project.

No Phase 1 database integration is required.

No Phase 1 source code integration is required.

The file-level handoff is:

```text
MP3 + LRC + JSON
```

and the file-level output is:

```text
MP3 + LRC + JSON
```

with the JSON cumulative and the MP3 metadata-preserving.


---

# APPENDIX C — PHASE 3 ORIGINAL SPECIFICATION

The complete Phase 3 source document follows verbatim below.

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

---

# APPENDIX D — DOCUMENT INTEGRITY NOTE

This integrated file intentionally contains both:

1. the new unified architectural plan and explicit integration decisions; and
2. the complete three source specifications verbatim.

The source appendices are not additional requirements that override the unified plan. Where a standalone source specification assumes its own independent runtime/database/project boundary, the unified integration decisions in Sections 1–120 supersede that boundary for the combined implementation while preserving the underlying functional behavior.

The original phase documents remain the authoritative historical record of the standalone specifications.

---

## Source-file checksums used for this consolidation

```text
PHASE1_COMPLETE_ULTRA_DETAILED_PROJECT_PLAN.md
SHA-256: 185ab40946eb016f0c805e817cf4f05d261ed5c2e6ee5d3f47867856a6cf0c9d

PHASE2_ULTRA_DETAILED_PROJECT_PLAN.md
SHA-256: 2a890e812e351ea2efe6bb7725b21c2d5a3eb6ed3d1c15b3180f65758d0c4e78

PHASE3_FINAL_COMPLETE_ULTRA_DETAILED_PROJECT_PLAN_V2.md
SHA-256: 582300385d669981ffd192b07afde2a33e52da955a3ebb9cd7ba6b1084ce046f
```

Combined plan line count at creation: **22,548** lines.
