import json, subprocess
from pathlib import Path
import numpy as np


def _wav(path, out, sr=11025, max_seconds=420):
    p = subprocess.run(
        ['ffmpeg', '-y', '-i', str(path), '-vn', '-ac', '1', '-ar', str(sr), '-t', str(max_seconds), '-f', 'wav', str(out)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace'
    )
    if p.returncode:
        raise RuntimeError(p.stdout[-4000:])


def _features(wav, sr=11025):
    import librosa
    y, _ = librosa.load(wav, sr=sr, mono=True)
    hop = 1024
    onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop, units='time')
    if hasattr(tempo, 'item'):
        tempo = float(tempo.item())
    beats = np.asarray(beats, dtype=float)
    onset = (onset - onset.mean()) / (onset.std() + 1e-8)
    chroma = (chroma - chroma.mean(axis=1, keepdims=True)) / (chroma.std(axis=1, keepdims=True) + 1e-8)
    return onset.astype(np.float32), chroma.astype(np.float32), beats, float(tempo), sr / hop


def _cos(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def _candidate_lags(sp_on, sp_ch, yt_on, yt_ch, start, length, fps):
    end = min(start + length, len(sp_on))
    if end - start < int(8 * fps):
        return []
    a_on = sp_on[start:end]
    a_ch = sp_ch[:, start:end]
    n = len(a_on)
    if len(yt_on) <= n + 2:
        return []
    import scipy.signal
    conv = scipy.signal.fftconvolve(yt_on, a_on[::-1], mode='valid')
    count = min(30, len(conv))
    idxs = np.argpartition(conv, -count)[-count:]
    rows = []
    for lag in idxs:
        lag = int(lag)
        z_on = yt_on[lag:lag+n]
        on_score = _cos(z_on, a_on)
        ch_scores = [_cos(yt_ch[c, lag:lag+n], a_ch[c]) for c in range(min(12, a_ch.shape[0]))]
        ch_score = float(np.mean(ch_scores))
        rows.append((.42 * on_score + .58 * ch_score, lag))
    return sorted(rows, reverse=True)[:8]


def _beat_consistency(sp_beats, yt_beats, offset, tolerance=0.18):
    if len(sp_beats) < 8 or len(yt_beats) < 8:
        return 0.0
    yt = np.asarray(yt_beats)
    mapped = np.asarray(sp_beats) + offset
    diffs = []
    for x in mapped:
        j = np.searchsorted(yt, x)
        candidates = []
        if j < len(yt): candidates.append(abs(yt[j] - x))
        if j > 0: candidates.append(abs(yt[j-1] - x))
        if candidates: diffs.append(min(candidates))
    if not diffs:
        return 0.0
    return float(np.mean(np.asarray(diffs) <= tolerance))


def align(spotify, youtube, temp):
    """Align recordings using onset + chroma + beat agreement across multiple anchors.

    Positive offset means: YouTube timestamp = Spotify timestamp + offset.
    This specifically handles a movie/video intro before the same song recording.
    """
    temp = Path(temp)
    spwav = temp / 'align_spotify.wav'
    ytwav = temp / 'align_youtube.wav'
    _wav(spotify, spwav)
    _wav(youtube, ytwav)
    sp_on, sp_ch, sp_beats, sp_tempo, fps = _features(spwav)
    yt_on, yt_ch, yt_beats, yt_tempo, _ = _features(ytwav)

    total = len(sp_on)
    window = max(int(24 * fps), 100)
    starts = [int(total * p) for p in (0.12, 0.28, 0.44, 0.60, 0.76)]
    anchors = []
    for s in starts:
        candidates = _candidate_lags(sp_on, sp_ch, yt_on, yt_ch, s, window, fps)
        if not candidates:
            continue
        score, lag = candidates[0]
        anchors.append({
            'spotify_seconds': s / fps,
            'youtube_seconds': lag / fps,
            'offset_seconds': lag / fps - s / fps,
            'feature_score': float(score),
        })

    if not anchors:
        raise RuntimeError('Could not align Spotify and YouTube audio.')

    offsets = np.asarray([a['offset_seconds'] for a in anchors], dtype=float)
    median_offset = float(np.median(offsets))
    # Reject obvious outlier anchors, then recalculate the final offset.
    good = [a for a in anchors if abs(a['offset_seconds'] - median_offset) <= 1.0]
    if not good:
        raise RuntimeError('No consistent alignment anchors found. The Spotify recording may be a different edit.')
    offsets2 = np.asarray([a['offset_seconds'] for a in good], dtype=float)
    offset = float(np.median(offsets2))
    spread = float(np.max(offsets2) - np.min(offsets2)) if len(offsets2) > 1 else 0.0
    feature_conf = float(np.mean([a['feature_score'] for a in good]))
    beat_conf = _beat_consistency(sp_beats, yt_beats, offset)
    confidence = .72 * feature_conf + .28 * beat_conf

    result = {
        'spotify_to_youtube_offset_seconds': round(offset, 4),
        'confidence': round(float(confidence), 4),
        'feature_confidence': round(feature_conf, 4),
        'beat_alignment_confidence': round(beat_conf, 4),
        'offset_spread_seconds': round(spread, 4),
        'spotify_tempo_bpm': round(sp_tempo, 3),
        'youtube_tempo_bpm': round(yt_tempo, 3),
        'anchors': anchors,
        'method': 'multi-anchor onset-envelope + chroma-CQT normalized cross-correlation, verified with beat-time agreement',
    }
    (temp / 'alignment.json').write_text(json.dumps(result, indent=2), encoding='utf-8')

    if len(good) < 2:
        raise RuntimeError('Audio alignment produced fewer than two consistent anchors.')
    if feature_conf < .34 or confidence < .40:
        raise RuntimeError(f'Audio alignment confidence too low ({confidence:.3f}); choose the correct Spotify recording.')
    if spread > 1.25:
        raise RuntimeError(f'Audio alignment is inconsistent (offset spread {spread:.2f}s); recordings may be different edits.')
    return result
