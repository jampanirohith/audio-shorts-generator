from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from .utils import stable_json_hash

@dataclass
class Config:
    root: Path
    data: dict
    config_hash: str
    
    @classmethod
    def load(cls, path: str|Path='config.json', root: Path|None=None):
        p=Path(path).resolve(); data=json.loads(p.read_text(encoding='utf-8')); root=(root or p.parent).resolve()
        return cls(root=root,data=data,config_hash=stable_json_hash(data))
    def get(self, key: str, default=None):
        cur=self.data
        for part in key.split('.'):
            if not isinstance(cur,dict) or part not in cur: return default
            cur=cur[part]
        return cur
    def path(self, key: str) -> Path: return (self.root/self.get(key)).resolve()
    @property
    def input_dir(self)->Path: return self.path('paths.input_dir')
    @property
    def output_dir(self)->Path: return self.path('paths.output_dir')
    @property
    def temp_dir(self)->Path: return self.path('paths.temp_dir')
    @property
    def db_path(self)->Path: return self.path('paths.db_path')
    @property
    def logs_dir(self)->Path: return self.path('paths.logs_dir')
    @property
    def fonts_dir(self)->Path: return self.path('paths.fonts_dir')
