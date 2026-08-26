import subprocess, numpy as np
from pathlib import Path

def _extract(video,wav):
    p=subprocess.run(['ffmpeg','-y','-i',str(video),'-vn','-ac','1','-ar','22050',str(wav)],
      stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
    if p.returncode: raise RuntimeError(p.stdout[-6000:])

def _z(x):
    x=np.asarray(x,float); return (x-np.mean(x))/(np.std(x)+1e-9)

def detect(video,temp,cfg):
    """Advanced single-hook selection: evaluate many 35-60s beat-aligned candidates,
    rank musical intensity, build-up, repetition, stability and clean endings, then
    return only the best final timeline. Only the selected video audio is analyzed."""
    import librosa
    wav=Path(temp)/'hook_audio.wav'; _extract(video,wav)
    y,sr=librosa.load(wav,sr=22050,mono=True)
    dur=len(y)/sr
    mn=float(cfg.get('hook_min_seconds',35)); lo=float(cfg.get('hook_preferred_min_seconds',40))
    hi=float(cfg.get('hook_preferred_max_seconds',60)); mx=float(cfg.get('hook_max_seconds',75))
    if dur<mn: return {'start':0.0,'end':float(dur),'duration':float(dur),'score':1.0,'reason':'source shorter than minimum'}

    hop=512; times=librosa.frames_to_time(np.arange(1+len(y)//hop),sr=sr,hop_length=hop)
    rms=librosa.feature.rms(y=y,hop_length=hop)[0]
    onset=librosa.onset.onset_strength(y=y,sr=sr,hop_length=hop)
    chroma=librosa.feature.chroma_cqt(y=y,sr=sr,hop_length=hop)
    tempo,beats=librosa.beat.beat_track(y=y,sr=sr,hop_length=hop,units='time')
    tempo=float(np.asarray(tempo).reshape(-1)[0])
    # Structural novelty/recurrence proxy.
    mfcc=librosa.feature.mfcc(y=y,sr=sr,n_mfcc=20,hop_length=hop)
    candidates=[]
    lengths=np.arange(mn,min(mx,dur)+.01,5.0)
    starts=np.arange(0,max(.01,dur-mn),1.0)
    for L in lengths:
      if L>dur: continue
      for s in starts:
        e=s+L
        if e>dur: continue
        a=int(np.searchsorted(times,s)); b=min(len(rms),int(np.searchsorted(times,e)))
        if b-a<20: continue
        r=rms[a:b]; o=onset[a:b]; m=mfcc[:,a:b]
        n=len(r); third=max(1,n//3)
        energy=np.mean(r); peak=np.percentile(r,90); activity=np.mean(o)
        buildup=np.mean(r[-third:])-np.mean(r[:third])
        dynamic=np.std(r)
        beatmask=(beats>=s)&(beats<=e); bc=np.sum(beatmask)
        beat_density=bc/max(L,1)
        # reward sections with repeated coherent musical material rather than random noise
        repeat=0.0
        if m.shape[1]>=40:
          k=m.shape[1]//2
          v1=np.mean(m[:,:k],axis=1); v2=np.mean(m[:,-k:],axis=1)
          repeat=float(np.dot(v1,v2)/(np.linalg.norm(v1)*np.linalg.norm(v2)+1e-9))
        # ending should not cut in silence or at an extreme transient
        tail=r[-max(4,int(3*sr/hop)):]
        end_level=np.mean(tail)/(np.mean(r)+1e-9)
        clean_end=1.0- min(1.0,abs(end_level-0.8))
        early_penalty=.25 if s<10 and energy<np.mean(rms)*1.05 else 0
        duration_bonus=1.0 if lo<=L<=hi else .65
        candidates.append([s,e,L,energy,peak,activity,buildup,dynamic,beat_density,repeat,clean_end,duration_bonus,early_penalty])
    if not candidates: raise RuntimeError('No hook candidates generated.')
    A=np.asarray(candidates,float)
    # Normalize each measured feature globally so incomparable units do not dominate.
    for col in [3,4,5,6,7,8,9,10]:
      A[:,col]=_z(A[:,col])
    score=(.20*A[:,3]+.13*A[:,4]+.18*A[:,5]+.15*A[:,6]+.08*A[:,7]+
           .08*A[:,8]+.10*A[:,9]+.08*A[:,10]+.06*A[:,11]-A[:,12])
    best=int(np.argmax(score))
    s,e,L=A[best,:3]
    # Snap to nearby beat boundaries for cleaner musical entry/exit.
    if len(beats):
      ss=beats[np.argmin(np.abs(beats-s))]; ee=beats[np.argmin(np.abs(beats-e))]
      if ee-ss>=mn and ee-ss<=mx: s,e=float(ss),float(ee)
    return {'start':round(float(s),3),'end':round(float(e),3),'duration':round(float(e-s),3),
      'score':round(float(score[best]),4),'tempo_bpm':round(tempo,2),'candidates_evaluated':int(len(A)),
      'reason':'best score across variable-length, 1-second-spaced musical candidates; beat-aligned boundaries'}
