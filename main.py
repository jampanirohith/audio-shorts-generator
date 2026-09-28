#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, logging, shutil, importlib.util
from pathlib import Path
from src.config import Config
from src.pipeline import Pipeline
from src.scanner import scan_packages
from src.hook_plan import HookPlan
from src.db import DB
from src.recovery import Recovery
from src.validator import Validator
from src.utils import Phase3Error, fmt_ms, ffmpeg_has_encoder


def doctor(cfg):
    checks={name:shutil.which(name) is not None for name in ('ffmpeg','ffprobe','yt-dlp')}
    checks['torch']=importlib.util.find_spec('torch') is not None
    checks['demucs']=importlib.util.find_spec('demucs') is not None
    checks['h264_nvenc']=bool(shutil.which('ffmpeg')) and ffmpeg_has_encoder('h264_nvenc')
    try:
        import torch; checks['cuda_available']=bool(torch.cuda.is_available())
    except Exception: checks['cuda_available']=False
    checks['hook_timeline_json']=(cfg.root/'hook_timeline.json').exists()
    cfg.input_dir.mkdir(parents=True,exist_ok=True); cfg.output_dir.mkdir(parents=True,exist_ok=True); cfg.temp_dir.mkdir(parents=True,exist_ok=True); cfg.logs_dir.mkdir(parents=True,exist_ok=True)
    for k,v in checks.items(): print(f'{k:20} {"OK" if v else "MISSING"}')
    return all(checks.get(k,False) for k in ('ffmpeg','ffprobe','yt-dlp','torch','demucs','hook_timeline_json'))

def load_plan(cfg):
    plan=HookPlan.load(cfg.root)
    print(f'Loaded hook timeline: {plan.path}')
    for e in plan.entries:
        print(f'  {e.source_song_path} | {fmt_ms(e.start_ms)} -> {fmt_ms(e.end_ms)} | {e.duration_ms/1000:.3f}s')
    for item in plan.unconfigured:
        print(f'  {item["song_path"]} | NOT CONFIGURED — fill hook.start and hook.end')
    return plan

def list_scan(cfg):
    pkgs=scan_packages(cfg.input_dir,bool(cfg.get('input.recursive',False)))
    if not pkgs: print('No MP3 packages found.'); return 0
    for p in pkgs: print(f'{p.basename}: mp3={p.mp3.exists()} lrc={p.lrc.exists()} json={p.json.exists()}')
    return 0

def main():
    parser=argparse.ArgumentParser(description='Phase 3 timeline-driven Telugu Reel generator')
    parser.add_argument('--config',default='config.json')
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--doctor',action='store_true'); group.add_argument('--scan',action='store_true'); group.add_argument('--fillhookjson',action='store_true'); group.add_argument('--process-all',action='store_true'); group.add_argument('--process'); group.add_argument('--resume',action='store_true'); group.add_argument('--inspect-match'); group.add_argument('--validate'); group.add_argument('--repair-state',action='store_true'); group.add_argument('--clean-temp',action='store_true')
    parser.add_argument('--force',action='store_true')
    args=parser.parse_args(); cfg=Config.load(args.config)
    if args.doctor: raise SystemExit(0 if doctor(cfg) else 2)
    if args.scan: raise SystemExit(list_scan(cfg))
    if args.fillhookjson:
        result=HookPlan.fill_from_final(cfg.root)
        print(f'Updated hook timeline: {result["path"]}')
        print(f'Songs found: {result["song_count"]} | existing hook times preserved: {result["preserved_count"]}')
        for missing in result['missing_lrc']:
            print(f'WARNING Missing LRC: {missing}')
        for item in json.loads(Path(result['path']).read_text(encoding='utf-8')).get('songs', []):
            hook=item.get('hook', {})
            state='CONFIGURED' if hook.get('start') and hook.get('end') else 'NOT CONFIGURED'
            print(f'  {item["song_path"]} | {item["lrc_path"]} | {state}')
        return
    if args.repair_state:
        db=DB(cfg.db_path); fixed=Recovery(cfg,db,logging.getLogger('phase3')).repair(); db.close(); print('Repaired:',fixed); return
    if args.clean_temp:
        db=DB(cfg.db_path); n=Recovery(cfg,db,logging.getLogger('phase3')).clean_temp(); db.close(); print(f'Removed {n} temp entries'); return

    # Every processing invocation automatically synchronizes hook_timeline.json
    # with songs/final before loading the plan. Existing manual timelines are
    # preserved; only newly discovered songs are added with blank hook times.
    sync=HookPlan.fill_from_final(cfg.root)
    print(f'Auto-updated hook timeline: {sync["path"]}')
    print(f'  songs found: {sync["song_count"]} | new: {sync["new_count"]} | existing hooks preserved: {sync["preserved_count"]}')
    for missing in sync['missing_lrc']:
        print(f'  WARNING Missing LRC: {missing}')

    # With no processing flag, main.py itself means process the configured hook plan.
    plan=load_plan(cfg)
    if not plan.entries:
        raise SystemExit('No configured hook timelines. Edit hook_timeline.json and fill hook.start / hook.end.')
    if args.resume:
        db=DB(cfg.db_path); rows=db.pending_jobs(); db.close(); pending={str(r['song_basename']) for r in rows}
        pipe=Pipeline(cfg)
        for e in plan.entries:
            if e.basename in pending:
                try: pipe.process_entry(e,force=False)
                except Exception: continue
        pipe.close(); return
    if args.inspect_match:
        from pathlib import Path
        e=plan.by_basename(Path(args.inspect_match).stem if Path(args.inspect_match).suffix else args.inspect_match)
        path=cfg.temp_dir/e.basename/'matching'/'selected_hook_match.json'
        print(path.read_text(encoding='utf-8') if path.exists() else 'No match cache found.'); return
    if args.validate:
        from pathlib import Path
        name=Path(args.validate).stem if Path(args.validate).suffix else args.validate
        mp4=cfg.output_dir/f'{name}_reel.mp4'
        if not mp4.exists(): raise SystemExit('Reel MP4 not found')
        v=Validator(cfg,cfg.temp_dir/name,logging.getLogger('phase3')).validate_mp4(mp4); print(json.dumps(v,indent=2,ensure_ascii=False)); return
    if args.process:
        from pathlib import Path
        name=Path(args.process).stem if Path(args.process).suffix else args.process
        pipe=Pipeline(cfg); pipe.process_entry(plan.by_basename(name),force=args.force); pipe.close(); return
    pipe=Pipeline(cfg); pipe.process_all(plan,force=args.force); pipe.close()

if __name__=='__main__': main()
