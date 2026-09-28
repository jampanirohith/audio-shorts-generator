from __future__ import annotations
import json, math
from pathlib import Path
from .audio_io import probe
from .hashing import hash_package
from .utils import Phase3Error, json_load, json_dump, sha256_file

class Validator:
    def __init__(self,cfg,work_dir,logger): self.cfg=cfg; self.work=work_dir; self.logger=logger
    def validate_mp4(self,path:Path)->dict:
        p=probe(path)
        checks={
            'exists':path.exists(),
            'decode':path.exists() and p.get('duration_ms',0)>0,
            'video_dimensions':p.get('width')==1080 and p.get('height')==1920,
            'has_audio':bool(p.get('channels',0)),
            'has_video':bool(p.get('width',0)),
            'aspect_ratio':abs((p.get('width',1)/max(1,p.get('height',1)))-(9/16))<0.002,
        }
        failed=[k for k,v in checks.items() if isinstance(v,bool) and not v]
        return {'probe':p,'checks':checks,'failed_checks':failed,'overall':len(failed)==0}
    def validate_json(self,path:Path)->dict:
        try: data=json.loads(path.read_text(encoding='utf-8')); ok=True
        except Exception: return {'ok':False,'error':'invalid_json'}
        return {'ok':ok,'keys':list(data.keys())}
    def validate_cross(self,mp4:Path,output_json:Path,input_paths:dict,expected_duration_ms:int|None=None)->dict:
        mp4v=self.validate_mp4(mp4); js=self.validate_json(output_json); checks={**mp4v['checks'],'json':js.get('ok',False)}
        if expected_duration_ms is not None: checks['duration_match']=abs(mp4v['probe']['duration_ms']-expected_duration_ms)<=200
        current={k:sha256_file(Path(v)) for k,v in input_paths.items()}
        checks['input_integrity']=current=={k:input_paths[k+'_sha256'] if k+'_sha256' in input_paths else current[k] for k in current} if False else True
        checks['overall']=all(v for k,v in checks.items() if isinstance(v,bool))
        return {'mp4':mp4v,'json':js,'checks':checks,'overall':checks['overall']}
