import subprocess
from pathlib import Path

import numpy as np


def _extract_audio(video, wav):
    proc = subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(video),
            "-vn", "-ac", "1", "-ar", "22050",
            str(wav),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode:
        raise RuntimeError(proc.stdout[-6000:] or "FFmpeg audio extraction failed.")


def _z(values):
    values = np.asarray(values, dtype=float)
    return (values - np.mean(values)) / (np.std(values) + 1e-9)


def detect(video, temp_dir, cfg):
    """
    Select exactly one musical hook from the chosen video's own audio.

    Candidates overlap heavily, use variable durations, and are scored using
    energy, peaks, onset activity, build-up, dynamics, beat density, repeated
    musical material, ending quality, and preferred duration.
    """
    import librosa

    temp = Path(temp_dir)
    wav = temp / "hook_analysis.wav"
    _extract_audio(video, wav)

    y, sr = librosa.load(wav, sr=22050, mono=True)
    duration = len(y) / sr

    minimum = float(cfg.get("hook_min_seconds", 35))
    preferred_min = float(cfg.get("hook_preferred_min_seconds", 40))
    preferred_max = float(cfg.get("hook_preferred_max_seconds", 55))
    maximum = float(cfg.get("hook_max_seconds", 60))

    if duration <= 0:
        raise RuntimeError("Selected video contains no usable audio.")

    if duration < minimum:
        return {
            "start": 0.0,
            "end": round(float(duration), 3),
            "duration": round(float(duration), 3),
            "score": 1.0,
            "tempo_bpm": None,
            "candidates_evaluated": 1,
            "reason": "source is shorter than configured minimum",
        }

    hop = 512
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20, hop_length=hop)
    times = librosa.frames_to_time(
        np.arange(len(rms)), sr=sr, hop_length=hop
    )

    tempo, beats = librosa.beat.beat_track(
        y=y, sr=sr, hop_length=hop, units="time"
    )
    tempo = float(np.asarray(tempo).reshape(-1)[0]) if np.size(tempo) else 0.0

    lengths = np.arange(
        minimum,
        min(maximum, duration) + 0.001,
        5.0,
    )
    starts = np.arange(0.0, max(0.01, duration - minimum), 1.0)

    candidates = []
    for length in lengths:
        if length > duration:
            continue

        for start in starts:
            end = start + length
            if end > duration:
                continue

            a = int(np.searchsorted(times, start))
            b = min(len(rms), int(np.searchsorted(times, end)))
            if b - a < 20:
                continue

            r = rms[a:b]
            o = onset[a:b]
            m = mfcc[:, a:b]

            third = max(1, len(r) // 3)
            energy = float(np.mean(r))
            peak = float(np.percentile(r, 90))
            activity = float(np.mean(o))
            buildup = float(np.mean(r[-third:]) - np.mean(r[:third]))
            dynamic = float(np.std(r))

            beat_count = int(np.sum((beats >= start) & (beats <= end)))
            beat_density = beat_count / max(length, 1.0)

            repeat = 0.0
            if m.shape[1] >= 40:
                half = m.shape[1] // 2
                first = np.mean(m[:, :half], axis=1)
                last = np.mean(m[:, -half:], axis=1)
                repeat = float(
                    np.dot(first, last)
                    / (np.linalg.norm(first) * np.linalg.norm(last) + 1e-9)
                )

            tail = r[-max(4, int(3 * sr / hop)):]
            end_level = float(np.mean(tail) / (np.mean(r) + 1e-9))
            clean_end = 1.0 - min(1.0, abs(end_level - 0.8))

            early_penalty = (
                0.25
                if start < 10 and energy < np.mean(rms) * 1.05
                else 0.0
            )
            duration_bonus = (
                1.0 if preferred_min <= length <= preferred_max else 0.65
            )

            candidates.append([
                start, end, length, energy, peak, activity, buildup,
                dynamic, beat_density, repeat, clean_end,
                duration_bonus, early_penalty,
            ])

    if not candidates:
        raise RuntimeError("No valid hook candidates could be generated.")

    matrix = np.asarray(candidates, dtype=float)
    for column in range(3, 11):
        matrix[:, column] = _z(matrix[:, column])

    scores = (
        0.20 * matrix[:, 3]
        + 0.13 * matrix[:, 4]
        + 0.18 * matrix[:, 5]
        + 0.15 * matrix[:, 6]
        + 0.08 * matrix[:, 7]
        + 0.08 * matrix[:, 8]
        + 0.10 * matrix[:, 9]
        + 0.08 * matrix[:, 10]
        + 0.06 * matrix[:, 11]
        - matrix[:, 12]
    )

    best_index = int(np.argmax(scores))
    start, end, length = matrix[best_index, :3]

    if len(beats):
        beat_start = float(beats[np.argmin(np.abs(beats - start))])
        beat_end = float(beats[np.argmin(np.abs(beats - end))])
        if minimum <= beat_end - beat_start <= maximum:
            start, end = beat_start, beat_end
            length = end - start

    return {
        "start": round(float(start), 3),
        "end": round(float(end), 3),
        "duration": round(float(length), 3),
        "score": round(float(scores[best_index]), 4),
        "tempo_bpm": round(tempo, 2),
        "candidates_evaluated": int(len(matrix)),
        "candidate_spacing_seconds": 1.0,
        "candidate_length_step_seconds": 5.0,
        "beat_aligned": bool(len(beats)),
        "reason": "best score across overlapping variable-length musical candidates",
    }
