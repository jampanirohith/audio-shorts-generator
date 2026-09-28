from __future__ import annotations
import shutil
from pathlib import Path
from .utils import now_iso

class Recovery:
    def __init__(self,cfg,db,logger): self.cfg=cfg; self.db=db; self.logger=logger
    def repair(self):
        fixed=[]
        outdir=self.cfg.output_dir
        outdir.mkdir(parents=True,exist_ok=True)
        for mp4 in outdir.glob('*_reel.mp4'):
            basename=mp4.name[:-9]
            js=outdir/f'{basename}_reel.json'
            if js.exists():
                row=self.db.get_job(basename)
                if row and row['status']!='finalized':
                    self.db.set_stage(basename,'finalized','finalized')
                    fixed.append(basename)
        return fixed
    def clean_temp(self):
        root=self.cfg.temp_dir; removed=0
        if not root.exists(): return 0
        for p in root.iterdir():
            if p.is_dir(): shutil.rmtree(p,ignore_errors=True); removed+=1
            else: p.unlink(missing_ok=True); removed+=1
        return removed
