

## Current output design

# Set-Up

## Setting Up Environment
```bash
python -m venv venv 
venv\Scripts\activate
```


## Checking FFmpeg
You also need **ffmpeg** on your PATH (not pip-installable):
- Windows: download from ffmpeg.org, add the `bin` folder to PATH
- Ubuntu: `sudo apt install ffmpeg`
- Mac: `brew install ffmpeg`
```bash
ffmpeg -version
ffprobe -version
```


## Install Packages
```bash
pip install -r requirements.txt
```



## Project layout

```
main.py                  pipeline entrypoint (ingest / process / publish / review)
demo.py                  hear the 8D engine on a generated test loop
config.yaml              paths, segment/scoring settings, 8D profile default, publishing config
requirements.txt

modules/
  database.py             SQLite wrapper (songs, segments, publish_log)
  ingest.py                reads audio/input/manifest.csv, no scraping
  audio_features.py        the AudioFeatures data shape (no heavy deps)
  audio_analyzer.py        BPM/beat/energy/chorus detection (needs librosa)
  segment_selector.py      scores candidate windows, picks the best one
  eightd_engine.py         the spatial audio DSP -- the technical core
  lyrics_engine.py         .lrc parsing, hook scoring, karaoke .ass generation
  video_generator.py       ffmpeg vertical video assembly
  publisher.py             YouTube (real OAuth flow) / Instagram / Facebook uploads

database/schema.sql
audio/input/manifest.csv   <- put your rights-cleared tracks here
tests/test_eightd_engine.py
```