import hashlib, json, subprocess
from pathlib import Path
import numpy as np


def extract(path, out, sr=11025, max_seconds=420):
    p = subprocess.run(
        ['ffmpeg', '-y', '-i', str(path), '-vn', '-ac', '1', '-ar', str(sr), '-t', str(max_seconds), '-f', 'wav', str(out)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace'
    )
    if p.returncode:
        raise RuntimeError(p.stdout[-4000:])


def fingerprint(path, temp, prefix):
    import librosa
    wav = Path(temp) / (prefix + '.wav')
    extract(path, wav)
    y, sr = librosa.load(wav, sr=11025, mono=True)
    if len(y) == 0:
        raise RuntimeError('Empty audio for fingerprinting')
    hop = 1024
    chroma = librosa.feature.chroma_stft(y=y, sr=sr, n_fft=4096, hop_length=hop)
    onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop, units='time')
    if hasattr(tempo, 'item'):
        tempo = float(tempo.item())
    beats = np.asarray(beats, dtype=float)
    intervals = np.diff(beats)
    c = (chroma * 15).clip(0, 15).astype(np.uint8).tobytes()
    b = np.round(intervals[:160] * 100).clip(0, 1000).astype(np.uint16).tobytes()
    o = np.round(onset[:2000]).clip(-8, 8).astype(np.int8).tobytes()
    digest = hashlib.sha256(c + b + o).hexdigest()
    data = {
        'sha256_feature_fingerprint': digest,
        'sample_rate': sr,
        'duration_seconds': len(y) / sr,
        'tempo_bpm': tempo,
        'beat_count': int(len(beats)),
        'beat_intervals_seconds': intervals[:160].round(4).tolist(),
        'beat_times_seconds': beats[:300].round(4).tolist(),
        'chroma_frames': int(chroma.shape[1]),
        'wav': str(wav),
        'method': 'quantized chroma + onset + beat-interval feature digest',
    }
    out = Path(temp) / (prefix + '_fingerprint.json')
    out.write_text(json.dumps(data, indent=2), encoding='utf-8')
    return data, wav
