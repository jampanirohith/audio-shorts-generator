import subprocess,numpy as np
from pathlib import Path
def envelope(path,rate=8):
 import librosa
 p=Path(path);wav=p.with_suffix('.sync.wav');q=subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error','-i',str(p),'-vn','-ac','1','-ar','22050',str(wav)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
 if q.returncode:raise RuntimeError(q.stdout[-6000:] or 'Audio extraction failed for synchronization')
 y,sr=librosa.load(wav,sr=22050,mono=True);wav.unlink(missing_ok=True);hop=max(1,int(sr/rate));r=librosa.feature.rms(y=y,frame_length=min(2048,len(y)),hop_length=hop)[0];r=np.log1p(r);return (r-r.mean())/(r.std()+1e-9)
def synchronize(youtube,spotify):
 a=envelope(youtube);b=envelope(spotify);maxlag=min(120*8,len(a)-1,len(b)-1);best=(-1,0)
 for lag in range(-maxlag,maxlag+1,2):
  aa=a[lag:] if lag>=0 else a[:len(a)+lag];bb=b[:len(aa)] if lag>=0 else b[-lag:];m=min(len(aa),len(bb))
  if m<16:continue
  c=float(np.corrcoef(aa[:m],bb[:m])[0,1]);
  if c>best[0]:best=(c,lag)
 return {'offset_seconds':round(best[1]/8,3),'confidence':round(max(0,best[0]),4),'method':'whole_song_energy_highs_lows','search_range_seconds':120}
