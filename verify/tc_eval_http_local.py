import base64
import json
import urllib.request
from pathlib import Path
import sys

ROOT = Path(r'e:\game\BERP')
sys.path.insert(0, str(ROOT / 'verify'))
from ai_engine_path import import_ai_engine_evaluator

mod = import_ai_engine_evaluator()
STANDARD_YONGE = '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。'
STANDARD_JINGYESI = '床前明月光，疑是地上霜。举头望明月，低头思故乡。'


def post_ai(audio_path: Path, standard_text: str):
    mime = 'audio/wav' if audio_path.suffix.lower() == '.wav' else 'audio/webm'
    payload = {
        'audio_base64': f'data:{mime};base64,' + base64.b64encode(audio_path.read_bytes()).decode('utf-8'),
        'standard_text': standard_text,
        'language': 'zh',
    }
    req = urllib.request.Request('http://127.0.0.1:8001/evaluate', data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode('utf-8'))


def score_core(standard_text: str, transcript: str):
    alignment = mod._summarize_alignment(standard_text, transcript)
    correct = alignment['correct']
    mis = alignment['mispronunciation']
    omission = alignment['omission']
    insertion = alignment['insertion']
    ref_len = max(1, alignment['ref_len'])
    accuracy_raw = (correct - (0.8 * mis) - (1.0 * omission) - (0.4 * insertion)) / ref_len
    accuracy_score = int(round(max(0.0, min(100.0, accuracy_raw * 100.0))))
    confidence = mod._resolve_asr_confidence(0.0, standard_text, transcript, alignment)
    pron_base = 60.0 + (40.0 * confidence)
    mis_ratio = mis / ref_len
    pron_penalty = min(35.0, mis_ratio * 100.0 * 0.6)
    pronunciation = int(round(max(0.0, min(100.0, pron_base - pron_penalty))))
    semantic, content = mod._compute_content_score(standard_text, transcript, alignment)
    errors = mod._generate_error_details(standard_text, transcript)
    return {
        'breakdown': {'accuracy': accuracy_score, 'pronunciation': pronunciation, 'semantic': semantic},
        'content': content,
        'error_head': errors[0] if errors else None,
    }

results = {}
case1 = post_ai(ROOT / 'YongE.wav', STANDARD_YONGE)
results['TC-EVAL-01'] = {'transcript': case1.get('transcript'), 'breakdown': case1.get('breakdown'), 'total_score': case1.get('total_score'), 'feedback': case1.get('feedback')}
case2 = score_core(STANDARD_JINGYESI, '床前明月光，疑是地上霜。举头忘明月，低头思故乡。')
results['TC-EVAL-02'] = case2
case3 = score_core(STANDARD_JINGYESI, '床前明月光，疑是地上霜')
results['TC-EVAL-03'] = case3
case4 = score_core(STANDARD_YONGE, '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。红掌拨清波。')
results['TC-EVAL-04'] = case4
slow_obj = post_ai(ROOT / 'test_video' / 'yonge1.wav', STANDARD_YONGE)
results['TC-EVAL-05'] = {'file': 'yonge1.wav', 'transcript': slow_obj.get('transcript'), 'breakdown': slow_obj.get('breakdown'), 'feedback': slow_obj.get('feedback')}
fast_obj = post_ai(ROOT / 'test_video' / 'yonge2.webm', STANDARD_YONGE)
results['TC-EVAL-06'] = {'file': 'yonge2.webm', 'transcript': fast_obj.get('transcript'), 'breakdown': fast_obj.get('breakdown'), 'feedback': fast_obj.get('feedback')}
Path(r'e:\game\BERP\verify\tc_eval_http_local_results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(results, ensure_ascii=False, indent=2))
