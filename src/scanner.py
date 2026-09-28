from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from .utils import Phase3Error

@dataclass
class SongPackage:
    basename:str
    mp3:Path
    lrc:Path
    json:Path

def scan_packages(input_dir:Path, recursive:bool=False)->list[SongPackage]:
    input_dir.mkdir(parents=True,exist_ok=True)
    mp3s=sorted(input_dir.rglob('*.mp3') if recursive else input_dir.glob('*.mp3'))
    seen={}; out=[]
    for mp3 in mp3s:
        b=mp3.stem
        if b in seen: raise Phase3Error('INPUT_BASENAME_COLLISION',f'Duplicate basename: {b}')
        lrc=mp3.with_suffix('.lrc'); js=mp3.with_suffix('.json');
        seen[b]=mp3
        out.append(SongPackage(b,mp3,lrc,js))
    return out

def find_package(input_dir:Path, basename:str)->SongPackage:
    mp3=input_dir/f'{basename}.mp3'; lrc=input_dir/f'{basename}.lrc'; js=input_dir/f'{basename}.json'
    return SongPackage(basename,mp3,lrc,js)
