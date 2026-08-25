import subprocess, numpy as np
from pathlib import Path

def extract_mono(video,out):
    p=subprocess.run(['ffmpeg','-y','-i',str(video),'-vn','-ac','1','-ar','22050','-f','wav',str(out)],
                     stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
    if p.returncode: raise RuntimeError(p.stdout[-4000:])

def detect(video,temp,cfg):
    import librosa
    wav=Path(temp)/'youtube_hook_audio.wav'; extract_mono(video,wav)
    y,sr=librosa.load(wav,sr=22050,mono=True)
    dur=len(y)/sr; mn=cfg['hook_min_seconds']; target=cfg['hook_target_seconds']; mx=cfg['hook_max_seconds']
    if dur < mn+2: raise RuntimeError('Video/song is too short for hook detection')
    hop=512
    rms=librosa.feature.rms(y=y,frame_length=2048,hop_length=hop)[0]
    onset=librosa.onset.onset_strength(y=y,sr=sr,hop_length=hop)
    tempo,beats=librosa.beat.beat_track(y=y,sr=sr,hop_length=hop,units='time')
    if hasattr(tempo,'item'): tempo=float(tempo.item())
    # Search every 1 second and score musical energy + onset density + beat density.
    candidates=[]
    for start in np.arange(0,max(0,dur-mn),1.0):
        end=min(dur,start+target)
        if end-start>mx: end=start+mx
        i0=max(0,int(start*len(rms)/dur)); i1=max(i0+1,int(end*len(rms)/dur))
        e=float(np.mean(rms[i0:i1])); o=float(np.mean(onset[i0:i1]))
        bc=float(np.sum((np.asarray(beats)>=start)&(np.asarray(beats)<=end)))
        # Favor sections that are energetic and rhythmically active, but don't let loud
        # intros win solely because they are loud.
        score=0.50*e+0.35*o+0.15*(bc/max(1,(end-start))*2.0)
        candidates.append((score,start,end))
    candidates.sort(reverse=True)
    chosen=[]
    for c in candidates:
        if all(abs(c[1]-x[1])>=mn*0.70 for x in chosen): chosen.append(c)
        if len(chosen)==3: break
    if len(chosen)<3:
        raise RuntimeError('Could not find three distinct hook candidates')
    return [{'rank':i+1,'score':round(c[0],6),'start':round(c[1],3),'end':round(c[2],3),'duration':round(c[2]-c[1],3),'tempo_bpm':round(tempo,2)} for i,c in enumerate(chosen)]
