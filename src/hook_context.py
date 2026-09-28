from __future__ import annotations
import numpy as np
from .utils import clamp
from .audio_io import decode_wav

class HookContextOptimizer:
    def __init__(self,cfg,work_dir,logger): self.cfg=cfg; self.work=work_dir; self.logger=logger
    def _energy(self,arr,times,st,en):
        if not arr:return 0
        idx=(np.asarray(times)>=st)&(np.asarray(times)<en); a=np.asarray(arr)[idx]; return float(a.mean()) if len(a) else 0
    def expand(self,candidates,words,acoustic,structure):
        times=acoustic['time_ms']; mix=acoustic['features'].get('mix',[]); drums=acoustic['features'].get('drums',[]); voc=acoustic['features'].get('vocals',[]); duration=acoustic['duration_ms']
        lead_vals=[500,1000,1500,2000,2500,3000,3500,4000,5000]
        tail_vals=[0,500,1000,1500,2000,3000,4000,5000]
        max_reel_ms=int(self.cfg.get('hook_selection.final_max_ms',40000))
        cw=self.cfg.get('hook_selection.context_weights',{})
        out=[]
        for c in candidates:
            st,en=c['core_start_ms'],c['core_end_ms']; best=None
            for lead in lead_vals:
                reel_st=max(0,st-lead)
                build=self._energy(mix,times,reel_st,st)/(self._energy(mix,times,st,en)+1e-6)
                drum=self._energy(drums,times,reel_st,st); voc_pre=self._energy(voc,times,reel_st,st)
                # Reward rising setup but avoid silent lead-ins.
                rise=clamp((self._energy(mix,times,reel_st,st)-self._energy(mix,times,max(reel_st,st-500),st))/(self._energy(mix,times,st,en)+1e-6)+0.5,0,1) if st>500 else 0.5
                lead_score=0.4*clamp(build,0,1)+0.25*clamp(drum/(build+1e-6),0,1)*0.5+0.35*rise
                for tail in tail_vals:
                    reel_en=min(duration,en+tail)
                    if reel_en-reel_st > max_reel_ms:
                        continue
                    tail_energy=self._energy(mix,times,en,reel_en)
                    # ending quality: reward some residual energy but not long silence.
                    endq=clamp(tail_energy/(self._energy(mix,times,st,en)+1e-6)*1.3,0,1) if tail else 0.5
                    # lyric continuity around boundaries.
                    starts=sum(1 for w in words if reel_st<=w['start_ms']<st+500)
                    ends=sum(1 for w in words if en-500<=w['end_ms']<=reel_en)
                    continuity=clamp((starts+ends)/3,0,1)
                    music_cont=clamp((tail_energy+build)/(self._energy(mix,times,st,en)+1e-6)*0.5,0,1)
                    ctx=(cw.get('lead_in_buildup',.35)*lead_score + cw.get('hook_entry_cleanliness',.25)*0.95 + cw.get('ending_quality',.2)*endq + cw.get('lyric_continuity',.1)*continuity + cw.get('musical_continuity',.1)*music_cont)
                    if best is None or ctx>best['context_score']:
                        best={'lead_in_ms':lead,'tail_ms':tail,'reel_start_ms':reel_st,'reel_end_ms':reel_en,'context_score':float(ctx)}
            if best is None:
                # Keep the candidate rather than dropping it silently; trim the
                # context to the hard Reel limit while preserving the core.
                reel_st=max(0,st-500)
                reel_en=min(duration, reel_st+max_reel_ms, en+max(0,max_reel_ms-(st-reel_st)))
                best={'lead_in_ms':st-reel_st,'tail_ms':max(0,reel_en-en),'reel_start_ms':reel_st,'reel_end_ms':reel_en,'context_score':0.0}
            c.update(best); c['final_score']=0.75*c['core_score']+0.25*c['context_score']; out.append(c)
        out.sort(key=lambda x:x['final_score'],reverse=True)
        return out
