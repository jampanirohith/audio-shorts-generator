# Implementation Notes — Phase 3 v1.0.13

The active pipeline is timeline-driven. `hook_timeline.json` is the only hook-selection authority.

Automatic hook discovery and Smart Crop are not part of the active code path.

The video renderer uses a static centered panel at `video_layout.height_fraction` of the 1080x1920 canvas height. The horizontal crop is always centered and there is no face/body/pose tracking.

Lyrics use the LRC file as the authoritative source for the displayed line text. Enhanced LRC word timestamps drive per-word highlighting when present; Phase 2 JSON word timing is the fallback for plain LRC lines.

Final audio is built from the exact selected interval of Demucs vocals, drums, bass, and other stems. The audio timeline is not time-stretched or pitch-shifted.

YouTube synchronization is a single full-track waveform correlation between the original local song and the complete YouTube audio. The resulting global offset is added directly to the user-entered hook timeline. The final Reel audio always comes from the local MP3/Demucs stems.
