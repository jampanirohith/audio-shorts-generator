#!/usr/bin/env python3
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.config import Config
from src.scanner import scan_packages
from src.package_validator import validate_package

root=Path(__file__).resolve().parents[1]
cfg=Config.load(root/'config.json')
pkgs=scan_packages(cfg.input_dir)
if not pkgs:
    print('No packages in songs/final')
    raise SystemExit(1)
for pkg in pkgs:
    m=validate_package(pkg,cfg)
    print(pkg.basename)
    print('  words:',len(m['words']))
    print('  youtube_video_id:',m['youtube_video_id'])
