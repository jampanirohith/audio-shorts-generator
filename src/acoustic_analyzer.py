from __future__ import annotations
from pathlib import Path
import json, numpy as np
from scipy.signal import find_peaks
from .audio_io import decode_wav
from .utils import json_dump

class AcousticAnalyzer:
    def __init__(self,cfg,work_dir,logger): self.cfg=cfg; self.work=work_dir; self.logger=logger
    def analyze(self, source_mp3:Path, stems:dict)->dict:
        import librosa
        sr=16000; mix,_=decode_wav(source_mp3,sr,True)
        # 0.5s frame features for efficient candidate lookup.
        hop=sr//2; win=sr
        signals={'mix':mix}
        for k,p in stems.items():
            if k in ('vocals','drums','bass','other'):
                try: signals[k],_=decode_wav(Path(p),sr,True)
                except Exception: continue
        n=max(len(x) for x in signals.values());
        for k,v in list(signals.items()):
            if len(v)<n: signals[k]=np.pad(v,(0,n-len(v)))
        def rms(x):
            frames=librosa.util.frame(x,frame_length=win,hop_length=hop).T
            return np.sqrt(np.mean(frames**2,axis=1)+1e-12)
        feats={k:rms(v) for k,v in signals.items()}
        onset=librosa.onset.onset_strength(y=mix,sr=sr,hop_length=hop)
        if len(onset)<len(feats['mix']): onset=np.pad(onset,(0,len(feats['mix'])-len(onset)))
        else: onset=onset[:len(feats['mix'])]
        centroid=librosa.feature.spectral_centroid(y=mix,sr=sr,hop_length=hop,n_fft=2048)[0]
        if len(centroid)<len(feats['mix']): centroid=np.pad(centroid,(0,len(feats['mix'])-len(centroid)),mode='edge')
        else: centroid=centroid[:len(feats['mix'])]
        energy=feats['mix'];
        peaks,_=find_peaks(onset,distance=max(1,int(2*1000/(hop*1000/sr))),prominence=np.std(onset)*0.4 if np.std(onset)>0 else None)
        time_ms=(np.arange(len(energy))*500).astype(int)
        result={'sample_rate':sr,'frame_ms':500,'duration_ms':int(round(len(mix)/sr*1000)),'time_ms':time_ms.tolist(),
                'features':{k:np.asarray(v,dtype=float).tolist() for k,v in feats.items()},
                'onset_strength':onset.astype(float).tolist(),'spectral_centroid':centroid.astype(float).tolist(),
                'energy_peaks_ms':(time_ms[peaks].astype(int)).tolist()}
        json_dump(self.work/'analysis'/'acoustic_features.json',result)
        return result
