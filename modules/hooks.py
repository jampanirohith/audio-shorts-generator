import subprocess,numpy as np
from pathlib import Path
from .lyrics import parse_lrc,lines_in_range
def extract(video,wav):
 p=subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error','-i',str(video),'-vn','-ac','1','-ar','22050',str(wav)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
 if p.returncode:raise RuntimeError(p.stdout[-6000:] or 'Audio extraction failed')
def z(x):x=np.asarray(x,float);return (x-x.mean())/(x.std()+1e-9)
def lyric_stats(lines,s,e):
 ls=lines_in_range(lines,s,e);texts=[x['text'] for x in ls];norm=[x['text'].strip().lower() for x in ls];rep=sum(1 for i,x in enumerate(norm) if x and x in norm[:i]);return {'density':sum(len(x.split()) for x in texts)/max(e-s,1),'repeated_lines':rep,'line_count':len(ls),'completeness':1 if ls and abs(ls[0]['time']-s)<1.5 else .5}
def detect(video,temp,cfg,youtube_lrc=None,spotify_lrc=None,sync=None):
 import librosa
 temp=Path(temp); wav=temp/'hook_analysis.wav'; extract(video,wav)
 y,sr=librosa.load(wav,sr=22050,mono=True); duration=len(y)/sr
 preferred_min=float(cfg.get('hook_min_seconds',35))
 candidate_min=float(cfg.get('hook_candidate_absolute_min_seconds',30))
 preferred_max=float(cfg.get('hook_max_seconds',60))
 candidate_max=float(cfg.get('hook_candidate_absolute_max_seconds',65))
 pmin=float(cfg.get('hook_preferred_min_seconds',40)); pmax=float(cfg.get('hook_preferred_max_seconds',55))
 if duration<=0: raise RuntimeError('Selected video contains no usable audio')
 if duration < candidate_min:
  return {'start':0.0,'end':round(duration,3),'duration':round(duration,3),'score':1.0,'lyrics_source':'none','reason':'source shorter than minimum candidate duration'}
 hop=512
 rms=librosa.feature.rms(y=y,hop_length=hop)[0]
 onset=librosa.onset.onset_strength(y=y,sr=sr,hop_length=hop)
 mfcc=librosa.feature.mfcc(y=y,sr=sr,n_mfcc=20,hop_length=hop)
 times=librosa.frames_to_time(np.arange(len(rms)),sr=sr,hop_length=hop)
 tempo,beats=librosa.beat.beat_track(y=y,sr=sr,hop_length=hop,units='time')
 tempo=float(np.asarray(tempo).reshape(-1)[0]) if np.size(tempo) else 0.0
 source='none'; lines=[]
 if youtube_lrc and Path(youtube_lrc).is_file():
  source='youtube'; lines=parse_lrc(youtube_lrc)
 elif spotify_lrc and Path(spotify_lrc).is_file() and sync:
  source='spotify_synchronized'; offset=float(sync.get('offset_seconds',0))
  # synchronize() defines offset as: YouTube time = Spotify time + offset.
  # Therefore Spotify LRC timestamps must be shifted by +offset into the
  # YouTube timeline before they are used for hook scoring.
  lines=[{'time':max(0,x['time']+offset),'text':x['text']} for x in parse_lrc(spotify_lrc)]
 lengths=np.arange(candidate_min,min(candidate_max,duration)+.001,float(cfg.get('hook_candidate_length_step_seconds',5)))
 starts=np.arange(0,max(.01,duration-candidate_min),float(cfg.get('hook_candidate_start_step_seconds',1)))
 global_level=float(np.mean(rms)); silence_threshold=max(global_level*0.28,1e-5)
 raw=[]
 for L in lengths:
  for st in starts:
   en=st+L
   if en>duration: continue
   a=int(np.searchsorted(times,st)); b=min(len(rms),int(np.searchsorted(times,en)))
   if b-a<20: continue
   r=rms[a:b]; o=onset[a:b]; m=mfcc[:,a:b]; third=max(1,len(r)//3)
   energy=float(np.mean(r)); peak=float(np.percentile(r,90)); activity=float(np.mean(o))
   buildup=float(np.mean(r[-third:])-np.mean(r[:third])); dynamic=float(np.std(r))
   beat_density=float(np.sum((beats>=st)&(beats<=en))/max(L,1))
   half=max(1,m.shape[1]//2); v1=np.mean(m[:,:half],axis=1); v2=np.mean(m[:,-half:],axis=1)
   coherence=float(np.dot(v1,v2)/(np.linalg.norm(v1)*np.linalg.norm(v2)+1e-9))
   # Repetition/coherence: compare the candidate's coarse MFCC sequence with other song regions.
   bins=24; target=np.asarray([np.mean(m[:,i*len(m[0])//bins:max((i+1)*len(m[0])//bins,i*len(m[0])//bins+1)],axis=1) for i in range(bins)])
   repeat_scores=[]; global_step=max(1,int(5*sr/hop)); half_frames=max(20,m.shape[1])
   for aa in range(0,max(1,len(mfcc[0])-half_frames+1),global_step):
    region=mfcc[:,aa:aa+half_frames]
    if aa>=a and aa<b: continue
    if region.shape[1]<max(20,half_frames*0.8): continue
    rbins=24; other=np.asarray([np.mean(region[:,j*region.shape[1]//rbins:max((j+1)*region.shape[1]//rbins,j*region.shape[1]//rbins+1)],axis=1) for j in range(rbins)])
    ta=target.reshape(-1); tb=other.reshape(-1)
    if np.std(ta)>1e-9 and np.std(tb)>1e-9: repeat_scores.append(float(np.corrcoef(ta,tb)[0,1]))
   repeat=max(repeat_scores or [0.0])
   rr=z(r); acs=[]
   for k in range(max(2,len(rr)//8),max(3,len(rr)//2),max(1,len(rr)//20)):
    if len(rr)>k+5: acs.append(float(np.corrcoef(rr[:-k],rr[k:])[0,1]))
   internal_repeat=max(acs or [0.0]); repeat=max(repeat,internal_repeat)
   tail=float(np.mean(r[-max(4,int(3*sr/hop)):]))
   clean_end=1-min(1,abs(tail/(np.mean(r)+1e-9)-0.8))
   silence_ratio=float(np.mean(r<silence_threshold))
   # Boundary activity: prefer candidates that do not begin/end in dead air.
   boundary=max(0.0,min(1.0,float(np.mean(r[:max(4,int(1*sr/hop))]))/(energy+1e-9)))
   boundary=min(boundary,float(np.mean(r[-max(4,int(1*sr/hop)):]))/(energy+1e-9))
   ly=lyric_stats(lines,st,en) if lines else {'density':0,'repeated_lines':0,'line_count':0,'completeness':0}
   duration_bonus=1.0 if pmin<=L<=pmax else 0.70
   raw.append([st,en,L,energy,peak,activity,buildup,dynamic,beat_density,coherence,repeat,clean_end,duration_bonus,ly['density'],ly['repeated_lines'],ly['completeness'],silence_ratio,boundary])
 if not raw: raise RuntimeError('No hook candidates generated')
 m=np.asarray(raw,float)
 for c in [3,4,5,6,7,8,9,10,11,13,14,15,16,17]: m[:,c]=z(m[:,c])
 if lines:
  score=(.17*m[:,3]+.10*m[:,4]+.15*m[:,5]+.09*m[:,6]+.06*m[:,7]+.07*m[:,8]+.11*m[:,9]+.11*m[:,10]+.05*m[:,11]+.05*m[:,13]+.09*m[:,14]+.04*m[:,15]+.05*m[:,12]+.06*m[:,17]-.09*m[:,16])
 else:
  score=(.21*m[:,3]+.12*m[:,4]+.18*m[:,5]+.11*m[:,6]+.07*m[:,7]+.09*m[:,8]+.12*m[:,9]+.12*m[:,10]+.06*m[:,11]+.06*m[:,12]+.06*m[:,17]-.10*m[:,16])
 i=int(np.argmax(score)); st,en,L=m[i,:3]; boundary_start=st
 if len(beats):
  bs=float(beats[np.argmin(abs(beats-st))]); be=float(beats[np.argmin(abs(beats-en))])
  if candidate_min<=be-bs<=candidate_max: st,en,L=bs,be,be-bs
 # Search slightly before the structural boundary for an engaging lead-in; do not force a fixed offset.
 leadmin=float(cfg.get('hook_leadin_min_seconds',.75)); leadmax=min(float(cfg.get('hook_leadin_max_seconds',3)),st); step=float(cfg.get('hook_leadin_search_step_seconds',.25)); best=st; bestv=-1e9
 for d in np.arange(leadmin,leadmax+1e-6,step):
  ss=max(0,st-d); a=int(np.searchsorted(times,ss)); b=int(np.searchsorted(times,st))
  if b-a<5: continue
  v=float(np.mean(rms[a:b])+.35*np.mean(onset[a:b]))
  if v>bestv: bestv=v; best=ss
 final_start=best; final_end=en
 if final_end-final_start>candidate_max: final_start=max(0,final_end-candidate_max)
 return {'start':round(float(final_start),3),'end':round(float(final_end),3),'duration':round(float(final_end-final_start),3),'score':round(float(score[i]),4),'tempo_bpm':round(tempo,2),'candidates_evaluated':len(m),'candidate_spacing_seconds':float(cfg.get('hook_candidate_start_step_seconds',1)),'candidate_length_step_seconds':float(cfg.get('hook_candidate_length_step_seconds',5)),'candidate_absolute_min_seconds':candidate_min,'candidate_absolute_max_seconds':candidate_max,'preferred_range_seconds':[pmin,pmax],'beat_aligned':bool(len(beats)),'lead_in_seconds':round(float(boundary_start-final_start),3),'lyrics_source':source,'lyrics_lines_considered':len(lines),'lyrics_used_for_scoring':bool(lines),'reason':'whole-song candidate scoring with musical strength, rhythm, build-up, dynamics, beat density, musical recurrence/coherence, lyrics when available, boundary quality, preferred duration and silence penalties'}
