from __future__ import annotations
import itertools
import numpy as np
from .utils import json_dump

class HookCandidateGenerator:
    def __init__(self,cfg,work_dir,logger): self.cfg=cfg; self.work=work_dir; self.logger=logger
    def _window_candidates(self,start_ms,end_ms,durations):
        center=(start_ms+end_ms)//2; out=[]
        for d in durations:
            st=max(0,center-d//2); en=st+d
            out.append((st,en))
        return out
    def generate(self,words,phrases,structure,acoustic)->list[dict]:
        dur=acoustic['duration_ms']; min_d=self.cfg.get('hook_selection.core_min_ms',10000); max_d=self.cfg.get('hook_selection.core_max_ms',35000); durations=[x*1000 for x in (10,12,14,16,18,20,22,24,26,28,30,32,35) if min_d<=x*1000<=max_d]
        anchors=[]
        # repeated phrase occurrences
        for p in phrases:
            if p.get('occurrence_count',0)>=2:
                for o in p.get('occurrences',[]):
                    st=int(o.get('start_ms',0)); en=int(o.get('end_ms',st+8000)); anchors.append((st,en,'REPEATED_PHRASE',p.get('cluster_id')))
        # structural regions
        for r in structure.get('regions',[]): anchors.append((r['start_ms'],r['end_ms'],r['type'],r.get('family')))
        # energy/vocal peaks as seed anchors
        mix=acoustic['features'].get('mix',[]); vocal=acoustic['features'].get('vocals',[]); times=acoustic['time_ms'];
        for arr,typ in ((vocal,'VOCAL_PEAK'),(mix,'ENERGY_PEAK')):
            if arr:
                idx=np.argsort(np.asarray(arr))[-min(12,len(arr)):]
                for i in idx: anchors.append((max(0,int(times[i])-5000),min(dur,int(times[i])+5000),typ,None))
        # broad sliding candidates at 2s for representative durations.
        step=2000
        for d in durations[::max(1,len(durations)//6)]:
            for st in range(0,max(1,dur-d+1),step): anchors.append((st,st+d,'SLIDING',None))
        candidates=[]; seen=set()
        for a,b,typ,fam in anchors:
            for st,en in self._window_candidates(a,b,durations):
                en=min(dur,en); st=max(0,en-(en-st))
                key=(st,en)
                if en-st<min_d or key in seen: continue
                seen.add(key)
                words_in=[w for w in words if w['end_ms']>st and w['start_ms']<en]
                candidates.append({'candidate_id':f'c{len(candidates):05d}','core_start_ms':st,'core_end_ms':en,'type_hint':typ,'family_seed':fam,'words':words_in})
        json_dump(self.work/'analysis'/'hook_candidates.json',{'count_raw':len(candidates),'candidates':candidates})
        return candidates
