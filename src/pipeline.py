from __future__ import annotations
import logging, shutil
from pathlib import Path
from .scanner import SongPackage
from .package_validator import validate_package
from .hashing import hash_package
from .audio_io import probe
from .stem_isolator import StemIsolator
from .acoustic_analyzer import AcousticAnalyzer
from .lyric_reader import parse_lrc, load_canonical_words
from .lyric_analyzer import LyricAnalyzer
from .phrase_repetition import PhraseRepetition
from .song_structure import SongStructureDetector
from .youtube_info import YouTubeInfo
from .youtube_audio import YouTubeAudioDownloader
from .audio_match import AudioMatcher
from .video_grabber import VideoGrabber
from .video_renderer import VideoRenderer
from .audio_8d import Audio8DEngine
from .lyric_renderer import LyricRenderer
from .assembler import Assembler
from .validator import Validator
from .output_json import OutputJSONBuilder
from .db import DB
from .utils import Phase3Error, json_dump, sha256_file, stable_json_hash
from .hook_plan import HookPlanEntry

class Pipeline:
    def __init__(self,cfg): self.cfg=cfg; self.db=DB(cfg.db_path); self.logger=logging.getLogger('phase3')
    def _work(self,pkg): return self.cfg.temp_dir/pkg.basename
    def _logger_for(self,pkg):
        log_dir=self._work(pkg)/'logs'; log_dir.mkdir(parents=True,exist_ok=True); path=log_dir/'song.log'
        logger=logging.getLogger(f'phase3.song.{pkg.basename}'); logger.handlers.clear(); logger.setLevel(logging.INFO); logger.propagate=False
        fh=logging.FileHandler(path,encoding='utf-8'); fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s')); logger.addHandler(fh)
        sh=logging.StreamHandler(); sh.setFormatter(logging.Formatter('%(levelname)s %(message)s')); logger.addHandler(sh); return logger

    def process(self,pkg:SongPackage,plan_entry:HookPlanEntry,force=False):
        work=self._work(pkg); work.mkdir(parents=True,exist_ok=True); logger=self._logger_for(pkg)
        try:
            meta=validate_package(pkg,self.cfg); hashes=hash_package(pkg.mp3,pkg.lrc,pkg.json); audio_info=probe(pkg.mp3)
            if plan_entry.start_ms<0 or plan_entry.end_ms<=plan_entry.start_ms or plan_entry.end_ms>audio_info['duration_ms']:
                raise Phase3Error('HOOK_PLAN_INVALID',f'Invalid hook timeline {plan_entry.start_ms}-{plan_entry.end_ms} for {pkg.basename} ({audio_info["duration_ms"]} ms song)')
            lrc_lines=parse_lrc(pkg.lrc); words=load_canonical_words(meta['json'],lrc_lines)
            plan_hash=stable_json_hash({'song_path':plan_entry.source_song_path,'start_ms':plan_entry.start_ms,'end_ms':plan_entry.end_ms})
            identity=stable_json_hash({'basename':pkg.basename,'hashes':hashes,'hook_plan':plan_hash,'pipeline':'1.0.16','config':self.cfg.config_hash,'demucs':self.cfg.get('demucs.model'),'match':'first_15s_energy_anchor','video_layout':'static_center_80pct','lyrics':'lrc_line_word_highlight','audio':'8d_spatial_4stem'})
            existing=self.db.get_job(pkg.basename)
            if not force and existing and existing['status']=='finalized' and existing['processing_identity']==identity and self._output_valid(pkg):
                logger.info('Already finalized for current hook plan/config; skipping %s',pkg.basename); return
            row=self.db.upsert_job(song_basename=pkg.basename,mp3_sha256=hashes['mp3_sha256'],lrc_sha256=hashes['lrc_sha256'],json_sha256=hashes['json_sha256'],processing_identity=identity,status='pending',stage='input_verified',quality_status='running',hook_selection_mode='timeline_file',manual_hook_start_ms=plan_entry.start_ms,manual_hook_end_ms=plan_entry.end_ms)
            self.db.set_stage(pkg.basename,'input_verified','running'); self.db.set_hook_mode(pkg.basename,'timeline_file',plan_entry.start_ms,plan_entry.end_ms)
            snapshot=work/'input_snapshot'; snapshot.mkdir(exist_ok=True)
            for p in (pkg.mp3,pkg.lrc,pkg.json): shutil.copy2(p,snapshot/p.name)

            stems=StemIsolator(self.cfg,work,logger).run(pkg.mp3); self.db.set_stage(pkg.basename,'stems_ready','running')
            acoustic=AcousticAnalyzer(self.cfg,work,logger).analyze(pkg.mp3,stems)
            lyric_analysis=LyricAnalyzer(self.cfg,work,logger).analyze(words,lrc_lines)
            phrases=PhraseRepetition(work,logger).analyze(words,lyric_analysis['lines'])
            structure=SongStructureDetector(work,logger).discover(words,lyric_analysis,phrases,acoustic)
            json_dump(work/'analysis'/'selected_hook.json',{
                'mode':'timeline_file','song_path':plan_entry.source_song_path,'start_ms':plan_entry.start_ms,'end_ms':plan_entry.end_ms,'duration_ms':plan_entry.duration_ms
            })
            json_dump(work/'analysis'/'analysis_summary.json',{'acoustic':acoustic,'lyric_analysis':lyric_analysis,'phrase_repetition':phrases,'song_structure':structure})
            self.db.set_stage(pkg.basename,'song_analysis_ready','running'); self.db.set_stage(pkg.basename,'hook_timeline_loaded','running')

            # Calculate one global offset between the original song and the full YouTube song audio.
            # The user-selected hook is then mapped by adding that offset directly.
            yt_info=YouTubeInfo(self.cfg,work,logger).get(meta['youtube_video_id'])
            yt_audio=YouTubeAudioDownloader(self.cfg,work,logger).download(meta['youtube_video_id']); self.db.set_stage(pkg.basename,'youtube_audio_ready','running')
            match=AudioMatcher(self.cfg,work,logger).match(pkg.mp3,yt_audio,plan_entry.start_ms,plan_entry.end_ms)
            json_dump(work/'matching'/'selected_hook_match.json',match)
            self.db.add_match(self.db.get_job(pkg.basename)['id'],meta['youtube_video_id'],match); self.db.set_stage(pkg.basename,'query_audio_ready','running'); self.db.set_stage(pkg.basename,'video_match_ready','running')

            guarder=VideoGrabber(self.cfg,work,logger); downloaded=guarder.download_section(meta['youtube_video_id'],match['video_match_start_ms'],match['video_match_end_ms'])
            exact=work/'video'/'exact_segment.mp4'
            guard_before_ms=min(int(self.cfg.get('video_match.guard_before_ms',1500)), max(0,int(match['video_match_start_ms'])))
            guarder.trim_exact(downloaded,exact,plan_entry.duration_ms,trim_start_ms=guard_before_ms); self.db.set_stage(pkg.basename,'video_segment_ready','running')
            cropped=VideoRenderer(self.cfg,work,logger).render(exact,None,None); self.db.set_stage(pkg.basename,'video_rendered','running')

            audio_engine=Audio8DEngine(self.cfg,work,logger); audio=audio_engine.render(stems,plan_entry.start_ms,plan_entry.end_ms,plan_entry.duration_ms,'MANUAL_TIMELINE'); self.db.set_stage(pkg.basename,'audio_rendered','running')
            ass,lyric_plan=LyricRenderer(self.cfg,work,logger).render(words,lrc_lines,plan_entry.start_ms,plan_entry.end_ms); self.db.set_stage(pkg.basename,'lyrics_rendered','running')
            stage_final=work/'stage_final'; stage_final.mkdir(exist_ok=True); staged_mp4=stage_final/f'{pkg.basename}_reel.mp4'
            Assembler(self.cfg,work,logger).assemble(cropped,audio,ass,staged_mp4,plan_entry.duration_ms); self.db.set_stage(pkg.basename,'assembled','running')

            staged_json=stage_final/f'{pkg.basename}_reel.json'
            source_hashes={k:hashes[k] for k in ('mp3_sha256','lrc_sha256','json_sha256')}
            source_section={'basename':pkg.basename,'song_path':plan_entry.source_song_path,'mp3_filename':pkg.mp3.name,'lrc_filename':pkg.lrc.name,'json_filename':pkg.json.name,**source_hashes,'input_duration_ms':audio_info['duration_ms']}
            hook_json={'mode':'timeline_file','source_file':'hook_timeline.json','song_path':plan_entry.source_song_path,'start_ms':plan_entry.start_ms,'end_ms':plan_entry.end_ms,'duration_ms':plan_entry.duration_ms}
            video_render={'resolution':'1080x1920','layout':'static_center','video_height_fraction':float(self.cfg.get('video_layout.height_fraction',0.80)),'source_segment_start_ms':match['video_match_start_ms'],'source_segment_end_ms':match['video_match_end_ms'],'guard_before_ms':self.cfg.get('video_match.guard_before_ms'),'guard_after_ms':self.cfg.get('video_match.guard_after_ms'),'dynamic_subject_tracking':False}
            audio_json={'source':'local_song','format':'8d_spatial_4stem','duration_ms':plan_entry.duration_ms,'target_lufs':self.cfg.get('audio_8d.target_lufs',-14),'true_peak_db':self.cfg.get('audio_8d.true_peak_db',-1),'demucs_stems_cropped_to_hook':True,'cropped_stem_paths':audio_engine.manifest.get('cropped_stems',{}) if audio_engine.manifest else {},'spatial_roles':audio_engine.manifest.get('stem_roles',{}) if audio_engine.manifest else {},'pitch_or_speed_change':False,'audio_8d_manifest':str(work/'audio'/'audio_8d_manifest.json')}
            processing={'run_id':stable_json_hash({'identity':identity,'hook_plan':plan_hash}),'pipeline_version':'1.0.16','config_hash':self.cfg.config_hash,'demucs':stems}
            validation=Validator(self.cfg,work,logger).validate_mp4(staged_mp4)
            current=hash_package(pkg.mp3,pkg.lrc,pkg.json); integrity=all(current[k]==hashes[k] for k in ('mp3_sha256','lrc_sha256','json_sha256')); validation.setdefault('checks',{})['input_integrity']=integrity; validation['overall']=bool(validation.get('overall',False) and integrity)
            duration_error_ms=abs(int(validation['probe'].get('duration_ms',0))-plan_entry.duration_ms)
            validation['checks']['duration_match']=duration_error_ms<=500
            validation['duration_error_ms']=duration_error_ms
            validation['checks']['input_integrity']=integrity
            validation['failed_checks']=[k for k,v in validation.get('checks',{}).items() if isinstance(v,bool) and not v]
            # Recompute the final result strictly from the actual boolean checks.
            # This keeps validation authoritative after duration/integrity checks are added.
            validation['overall']=(len(validation['failed_checks'])==0)
            json_dump(work/'validation'/'final_validation.json',validation)
            if not validation['overall']:
                logger.error('OUTPUT VALIDATION FAILED: checks=%s probe=%s', validation['failed_checks'], validation.get('probe',{}))
                raise Phase3Error('OUTPUT_VALIDATION_FAILED',f'Final validation failed: {", ".join(validation["failed_checks"])}',details=validation)
            self.db.set_stage(pkg.basename,'validated','running')
            data=OutputJSONBuilder(self.cfg,work,logger).build(source_section,processing,hook_json,yt_info,match,video_render,audio_json,lyric_plan,validation,[])
            OutputJSONBuilder(self.cfg,work,logger).write(data,staged_json,staged_mp4)
            out_dir=self.cfg.output_dir; out_dir.mkdir(parents=True,exist_ok=True); final_mp4=out_dir/f'{pkg.basename}_reel.mp4'; final_json=out_dir/f'{pkg.basename}_reel.json'
            shutil.copy2(staged_mp4,final_mp4); shutil.copy2(staged_json,final_json)
            self.db.add_artifact(self.db.get_job(pkg.basename)['id'],'reel_mp4',str(final_mp4),sha256_file(final_mp4),final_mp4.stat().st_size)
            self.db.add_artifact(self.db.get_job(pkg.basename)['id'],'reel_json',str(final_json),sha256_file(final_json),final_json.stat().st_size)
            self.db.set_stage(pkg.basename,'finalized','finalized'); logger.info('FINALIZED %s -> %s',pkg.basename,final_mp4); return final_mp4,final_json
        except Phase3Error as e:
            logger.exception('%s: %s',e.code,e); self.db.set_stage(pkg.basename,'failed','failed',e.code,str(e)); raise
        except Exception as e:
            logger.exception('Unexpected failure'); self.db.set_stage(pkg.basename,'failed','failed','UNEXPECTED',str(e)); raise

    def _output_valid(self,pkg):
        mp4=self.cfg.output_dir/f'{pkg.basename}_reel.mp4'; js=self.cfg.output_dir/f'{pkg.basename}_reel.json'; return mp4.exists() and js.exists() and mp4.stat().st_size>10000
    def process_all(self,plan,force=False):
        results=[]
        for entry in plan.entries:
            pkg=SongPackage(entry.basename,entry.song_path,entry.song_path.with_suffix('.lrc'),entry.song_path.with_suffix('.json'))
            try:
                logger=self._logger_for(pkg); logger.info('HOOK PLAN: %s | %s -> %s',entry.source_song_path,entry.start_ms,entry.end_ms)
                meta=validate_package(pkg,self.cfg); info=probe(pkg.mp3); plan.validate_package_and_duration(entry,info)
                results.append(self.process(pkg,entry,force=force))
            except Exception as exc:
                logging.getLogger('phase3').error('%s failed: %s',entry.basename,exc)
                continue
        return results
    def process_entry(self,entry,force=False):
        pkg=SongPackage(entry.basename,entry.song_path,entry.song_path.with_suffix('.lrc'),entry.song_path.with_suffix('.json'))
        return self.process(pkg,entry,force=force)
    def close(self): self.db.close()
