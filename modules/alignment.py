import json, subprocess
from pathlib import Path
import librosa, numpy as np

def wav(src,dst,ffmpeg):
    subprocess.run([ffmpeg,'-y','-i',str(src),'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',str(dst)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def chroma(p):
    y,sr=librosa.load(p,sr=16000,mono=True); c=librosa.feature.chroma_cqt(y=y,sr=sr,hop_length=512); c=(c-c.mean(1,keepdims=True))/(c.std(1,keepdims=True)+1e-8); return c
def align_audio(spotify_file,youtube_file,song_dir,cfg):
    d=Path(song_dir)/'_alignment'; d.mkdir(exist_ok=True); sw=d/'spotify.wav'; yw=d/'youtube.wav'; wav(spotify_file,sw,cfg['ffmpeg']); wav(youtube_file,yw,cfg['ffmpeg'])
    a,b=chroma(sw),chroma(yw); hop=512/16000; win=int(10/hop); matches=[]
    if a.shape[1]<win or b.shape[1]<win: raise RuntimeError('Audio too short for alignment.')
    starts=np.linspace(0,max(0,a.shape[1]-win),9).astype(int); bn=b/(np.linalg.norm(b,axis=0,keepdims=True)+1e-8)
    for s in starts:
        q=a[:,s:s+win]; q=q/(np.linalg.norm(q,axis=0,keepdims=True)+1e-8); qp=q.mean(1); qp/=np.linalg.norm(qp)+1e-8
        best=(-9,None)
        stride=max(1,win//6)
        for t in range(0,max(1,b.shape[1]-win),stride):
            bp=bn[:,t:t+win].mean(1); bp/=np.linalg.norm(bp)+1e-8; sc=float(np.dot(qp,bp))
            if sc>best[0]: best=(sc,t)
        if best[1] is not None: matches.append({'spotify_time':s*hop,'youtube_time':best[1]*hop,'offset':best[1]*hop-s*hop,'score':best[0]})
    offs=np.array([x['offset'] for x in matches]); med=float(np.median(offs)); dev=np.abs(offs-med); inl=[m for m,dv in zip(matches,dev) if dv<=2]
    score=float(np.mean([m['score'] for m in inl])) if inl else 0; consistency=max(0,1-float(np.median(dev))/2) if len(dev) else 0; conf=.7*score+.3*consistency
    res={'accepted':conf>=cfg['alignment_min_confidence'] and len(inl)>=3,'offset_seconds':med,'confidence':conf,'matches':matches,'inliers':inl,'spotify_file':str(spotify_file),'youtube_file':str(youtube_file)}
    (Path(song_dir)/'alignment.json').write_text(json.dumps(res,indent=2),encoding='utf-8'); return res
