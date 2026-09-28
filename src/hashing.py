from pathlib import Path
from .utils import sha256_file

def hash_package(mp3:Path,lrc:Path,json_path:Path)->dict:
    return {
        'mp3_sha256':sha256_file(mp3),'lrc_sha256':sha256_file(lrc),'json_sha256':sha256_file(json_path),
        'mp3_size':mp3.stat().st_size,'lrc_size':lrc.stat().st_size,'json_size':json_path.stat().st_size,
        'mp3_mtime':mp3.stat().st_mtime,'lrc_mtime':lrc.stat().st_mtime,'json_mtime':json_path.stat().st_mtime,
    }
