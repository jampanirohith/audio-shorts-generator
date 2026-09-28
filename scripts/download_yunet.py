#!/usr/bin/env python3
from pathlib import Path
import requests

URLS = [
    'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx',
    'https://github.com/opencv/opencv_zoo/raw/refs/heads/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx',
]

root = Path(__file__).resolve().parents[1]
out = root / 'assets' / 'models' / 'face_detection_yunet_2023mar.onnx'
out.parent.mkdir(parents=True, exist_ok=True)

if out.exists() and out.stat().st_size > 50000:
    print(f'YuNet already present: {out}')
    raise SystemExit(0)

for url in URLS:
    try:
        print(f'Downloading YuNet from {url}')
        with requests.get(url, timeout=60, stream=True) as r:
            r.raise_for_status()
            tmp = out.with_suffix('.download')
            total = 0
            with tmp.open('wb') as f:
                for chunk in r.iter_content(1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        total += len(chunk)
            if total <= 50000:
                raise RuntimeError('download was too small; likely a Git-LFS pointer')
            tmp.replace(out)
            print(f'Installed: {out} ({total} bytes)')
            raise SystemExit(0)
    except Exception as e:
        print(f'Failed: {e}')

raise SystemExit('Unable to download YuNet. The pipeline can still run using fallback detectors.')
