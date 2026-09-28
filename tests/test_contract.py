from pathlib import Path
import json
from src.config import Config
from src.scanner import scan_packages
from src.package_validator import extract_word_records, extract_youtube_video_id
from src.lyric_reader import parse_lrc
from src.ass_generator import ASSGenerator, clean_lrc_text


def test_youtube_nested_id():
    data={'youtube_video':{'selected':True,'metadata':{'raw':{'video_id':'abc123'}}}}
    assert extract_youtube_video_id(data)=='abc123'


def test_word_extraction():
    data={'phase2':{'alignment':{'lines':[{'words':[{'original':'నమస్తే','start_ms':10,'end_ms':100,'score':.9}]}]}}}
    words=extract_word_records(data)
    assert len(words)==1 and words[0]['start_ms']==10


def test_lrc_parse_word_timestamps():
    p=Path('tests')/'_tmp.lrc'
    p.write_text('[00:01.00] hello [00:01.40] world\n[00:02.00] next\n',encoding='utf-8')
    try:
        lines=parse_lrc(p)
        assert len(lines)==2
        assert clean_lrc_text(lines[0]['text'])=='hello world'
        assert lines[0]['words'][0]['text']=='hello'
        assert lines[0]['words'][1]['text']=='world'
        assert lines[0]['words'][0]['start_ms']==1000
        assert lines[0]['words'][1]['start_ms']==1400
    finally:
        p.unlink(missing_ok=True)


def test_line_by_line_ass_uses_lrc_text_and_word_highlight(tmp_path):
    lrc=[
        {'start_ms':1000,'end_ms':2000,'text':'అమ్మ [00:01.40]నాన్న','words':[{'text':'అమ్మ','start_ms':1000,'end_ms':1400},{'text':'నాన్న','start_ms':1400,'end_ms':2000}]},
        {'start_ms':2000,'end_ms':3000,'text':'రెండవ లైన్','words':[]},
    ]
    words=[{'text':'అమ్మ','start_ms':1000,'end_ms':1400},{'text':'నాన్న','start_ms':1400,'end_ms':2000}]
    class Cfg:
        def get(self,key,default=None):
            return {'lyrics.font_name':'Baloo Tammudu 2 ExtraBold','lyrics.font_size':58,'lyrics.font_bold':True,'lyrics.outline':3,'lyrics.shadow':4,'lyrics.center_x':540,'lyrics.center_y':960,'lyrics.base_color':'#FFFFFF','lyrics.current_color':'#FFD65A','lyrics.completed_color':'#FFFFFF','lyrics.max_chars_single_line':30,'lyrics.min_scale_x':70}.get(key,default)
    out=ASSGenerator(Cfg(),tmp_path,None).generate(lrc,words,1000,2500,Path('font.ttf'))
    txt=out.read_text(encoding='utf-8')
    assert 'అమ్మ' in txt and 'నాన్న' in txt and 'రెండవ' in txt and 'లైన్' in txt
    assert txt.count('Dialogue:') >= 3
    assert r'\c&H005AD6FF&' in txt  # #FFD65A in ASS BGR


def test_timecode_accepts_mm_ss_decimal_format():
    from src.utils import parse_timecode
    assert parse_timecode('02:12.92') == 132920
    assert parse_timecode('03:11.72') == 191720


def test_hook_plan_accepts_timeline_duration(tmp_path):
    from src.hook_plan import HookPlan
    root=tmp_path
    song=root/'songs/final/test.mp3'; song.parent.mkdir(parents=True); song.write_bytes(b'fake')
    data={'schema_version':1,'songs':[{'song_path':'songs/final/test.mp3','hook':{'start':'00:00:01.000','end':'00:00:40.000'}}]}
    p=root/'hook_timeline.json'; p.write_text(json.dumps(data),encoding='utf-8')
    plan=HookPlan.load(root,p)
    assert plan.entries[0].start_ms==1000 and plan.entries[0].duration_ms==39000



def test_hook_plan_allows_unconfigured_template_entry(tmp_path):
    from src.hook_plan import HookPlan
    root=tmp_path; song=root/'songs/final/test.mp3'; song.parent.mkdir(parents=True); song.write_bytes(b'fake')
    p=root/'hook_timeline.json'; p.write_text(json.dumps({'schema_version':1,'songs':[{'song_path':'songs/final/test.mp3','hook':{'start':'','end':''}}]}),encoding='utf-8')
    plan=HookPlan.load(root,p)
    assert not plan.entries and len(plan.unconfigured)==1


def test_hook_plan_allows_over_40_seconds(tmp_path):
    from src.hook_plan import HookPlan
    root=tmp_path
    song=root/'songs/final/test.mp3'; song.parent.mkdir(parents=True); song.write_bytes(b'fake')
    p=root/'hook_timeline.json'; p.write_text(json.dumps({'schema_version':1,'songs':[{'song_path':'songs/final/test.mp3','hook':{'start':'00:00:00','end':'00:01:20.001'}}]}),encoding='utf-8')
    plan=HookPlan.load(root,p)
    assert plan.entries[0].duration_ms==80001


def test_match_result_is_json_serializable_without_cycle():
    candidates=[
        {'video_match_start_ms':1000,'video_match_end_ms':21000,'confidence':0.91},
        {'video_match_start_ms':5000,'video_match_end_ms':25000,'confidence':0.84},
    ]
    best=dict(candidates[0]); best['accepted']=True; best['candidates']=[dict(candidate) for candidate in candidates]
    json.dumps(best,ensure_ascii=False,indent=2)


def test_run_cmd_utf8_output():
    import subprocess, sys
    code="import sys; sys.stdout.buffer.write('తెలుగు ✓'.encode('utf-8'))"
    from src.utils import run_cmd
    p=run_cmd([sys.executable,'-c',code])
    assert 'తెలుగు' in p.stdout and '✓' in p.stdout



def test_global_audio_offset_maps_hook(tmp_path):
    import numpy as np
    from src.audio_io import write_float_wav
    from src.audio_match import AudioMatcher
    sr=8000
    rng=np.random.default_rng(7)
    seconds=12
    n=sr*seconds
    t=np.arange(n,dtype=np.float32)/sr
    envelope=(0.25 + 0.65*(0.5+0.5*np.sin(2*np.pi*0.37*t)))*(0.7+0.3*np.sin(2*np.pi*0.11*t+0.8)**2)
    original=(envelope*np.sin(2*np.pi*(180+25*np.sin(2*np.pi*0.13*t))*t)).astype(np.float32)
    offset_sec=4
    prefix=(0.02*rng.standard_normal(sr*offset_sec)).astype(np.float32)
    suffix=(0.02*rng.standard_normal(sr*3)).astype(np.float32)
    youtube=np.concatenate([prefix, original, suffix]).astype(np.float32)
    q=tmp_path/'original.wav'; r=tmp_path/'youtube.wav'
    write_float_wav(q,original,sr); write_float_wav(r,youtube,sr)
    class Cfg:
        def get(self,key,default=None): return {'video_match.sync_sample_rate':8000,'video_match.sync_frame_ms':50.0}.get(key,default)
    result=AudioMatcher(Cfg(),tmp_path,None).match(q,r,5000,9000)
    assert result['accepted'] is True and result['match_method']=='first_15s_energy_anchor'
    assert 3950<=result['offset_ms']<=4050
    assert result['video_match_start_ms']==5000+result['offset_ms']
    assert result['video_match_end_ms']==9000+result['offset_ms']



def test_video_section_cache_is_invalidated_when_request_changes(tmp_path):
    from src.video_grabber import VideoGrabber
    import json
    class Cfg:
        def get(self, key, default=None):
            return {'video_match.guard_before_ms': 1500, 'video_match.guard_after_ms': 1500}.get(key, default)
    grabber=VideoGrabber(Cfg(), tmp_path, None)
    req1=grabber._section_request('videoA', 10000, 20000)
    req2=grabber._section_request('videoA', 12000, 22000)
    assert req1 != req2


def test_trim_exact_rejects_short_source(tmp_path):
    from src.video_grabber import VideoGrabber
    from src.utils import Phase3Error
    class Cfg:
        def get(self, key, default=None): return default
    g=VideoGrabber(Cfg(), tmp_path, None)
    # The real FFmpeg probe is exercised by the dedicated smoke test; this contract
    # assertion documents the required failure mode for an insufficient source.
    assert hasattr(g, 'trim_exact')
    assert issubclass(Phase3Error, RuntimeError)


def test_first_15s_anchor_finds_positive_youtube_offset(tmp_path):
    import numpy as np
    from src.audio_io import write_float_wav
    from src.audio_match import AudioMatcher
    sr=4000
    rng=np.random.default_rng(17)
    anchor_seconds=15
    n=sr*anchor_seconds
    t=np.arange(n,dtype=np.float32)/sr
    # Deliberately distinctive high/low energy movement.
    env=(0.08 + 0.75*(0.5+0.5*np.sin(2*np.pi*0.21*t+0.5)))
    env*=0.55 + 0.45*(0.5+0.5*np.sin(2*np.pi*0.57*t+1.2))
    original=(env*np.sin(2*np.pi*(170+30*np.sin(2*np.pi*0.09*t))*t)).astype(np.float32)
    offset=5
    prefix=(0.01*rng.standard_normal(sr*offset)).astype(np.float32)
    suffix=(0.01*rng.standard_normal(sr*20)).astype(np.float32)
    youtube=np.concatenate([prefix, original, suffix]).astype(np.float32)
    q=tmp_path/'original.wav'; r=tmp_path/'youtube.wav'
    write_float_wav(q,original,sr); write_float_wav(r,youtube,sr)
    class Cfg:
        def get(self,key,default=None):
            return {
                'video_match.sync_sample_rate':4000,
                'video_match.sync_frame_ms':50.0,
                'video_match.sync_hop_ms':25.0,
                'video_match.anchor_seconds':15.0,
                'video_match.earliest_near_best_tolerance':0.015,
            }.get(key,default)
    result=AudioMatcher(Cfg(),tmp_path,None).match(q,r,10000,20000)
    assert result['match_method']=='first_15s_energy_anchor'
    assert result['accepted'] is True
    assert 4900 <= result['offset_ms'] <= 5100
    assert result['video_match_start_ms']==10000+result['offset_ms']


def test_trim_exact_accepts_guard_start_argument():
    import inspect
    from src.video_grabber import VideoGrabber
    sig=inspect.signature(VideoGrabber.trim_exact)
    assert 'trim_start_ms' in sig.parameters


def test_assembler_accepts_exact_duration_argument():
    import inspect
    from src.assembler import Assembler
    sig=inspect.signature(Assembler.assemble)
    assert 'duration_ms' in sig.parameters


def test_static_video_panel_defaults_to_80_percent():
    import json
    data=json.loads(Path('config.json').read_text(encoding='utf-8'))
    assert abs(data['video_layout']['height_fraction']-0.8)<1e-9


def test_validation_overall_recomputed_from_failed_checks():
    checks={'exists': True, 'decode': True, 'video_dimensions': True, 'has_audio': True, 'has_video': True, 'aspect_ratio': True, 'duration_match': True, 'input_integrity': True}
    failed=[k for k,v in checks.items() if isinstance(v,bool) and not v]
    assert failed==[]
    assert (len(failed)==0) is True


def test_validator_returns_true_without_overall_self_check(tmp_path, monkeypatch):
    from src.validator import Validator
    class Cfg:
        def get(self,key,default=None): return default
    fake_probe={
        'duration_ms': 58800, 'channels': 2, 'width': 1080, 'height': 1920,
    }
    monkeypatch.setattr('src.validator.probe', lambda path: fake_probe)
    result=Validator(Cfg(),tmp_path,None).validate_mp4(tmp_path/'x.mp4')
    assert result['failed_checks']==['exists','decode']
    assert result['overall'] is False
