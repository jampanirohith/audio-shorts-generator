from __future__ import annotations
import os, shutil
from pathlib import Path
from .utils import Phase3Error, run_cmd
from .audio_io import probe

class StemIsolator:
    def __init__(self,cfg,work_dir:Path,logger): self.cfg=cfg; self.work_dir=work_dir; self.logger=logger
    def run(self,source:Path)->dict:
        stems=self.work_dir/'stems'; stems.mkdir(parents=True,exist_ok=True)
        expected={k:stems/f'{k}.wav' for k in ('vocals','drums','bass','other')}
        if all(p.exists() for p in expected.values()): return {k:str(v) for k,v in expected.items()}
        model=self.cfg.get('demucs.model','htdemucs'); requested=self.cfg.get('demucs.device','cuda')
        device=requested
        if device=='cuda':
            try:
                import torch
                if not torch.cuda.is_available(): device='cpu'
            except Exception: device='cpu'
        tmp=self.work_dir/'demucs_raw'; tmp.mkdir(exist_ok=True)
        cmd=['python','-m','demucs.separate','-n',model,'-o',str(tmp),'--float32']
        if device=='cpu': cmd.append('--device'); cmd.append('cpu')
        else: cmd += ['-d',device]
        cmd.append(str(source))
        try:
            run_cmd(cmd,timeout=7200)
        except Phase3Error as e:
            if 'out of memory' in str(e).lower() and device=='cuda' and self.cfg.get('demucs.fallback_to_cpu',True):
                self.logger.warning('Demucs CUDA OOM/failure; retrying CPU')
                run_cmd(['python','-m','demucs.separate','-n',model,'-o',str(tmp),'--float32','-d','cpu',str(source)],timeout=7200)
                device='cpu'
            else: raise Phase3Error('DEMUCS_FAILED',str(e),details=e.details)
        # Demucs output: model/basename/*.wav
        candidates=list(tmp.rglob('*.wav'))
        for key,dst in expected.items():
            src=next((p for p in candidates if p.stem.lower()==key),None)
            if src is None: raise Phase3Error('DEMUCS_FAILED',f'Missing stem {key}')
            shutil.copy2(src,dst)
        self.logger.info('Demucs complete on %s',device)
        return {k:str(v) for k,v in expected.items()} | {'device':device,'model':model}
