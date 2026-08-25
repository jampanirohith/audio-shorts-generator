import json, re
from pathlib import Path
import librosa, numpy as np

def parse_lrc(path):
    if not path or not Path(path).exists(): return []
    out=[]; rx=re.compile(r'\[(\d+):(\d+(?:\.\d+)?)\](.*)')
    for line in Path(path).read_text(encoding='utf-8',errors='ignore').splitlines():
        m=rx.match(line.strip())
        if m:
            t=int(m.group(1))*60+float(m.group(2)); txt=m.group(3).strip()
            if txt: out.append((t,txt))
    return sorted(out)
def key(t): return re.sub(r'[^\w\u0B00-\u0B7F\u0C00-\u0C7F\u0D00-\u0D7F\u0900-\u097F ]+','',t.lower()).strip()
def detect_three_hooks(youtube_file,lrc_file,alignment,song_dir,cfg):
    y,sr=librosa.load(youtube_file,sr=22050,mono=True); dur=len(y)/sr; hop=512; times=librosa.frames_to_time(np.arange(int(np.ceil(len(y)/hop))),sr=sr,hop_length=hop)
    rms=librosa.feature.rms(y=y,frame_length=2048,hop_length=hop)[0]; rms=(rms-rms.min())/(rms.max()-rms.min()+1e-8)
    onset=librosa.onset.onset_strength(y=y,sr=sr,hop_length=hop); onset=(onset-onset.min())/(onset.max()-onset.min()+1e-8)
    lo,hi=cfg['hook_min_seconds'],cfg['hook_max_seconds']; candidates=[]
    # Analyze ONLY YouTube audio. Spotify is used solely for timeline alignment.
    step=3.0; starts=np.arange(5,max(5,dur-hi),step)
    for st in starts:
        en=min(st+hi,dur); seg=(times>=st)&(times<en)
        if seg.sum()<5: continue
        energy=float(rms[seg].mean()); beat=float(onset[seg].mean())
        # Penalize very low-energy intro/outro and favor dynamic, sustained sections.
        score=.58*energy+.42*beat
        candidates.append({'start':float(st),'end':float(en),'duration':float(en-st),'score':score,'youtube_energy':energy,'youtube_onset':beat})
    # Prefer candidates separated in time; remove near-duplicates.
    candidates.sort(key=lambda x:x['score'],reverse=True); chosen=[]
    gap=cfg['three_hook_gap_seconds']
    for c in candidates:
        if all(abs(c['start']-x['start'])>=gap for x in chosen): chosen.append(c)
        if len(chosen)==3: break
    if len(chosen)<3: raise RuntimeError('Could not find three distinct hook candidates from YouTube audio.')
    # Convert to Spotify times only for lyric lookup.
    offset=alignment['offset_seconds']
    lines=parse_lrc(lrc_file); hooks=[]
    for i,c in enumerate(chosen,1):
        sp_start=c['start']-offset; sp_end=c['end']-offset
        lyrics=[{'time':t,'text':txt} for t,txt in lines if sp_start<=t<sp_end]
        h=dict(c,index=i,spotify_start=sp_start,spotify_end=sp_end,lyrics=lyrics,accepted=True)
        hooks.append(h)
    result={'accepted':True,'hooks':hooks,'method':'YouTube-audio energy + onset dynamics; Spotify audio is not used for hook scoring'}
    (Path(song_dir)/'hooks.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8'); return result
