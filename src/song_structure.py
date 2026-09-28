from __future__ import annotations
from collections import defaultdict
from .utils import json_dump

class SongStructureDetector:
    def __init__(self,work_dir,logger): self.work=work_dir; self.logger=logger
    def discover(self,words,lyrics,phrases,acoustic):
        duration=acoustic['duration_ms']; features=acoustic['features'];
        vocal=features.get('vocals') or [0]*len(acoustic['time_ms']); onset=acoustic.get('onset_strength') or [0]*len(acoustic['time_ms'])
        regions=[]
        # Repeated phrase regions are the most reliable section seeds.
        for c in phrases:
            occ=c.get('occurrences',[])
            for n,o in enumerate(occ):
                if 'start_ms' in o:
                    st=int(o['start_ms']); en=int(o.get('end_ms',st+10000));
                    typ='CHORUS' if c.get('n') in ('line','similar_line') or c.get('occurrence_count',0)>=3 else 'REFRAIN'
                    regions.append({'start_ms':st,'end_ms':min(duration,en),'type':typ,'confidence':min(1,0.55+0.08*c.get('occurrence_count',1)),'family':c['cluster_id']})
        # Vocal peaks -> vocal highlight candidates.
        if vocal:
            arr=list(vocal); med=sorted(arr)[len(arr)//2];
            for i,v in enumerate(arr):
                if v>=med*1.6:
                    st=max(0,int(acoustic['time_ms'][i])-8000); en=min(duration,int(acoustic['time_ms'][i])+8000)
                    regions.append({'start_ms':st,'end_ms':en,'type':'VOCAL_HIGHLIGHT','confidence':0.65,'family':None})
        # Merge overlapping exact-ish regions.
        regions=sorted(regions,key=lambda x:(x['start_ms'],x['end_ms']))
        merged=[]
        for r in regions:
            if merged and r['start_ms']<=merged[-1]['end_ms'] and r['type']==merged[-1]['type']:
                merged[-1]['end_ms']=max(merged[-1]['end_ms'],r['end_ms']); merged[-1]['confidence']=max(merged[-1]['confidence'],r['confidence'])
            else: merged.append(dict(r))
        # Final occurrence heuristic.
        if merged:
            latest=max(merged,key=lambda x:x['end_ms'])
            if latest['type'] in ('CHORUS','REFRAIN'): latest=dict(latest); latest['type']='FINAL_CHORUS'
        result={'duration_ms':duration,'regions':merged}
        json_dump(self.work/'analysis'/'song_structure.json',result); return result
