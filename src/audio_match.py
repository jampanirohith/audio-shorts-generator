from __future__ import annotations

from pathlib import Path
import numpy as np
from scipy.signal import correlate
from .audio_io import decode_wav
from .utils import Phase3Error, clamp, json_dump


class AudioMatcher:
    """Find one simple global YouTube offset from a 15-second song-start anchor.

    The first 15 seconds of the original local song are treated as an anchor.
    The YouTube audio is scanned forward from time zero in short energy-envelope
    windows.  Each candidate is scored from two very simple signatures:

      1. frame RMS / loudness high-low shape
      2. changes between adjacent frame energies (peak/valley shape)

    The best location is the global offset.  The manually entered hook is then
    mapped with that one offset; the hook itself is never re-searched.
    """

    def __init__(self, cfg, work_dir, logger):
        self.cfg = cfg
        self.work = Path(work_dir)
        self.logger = logger

    def _decode(self, path: Path) -> tuple[np.ndarray, int]:
        sr = int(self.cfg.get("video_match.sync_sample_rate", 4000))
        sr = max(2000, min(sr, 8000))
        y, rate = decode_wav(path, sr, True)
        y = np.asarray(y, dtype=np.float32)
        if y.size < max(100, int(rate * 0.2)):
            raise Phase3Error("VIDEO_MATCH_LOW_CONFIDENCE", f"Audio is too short to synchronize: {path}")
        y = y - float(np.mean(y))
        peak = float(np.max(np.abs(y))) if y.size else 0.0
        if peak <= 1e-8 or float(np.std(y)) <= 1e-8:
            raise Phase3Error("VIDEO_MATCH_LOW_CONFIDENCE", f"Audio is effectively silent: {path}")
        y = np.clip(y / max(peak, 1e-8), -1.0, 1.0)
        return y.astype(np.float32), rate

    @staticmethod
    def _energy_signature(y: np.ndarray, sr: int, frame_ms: float, hop_ms: float) -> tuple[np.ndarray, np.ndarray]:
        frame = max(8, int(round(sr * frame_ms / 1000.0)))
        hop = max(4, int(round(sr * hop_ms / 1000.0)))
        if len(y) < frame:
            return np.empty(0, dtype=np.float32), np.empty(0, dtype=np.float32)
        count = 1 + (len(y) - frame) // hop
        shape = np.lib.stride_tricks.as_strided(
            y,
            shape=(count, frame),
            strides=(y.strides[0] * hop, y.strides[0]),
            writeable=False,
        )
        rms = np.sqrt(np.mean(shape * shape, axis=1) + 1e-12).astype(np.float32)
        # Log-RMS makes the signature less sensitive to mastering/volume changes.
        energy = np.log1p(20.0 * rms).astype(np.float32)
        energy -= float(np.mean(energy))
        sd = float(np.std(energy))
        if sd > 1e-8:
            energy /= sd
        delta = np.diff(energy, prepend=energy[:1]).astype(np.float32)
        dsd = float(np.std(delta))
        if dsd > 1e-8:
            delta /= dsd
        return energy, delta

    @staticmethod
    def _sliding_normalized_scores(signal: np.ndarray, template: np.ndarray) -> np.ndarray:
        """Normalized dot-product score for every same-length sliding window."""
        n = len(template)
        if n == 0 or len(signal) < n:
            return np.empty(0, dtype=np.float32)
        template = template.astype(np.float64)
        template -= template.mean()
        denom_t = np.linalg.norm(template)
        if denom_t <= 1e-12:
            return np.full(len(signal) - n + 1, -1.0, dtype=np.float32)
        corr = correlate(signal.astype(np.float64), template, mode="valid", method="fft")
        cs = np.concatenate(([0.0], np.cumsum(signal.astype(np.float64))))
        cs2 = np.concatenate(([0.0], np.cumsum(signal.astype(np.float64) ** 2)))
        sums = cs[n:] - cs[:-n]
        sums2 = cs2[n:] - cs2[:-n]
        means = sums / n
        var = np.maximum(sums2 / n - means * means, 0.0)
        denom = np.sqrt(var * n) * denom_t
        scores = np.full_like(corr, -1.0, dtype=np.float64)
        good = denom > 1e-12
        scores[good] = corr[good] / denom[good]
        return np.clip(scores, -1.0, 1.0).astype(np.float32)

    def match(self, original_song: Path, youtube_audio: Path, hook_start_ms: int, hook_end_ms: int) -> dict:
        original, sr = self._decode(original_song)
        youtube, ysr = self._decode(youtube_audio)
        if sr != ysr:
            raise Phase3Error("VIDEO_MATCH_LOW_CONFIDENCE", f"Sync sample-rate mismatch: {sr} vs {ysr}")

        anchor_seconds = float(self.cfg.get("video_match.anchor_seconds", 15.0))
        anchor_seconds = max(5.0, min(anchor_seconds, 30.0))
        anchor_samples = min(len(original), int(round(anchor_seconds * sr)))
        original_anchor = original[:anchor_samples]
        if len(original_anchor) < int(5 * sr):
            raise Phase3Error("VIDEO_MATCH_LOW_CONFIDENCE", "Original song is shorter than the minimum sync anchor")

        frame_ms = float(self.cfg.get("video_match.sync_frame_ms", 50.0))
        hop_ms = float(self.cfg.get("video_match.sync_hop_ms", 25.0))
        anchor_energy, anchor_delta = self._energy_signature(original_anchor, sr, frame_ms, hop_ms)
        youtube_energy, youtube_delta = self._energy_signature(youtube, sr, frame_ms, hop_ms)
        if len(anchor_energy) == 0 or len(youtube_energy) < len(anchor_energy):
            raise Phase3Error("VIDEO_MATCH_LOW_CONFIDENCE", "YouTube audio is shorter than the sync anchor")

        energy_scores = self._sliding_normalized_scores(youtube_energy, anchor_energy)
        delta_scores = self._sliding_normalized_scores(youtube_delta, anchor_delta)
        # High/low envelope is the main signal; peak/valley changes break ties.
        scores = (0.72 * energy_scores + 0.28 * delta_scores).astype(np.float32)

        # Prefer the earliest candidate when multiple nearby locations are nearly identical.
        best_score = float(np.max(scores))
        tolerance = float(self.cfg.get("video_match.earliest_near_best_tolerance", 0.015))
        near = np.flatnonzero(scores >= best_score - tolerance)
        best_index = int(near[0]) if near.size else int(np.argmax(scores))
        offset_ms = int(round(best_index * hop_ms))

        energy_corr = float(energy_scores[best_index])
        delta_corr = float(delta_scores[best_index])
        confidence = float(clamp((float(scores[best_index]) + 1.0) / 2.0, 0.0, 1.0))
        youtube_duration_ms = int(round(len(youtube) * 1000.0 / sr))
        video_start_ms = int(hook_start_ms + offset_ms)
        video_end_ms = int(hook_end_ms + offset_ms)
        hook_duration_ms = int(hook_end_ms - hook_start_ms)

        if video_start_ms < 0 or video_end_ms > youtube_duration_ms:
            raise Phase3Error(
                "VIDEO_MATCH_LOW_CONFIDENCE",
                f"15-second anchor maps the selected hook outside the YouTube audio: {video_start_ms}..{video_end_ms} ms of {youtube_duration_ms} ms",
                details={
                    "offset_ms": offset_ms,
                    "anchor_seconds": anchor_seconds,
                    "anchor_score": float(scores[best_index]),
                    "hook_start_ms": int(hook_start_ms),
                    "hook_end_ms": int(hook_end_ms),
                    "youtube_duration_ms": youtube_duration_ms,
                },
            )

        result = {
            "match_method": "first_15s_energy_anchor",
            "accepted": True,
            "offset_ms": offset_ms,
            "offset_seconds": offset_ms / 1000.0,
            "offset_sign": "+" if offset_ms >= 0 else "-",
            "confidence": confidence,
            "anchor_score": float(scores[best_index]),
            "energy_correlation": energy_corr,
            "peak_valley_correlation": delta_corr,
            "anchor_seconds": anchor_seconds,
            "anchor_start_ms": 0,
            "anchor_end_ms": int(round(anchor_seconds * 1000.0)),
            "scan_start_ms": 0,
            "scan_step_ms": int(round(hop_ms)),
            "sync_sample_rate": int(sr),
            "sync_frame_ms": frame_ms,
            "sync_hop_ms": hop_ms,
            "original_duration_ms": int(round(len(original) * 1000.0 / sr)),
            "youtube_duration_ms": youtube_duration_ms,
            "youtube_anchor_start_ms": offset_ms,
            "youtube_anchor_end_ms": offset_ms + int(round(anchor_seconds * 1000.0)),
            "hook_start_ms": int(hook_start_ms),
            "hook_end_ms": int(hook_end_ms),
            "hook_duration_ms": hook_duration_ms,
            "video_match_start_ms": video_start_ms,
            "video_match_end_ms": video_end_ms,
            "query_start_ms": int(hook_start_ms),
            "query_end_ms": int(hook_end_ms),
            "selected_by": "hook_timeline.json",
        }

        out_dir = self.work / "matching"
        json_dump(out_dir / "global_offset.json", result)
        json_dump(out_dir / "best_video_match.json", result)
        json_dump(
            out_dir / "coarse_matches.json",
            {
                "match_method": "first_15s_energy_anchor",
                "offset_ms": offset_ms,
                "anchor_score": float(scores[best_index]),
                "energy_correlation": energy_corr,
                "peak_valley_correlation": delta_corr,
            },
        )

        if self.logger:
            sign = "+" if offset_ms >= 0 else "-"
            self.logger.info(
                "YouTube 15s anchor offset: %s%d ms (%s%.3f s), score %.4f (energy %.4f, peaks/valleys %.4f)",
                sign,
                abs(offset_ms),
                sign,
                abs(offset_ms) / 1000.0,
                float(scores[best_index]),
                energy_corr,
                delta_corr,
            )
        return result
