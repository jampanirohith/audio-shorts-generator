from __future__ import annotations
from .utils import json_dump, Phase3Error
from .hook_candidates import HookCandidateGenerator
from .hook_scorer import HookScorer
from .hook_diversity import HookDiversity
from .hook_context import HookContextOptimizer

class HookSelector:
    def __init__(self,cfg,work_dir,logger): self.cfg=cfg; self.work=work_dir; self.logger=logger
    def automatic(self,words,phrases,structure,acoustic)->dict:
        raw=HookCandidateGenerator(self.cfg,self.work,self.logger).generate(words,phrases,structure,acoustic)
        if not raw: raise Phase3Error('HOOK_NO_CANDIDATES','No hook candidates generated')
        scored=HookScorer(self.cfg,self.work,self.logger).score(raw,words,acoustic,phrases,structure)
        finalists,family_count=HookDiversity(self.cfg,self.work,self.logger).select(scored)
        if len(finalists)<int(self.cfg.get('hook_selection.finalist_count_min',10)) and len(scored)>=int(self.cfg.get('hook_selection.finalist_count_min',10)):
            raise Phase3Error('HOOK_INSUFFICIENT_FINALISTS',f'Only {len(finalists)} distinct finalists generated')
        expanded=HookContextOptimizer(self.cfg,self.work,self.logger).expand(finalists,words,acoustic,structure)
        max_reel_ms=int(self.cfg.get('hook_selection.final_max_ms',40000))
        expanded=[c for c in expanded if 0 < int(c['reel_end_ms'])-int(c['reel_start_ms']) <= max_reel_ms]
        if not expanded:
            raise Phase3Error('HOOK_SELECTION_FAILED','No hook context fits the configured maximum Reel duration')
        selected=expanded[0]
        return {'mode':'automatic','candidate_count_raw':len(raw),'candidate_count_after_filter':len(scored),'hook_family_count':family_count,'finalist_count':len(expanded),'selected':{k:selected[k] for k in ('core_start_ms','core_end_ms','reel_start_ms','reel_end_ms','lead_in_ms','tail_ms','core_score','context_score','final_score','type_hint')},'candidates':expanded}
    def manual(self,start_ms,end_ms,duration_ms)->dict:
        max_reel_ms=int(self.cfg.get('hook_selection.final_max_ms',40000))
        if start_ms<0 or end_ms<=start_ms or end_ms>duration_ms: raise Phase3Error('HOOK_SELECTION_FAILED','Manual hook is outside source duration')
        if end_ms-start_ms>max_reel_ms: raise Phase3Error('HOOK_SELECTION_FAILED',f'Manual hook exceeds maximum Reel duration of {max_reel_ms/1000:.0f} seconds')
        return {'mode':'manual','manual':{'start_ms':int(start_ms),'end_ms':int(end_ms),'duration_ms':int(end_ms-start_ms)},'selected':{'core_start_ms':int(start_ms),'core_end_ms':int(end_ms),'reel_start_ms':int(start_ms),'reel_end_ms':int(end_ms),'lead_in_ms':0,'tail_ms':0,'core_score':1.0,'context_score':1.0,'final_score':1.0,'type_hint':'MANUAL'}}
    
