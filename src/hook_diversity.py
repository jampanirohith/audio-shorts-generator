from __future__ import annotations
from difflib import SequenceMatcher
from .utils import json_dump

def _overlap(a,b):
    s=max(a['core_start_ms'],b['core_start_ms']); e=min(a['core_end_ms'],b['core_end_ms']); inter=max(0,e-s)
    shorter=min(a['core_end_ms']-a['core_start_ms'],b['core_end_ms']-b['core_start_ms'])
    return inter/max(1,shorter)

def _lyrics_sim(a,b):
    ta=' '.join(w.get('normalized','') for w in a.get('words',[])); tb=' '.join(w.get('normalized','') for w in b.get('words',[]))
    return SequenceMatcher(None,ta,tb).ratio()

class HookDiversity:
    def __init__(self,cfg,work_dir,logger): self.cfg=cfg; self.work=work_dir; self.logger=logger
    def select(self,candidates):
        overlap_thr=float(self.cfg.get('hook_selection.same_family_overlap_ratio',0.5)); sim_thr=float(self.cfg.get('hook_selection.same_family_lyric_similarity',0.8))
        families=[]; reps=[]
        for c in candidates:
            family=None
            for fi,rep in enumerate(reps):
                if _overlap(c,rep)>=overlap_thr or _lyrics_sim(c,rep)>=sim_thr:
                    family=fi; break
            if family is None:
                reps.append(c); family=len(reps)-1
            families.append(family)
            c['family_id']=family
        # Keep best per family, then diversify by time; allow different repeated occurrences.
        best=[]; seenfam=set()
        for c in candidates:
            if c['family_id'] not in seenfam:
                best.append(c); seenfam.add(c['family_id'])
        # ensure distinct temporal buckets and enough finalists.
        best.sort(key=lambda x:x['core_score'],reverse=True)
        nmin=int(self.cfg.get('hook_selection.finalist_count_min',10)); nmax=int(self.cfg.get('hook_selection.finalist_count_max',15))
        finalists=[]
        for c in best:
            too_close=False
            for f in finalists:
                ov=_overlap(c,f)
                if ov>=0.35: too_close=True; break
                # same exact family representative already handled.
            if too_close: continue
            finalists.append(c)
            if len(finalists)>=nmax: break
        if len(finalists)<nmin:
            for c in best:
                if c not in finalists:
                    finalists.append(c)
                    if len(finalists)>=nmin: break
        for i,c in enumerate(finalists,1): c['rank_pre_context']=i
        json_dump(self.work/'analysis'/'finalists.json',{'count':len(finalists),'finalists':finalists,'family_count':len(reps)})
        return finalists,len(reps)
