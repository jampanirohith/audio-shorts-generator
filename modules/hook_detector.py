from __future__ import annotations
import json, math, subprocess
from pathlib import Path
import numpy as np
import librosa
from scipy.ndimage import gaussian_filter1d

def _norm(x):
    x=np.asarray(x,dtype=float); 
    if x.size==0:return x
    lo,hi=np.percentile(x,[5,95]); return np.clip((x-lo)/(hi-lo+1e-9),0,1)

def _sim(a,b):
    if len(a)==0 or len(b)==0:return 0
    n=min(len(a),len(b))
    a=a[:n]; b=b[:n]
    if np.std(a)<1e-8 or np.std(b)<1e-8:return 0
    return float((np.corrcoef(a,b)[0,1]+1)/2)

def _window_score(features,s,e):
    t=features["times"]; mask=(t>=s)&(t<=e)
    idx=np.where(mask)[0]
    if len(idx)<3:return -1e9,{}
    rms=features["rms"][idx]; onset=features["onset"][idx]
    chrom=features["chrom"][...,idx]
    energy=float(np.mean(rms))
    peak=float(np.percentile(rms,85))
    dyn=float(np.std(rms))
    on=float(np.mean(onset))
    # repetition: compare first/last halves and against nearby same-length windows
    mid=len(idx)//2
    rep=_sim(rms[:mid],rms[mid:]) if mid>3 else 0
    beat_q=float(np.mean(features["beat_quality"][idx]))
    startq=float(features["boundary"](s))
    endq=float(features["boundary"](e))
    resolution=float(features["resolution"](s,e))
    # Prefer an ending that resolves rather than stopping on an arbitrary peak.
    tail=rms[max(0,len(rms)-12):]
    tail_var=float(np.std(tail)) if len(tail)>2 else 0
    tail_clean=float(np.clip(1-tail_var*2.5,0,1))
    score=(0.15*energy+0.13*peak+0.10*dyn+0.13*on+0.16*rep+
           0.11*beat_q+0.08*startq+0.09*endq+0.05*resolution+0.10*tail_clean)
    return score,{"energy":energy,"peak":peak,"dynamic":dyn,"onset":on,"repetition":rep,
                   "beat_alignment":beat_q,"start_boundary":startq,"end_boundary":endq,
                   "ending_resolution":resolution,"tail_clean":tail_clean}

def detect(wav,outdir,cfg):
    y,sr=librosa.load(str(wav),sr=22050,mono=True)
    dur=len(y)/sr
    hop=512
    rms=librosa.feature.rms(y=y,hop_length=hop)[0]
    onset=librosa.onset.onset_strength(y=y,sr=sr,hop_length=hop)
    chrom=librosa.feature.chroma_stft(y=y,sr=sr,hop_length=hop)
    times=librosa.frames_to_time(np.arange(len(rms)),sr=sr,hop_length=hop)
    onset=np.resize(onset,len(rms))
    tempo,beats=librosa.beat.beat_track(y=y,sr=sr,hop_length=hop)
    beat_times=librosa.frames_to_time(beats,sr=sr,hop_length=hop)
    rms_s=gaussian_filter1d(_norm(rms),2)
    onset_s=gaussian_filter1d(_norm(onset),2)
    # Phrase-like boundaries from novelty/energy changes.
    delta=np.abs(np.diff(rms_s,prepend=rms_s[0]))
    peaks=np.where(delta>np.percentile(delta,88))[0]
    boundary_times=list(times[peaks])
    boundary_times += list(beat_times)
    boundary_times=sorted(set(round(float(x),2) for x in boundary_times if 0<x<dur))
    def boundary(t):
        if not boundary_times:return 0.4
        d=min(abs(t-x) for x in boundary_times)
        return float(np.exp(-d/0.75))
    def resolution(s,e):
        # ending is stronger when the last seconds descend/stabilize
        mask=(times>=max(s,e-4))&(times<=e)
        a=rms_s[mask]
        if len(a)<4:return 0.4
        slope=float(np.polyfit(np.arange(len(a)),a,1)[0])
        return float(np.clip(0.5-slope*3,0,1))
    beat_quality=np.zeros(len(times))
    for bt in beat_times:
        j=int(np.argmin(abs(times-bt)))
        beat_quality[max(0,j-1):min(len(times),j+2)]=1
    features={"times":times,"rms":rms_s,"onset":onset_s,"chrom":chrom,
              "boundary":boundary,"resolution":resolution,"beat_quality":beat_quality}
    min_s=float(cfg["hook"]["min_seconds"]); pref_min=float(cfg["hook"]["preferred_min"])
    pref_max=float(cfg["hook"]["preferred_max"]); max_s=float(cfg["hook"]["max_seconds"])
    target_n=int(cfg["hook"].get("candidate_count",15))
    if dur<min_s: raise RuntimeError(f"Video/audio is only {dur:.2f}s; shorter than minimum hook duration.")
    # Generate many candidates at several durations; duration is NOT fixed.
    candidates=[]
    duration_grid=np.linspace(pref_min,pref_max,7).tolist()+[min_s,max_s]
    for L in duration_grid:
        step=max(2.0,L/8)
        starts=np.arange(0,max(0,dur-L)+0.001,step)
        for s in starts:
            e=min(dur,s+L)
            sc,m=_window_score(features,float(s),float(e))
            # soft duration preference, not a hard requirement
            center=(pref_min+pref_max)/2
            dur_pref=math.exp(-((L-center)/(max(1,(pref_max-pref_min)/1.7)))**2)
            sc += 0.10*dur_pref
            candidates.append({"start":float(s),"end":float(e),"score":float(sc),"metrics":m})
    candidates.sort(key=lambda x:x["score"],reverse=True)
    refined=[]
    for c in candidates[:max(40,target_n*4)]:
        s,e=c["start"],c["end"]
        # refine each boundary locally on 0.25s grid
        best=(c["score"],s,e,c["metrics"])
        for ss in np.arange(max(0,s-4),min(e-min_s,s+4)+0.001,0.25):
            for ee in np.arange(max(ss+min_s,e-4),min(dur,ss+max_s,e+4)+0.001,0.25):
                sc,m=_window_score(features,float(ss),float(ee))
                if pref_min<=ee-ss<=pref_max: sc+=0.06
                if sc>best[0]:best=(sc,float(ss),float(ee),m)
        refined.append({"start":best[1],"end":best[2],"score":best[0],"metrics":best[3]})
    refined.sort(key=lambda x:x["score"],reverse=True)
    dedup=[]
    for c in refined:
        overlap=False
        for d in dedup:
            inter=max(0,min(c["end"],d["end"])-max(c["start"],d["start"]))
            union=max(c["end"],d["end"])-min(c["start"],d["start"])
            if union and inter/union>0.65: overlap=True; break
        if not overlap: dedup.append(c)
        if len(dedup)>=target_n: break
    final=dedup[0]
    report={"duration":dur,"tempo_bpm":float(np.asarray(tempo).reshape(-1)[0]) if np.asarray(tempo).size else None,
            "beat_count":len(beat_times),"candidate_count":len(candidates),"refined_count":len(refined),
            "unique_candidates":len(dedup),"final":final,"top_candidates":dedup}
    Path(outdir,"hook_analysis.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    return final,report

def cut_video(video,start,end,out):
    dur=end-start
    args=["ffmpeg","-y","-hide_banner","-loglevel","error","-ss",f"{start:.3f}","-i",str(video),
          "-t",f"{dur:.3f}","-map","0:v:0","-map","0:a:0?","-c:v","libx264","-preset","medium","-crf","18","-c:a","aac","-b:a","192k",str(out)]
    p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding="utf-8",errors="replace")
    if p.returncode: raise RuntimeError(p.stderr[-4000:])
