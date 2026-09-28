from __future__ import annotations
import numpy as np
from .utils import percentile_ranks, clamp, json_dump

class HookScorer:
    def __init__(self,cfg,work_dir,logger): self.cfg=cfg; self.work=work_dir; self.logger=logger
    @staticmethod
    def _mean_segment(arr,times,st,en):
        if not arr: return 0.0
        idx=(np.asarray(times)>=st)&(np.asarray(times)<en)
        vals=np.asarray(arr,dtype=float)[idx]
        return float(np.mean(vals)) if len(vals) else 0.0
    def score(self,candidates,words,acoustic,phrases,structure):
        times=acoustic['time_ms']; feats=acoustic['features']; dur=acoustic['duration_ms']
        # Repetition phrase overlap counts.
        phrase_occ_by_candidate=[]
        for c in candidates:
            st,en=c['core_start_ms'],c['core_end_ms']; score_rep=0; phrase_count=0
            for p in phrases:
                occ=sum(1 for o in p.get('occurrences',[]) if o.get('start_ms',1e18)<en and o.get('end_ms',-1)>st)
                if occ:
                    phrase_count+=1; score_rep+=min(1.0,p.get('occurrence_count',1)/4.0)*min(1.0,p.get('similarity_score',1.0))
            phrase_occ_by_candidate.append((phrase_count,score_rep))
        raw={k:[] for k in ['lyric','vocal','repetition','music','arrangement','contour','complete','timing']}
        for i,c in enumerate(candidates):
            st,en=c['core_start_ms'],c['core_end_ms']; ws=[w for w in words if w['end_ms']>st and w['start_ms']<en]
            dur_s=max(0.1,(en-st)/1000); wps=len(ws)/dur_s
            lyric_density=min(1,wps/4)
            if ws:
                completeness=sum(1 for w in ws if w['start_ms']>=st and w['end_ms']<=en)/len(ws)
                timing=np.mean([float(w.get('score') or 0.8) for w in ws]);
            else: completeness=0; timing=0
            voc=self._mean_segment(feats.get('vocals',[]),times,st,en); drums=self._mean_segment(feats.get('drums',[]),times,st,en); bass=self._mean_segment(feats.get('bass',[]),times,st,en); other=self._mean_segment(feats.get('other',[]),times,st,en); mix=self._mean_segment(feats.get('mix',[]),times,st,en)
            if en-st>=1000:
                half=(st+en)//2; a=self._mean_segment(feats.get('mix',[]),times,st,half); b=self._mean_segment(feats.get('mix',[]),times,half,en); contour=clamp(abs(b-a)/(mix+1e-6)*2,0,1)
            else: contour=0
            raw['lyric'].append(0.7*min(1,lyric_density)+0.3*(1 if len(ws)>=4 else len(ws)/4))
            raw['vocal'].append(voc/(mix+1e-6))
            raw['repetition'].append(phrase_occ_by_candidate[i][1])
            raw['music'].append((drums+0.5*bass+other)/(mix+1e-6))
            raw['arrangement'].append((voc+drums+bass+other)/(mix+1e-6))
            raw['contour'].append(contour)
            raw['complete'].append(completeness)
            raw['timing'].append(timing)
        norm={k:percentile_ranks(v) for k,v in raw.items()}
        weights=self.cfg.get('hook_selection.weights',{})
        for i,c in enumerate(candidates):
            c['features']={
              'lyric_memorability':norm['lyric'][i], 'vocal_quality':norm['vocal'][i], 'repetition_strength':norm['repetition'][i],
              'musical_energy':norm['music'][i], 'arrangement_richness':norm['arrangement'][i], 'energy_contour':norm['contour'][i],
              'phrase_completeness':norm['complete'][i], 'timing_quality':norm['timing'][i]
            }
            # Hard filter-ish penalties.
            lyric_ok=(len(c['words'])>=2); instrumental_share=max(0,1-norm['vocal'][i])
            penalty=1.0
            if not lyric_ok: penalty*=0.35
            if instrumental_share>0.95: penalty*=0.4
            c['hard_penalty']=penalty
            c['core_score']=float(sum(weights.get(k,0)*c['features'].get(k,0) for k in weights)*penalty)
            hint=c.get('type_hint','')
            if hint in set(self.cfg.get('hook_selection.preferred_core_types',[])): c['core_score']*=1.03
        candidates=[c for c in candidates if c['hard_penalty']>0]
        candidates.sort(key=lambda x:x['core_score'],reverse=True)
        json_dump(self.work/'analysis'/'hook_rankings.json',{'count_after_filter':len(candidates),'candidates':candidates})
        return candidates
