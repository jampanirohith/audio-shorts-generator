import subprocess
from pathlib import Path
import numpy as np


def _extract(path, wav):
    p = subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(path),
        "-vn", "-ac", "1", "-ar", "22050", str(wav)
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        raise RuntimeError(p.stdout[-6000:] or "Audio extraction failed for synchronization")


def _envelope(wav, rate):
    import librosa
    y, sr = librosa.load(wav, sr=22050, mono=True)
    hop = max(1, int(sr / rate))
    frame = min(2048, max(256, len(y)))
    rms = librosa.feature.rms(y=y, frame_length=frame, hop_length=hop, center=True)[0]
    rms = np.log1p(rms)
    return (rms - rms.mean()) / (rms.std() + 1e-9)


def _corr_at(youtube, spotify, lag):
    if lag >= 0:
        n = min(len(youtube) - lag, len(spotify))
        if n <= 0: return -1.0
        a = youtube[lag:lag+n]
        b = spotify[:n]
    else:
        n = min(len(youtube), len(spotify) + lag)
        if n <= 0: return -1.0
        a = youtube[:n]
        b = spotify[-lag:-lag+n]
    if n < 32: return -1.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


def synchronize(youtube, spotify, hook_start=None, cfg=None):
    cfg = cfg or {}
    rate = float(cfg.get("sync_envelope_rate", 8))
    max_seconds = float(cfg.get("sync_search_range_seconds", 120))
    work = Path(youtube).parent / ".sync"
    work.mkdir(parents=True, exist_ok=True)
    yw = work / "youtube.wav"; sw = work / "spotify.wav"
    try:
        _extract(youtube, yw); _extract(spotify, sw)
        y = _envelope(yw, rate); s = _envelope(sw, rate)
        maxlag = min(int(max_seconds * rate), len(y)-1, len(s)-1)
        if maxlag < 1: raise RuntimeError("Audio is too short for synchronization.")
        # Search every envelope frame. This is fast at 8 Hz and avoids the coarse
        # two-frame stepping that could move the final visual by 0.25s.
        scores = np.full(2*maxlag+1, -1.0, dtype=float)
        for i, lag in enumerate(range(-maxlag, maxlag+1)):
            scores[i] = _corr_at(y, s, lag)
        best_i = int(np.argmax(scores)); lag = best_i - maxlag; best = float(scores[best_i])
        # Refine the offset around the winning 1/rate sample with interpolation.
        if 0 < best_i < len(scores)-1:
            ym, yc, yp = scores[best_i-1], scores[best_i], scores[best_i+1]
            den = ym - 2*yc + yp
            frac = 0.5*(ym-yp)/den if abs(den) > 1e-12 else 0.0
            frac = float(np.clip(frac, -0.5, 0.5))
        else:
            frac = 0.0
        offset = (lag + frac) / rate
        # Confidence compares the best peak with the best competing lag.
        mask = np.ones_like(scores, dtype=bool)
        lo=max(0,best_i-int(rate*2)); hi=min(len(scores),best_i+int(rate*2)+1); mask[lo:hi]=False
        second=float(np.max(scores[mask])) if np.any(mask) else -1.0
        confidence=max(0.0, min(1.0, (best-second)/(1.0-second+1e-9)))
        result={"offset_seconds":round(float(offset),4),"confidence":round(float(confidence),4),"peak_correlation":round(best,4),"second_peak_correlation":round(second,4),"peak_margin":round(best-second,4),"method":"whole_song_audio_envelope_cross_correlation","envelope_rate_hz":rate,"search_range_seconds":max_seconds}
        # Human-readable diagnostics explain why the confidence score may be low.
        diagnostics=[]
        if best < 0.50:
            diagnostics.append(f"Best correlation is weak ({best:.4f}); the two audio envelopes do not match strongly enough.")
        elif best < 0.70:
            diagnostics.append(f"Best correlation is only moderate ({best:.4f}); loudness/envelope differences or different mixes may be present.")
        if second > best - 0.10:
            diagnostics.append(f"A competing offset is nearly as good (second peak {second:.4f}); the recording may contain repeated/ambiguous sections.")
        if abs(offset) > max_seconds * 0.90:
            diagnostics.append("The winning offset is close to the configured search limit; the true alignment may lie outside the search range.")
        if confidence < 0.45:
            diagnostics.append(f"Confidence {confidence:.4f} is below the configured minimum {float(cfg.get('sync_min_confidence',.45)):.4f}.")
        if not diagnostics:
            diagnostics.append("No major confidence warning detected; the winning peak is sufficiently distinct.")
        result["diagnostics"]=diagnostics
        # Local verification around the selected hook, if supplied.
        if hook_start is not None:
            center = int(round((float(hook_start)+offset)*rate))
            radius = int(float(cfg.get("sync_local_window_seconds",12))*rate)
            # Compare a short hook-centered region against Spotify at the predicted offset.
            ys = max(0, center-radius); ye=min(len(y),center+radius)
            ss = max(0, int(round(float(hook_start)*rate))-radius); se=min(len(s),ss+(ye-ys))
            if ye-ys >= 32 and se-ss >= 32:
                n=min(ye-ys,se-ss); local=float(np.corrcoef(y[ys:ys+n],s[ss:ss+n])[0,1])
                result["local_hook_correlation"]=round(local,4)
        return result
    finally:
        for p in (yw,sw): p.unlink(missing_ok=True)
        try: work.rmdir()
        except OSError: pass
