#!/usr/bin/env python3
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.font_manager import ensure_telugu_font

root=Path(__file__).resolve().parents[1]
path=ensure_telugu_font(root/'assets/fonts')
print(path)
