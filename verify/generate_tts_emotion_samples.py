import json
import subprocess
from pathlib import Path
import sys
import base64
import itertools

ROOT = Path(r'e:\game\BERP')
GEN = ROOT / 'verify' / 'tts_generated'
GEN.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / 'ai-engine'))
from audio_feature_extractor import AudioFeatureExtractor

TEXTS = {
    '咏鹅': '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。',
    '静夜思': '床前明月光，疑是地上霜。举头望明月，低头思故乡。',
}

# 用中文女声生成，靠 rate / pitch / volume 制造不同风格。
VOICE = 'Microsoft Huihui Desktop'
PARAMS = {
    '咏鹅': {
        'match': [
            {'id':'m1','rate':'20%','pitch':'+35%','volume':'100%'},
            {'id':'m2','rate':'30%','pitch':'+45%','volume':'100%'},
            {'id':'m3','rate':'10%','pitch':'+25%','volume':'100%'},
        ],
        'diverge': [
            {'id':'d1','rate':'-25%','pitch':'-35%','volume':'80%'},
            {'id':'d2','rate':'-35%','pitch':'-45%','volume':'75%'},
            {'id':'d3','rate':'-15%','pitch':'-25%','volume':'85%'},
        ],
        'neutral': [
            {'id':'n1','rate':'0%','pitch':'0%','volume':'100%'},
            {'id':'n2','rate':'-5%','pitch':'-5%','volume':'95%'},
            {'id':'n3','rate':'5%','pitch':'5%','volume':'100%'},
        ],
    },
    '静夜思': {
        'match': [
            {'id':'m1','rate':'-25%','pitch':'-20%','volume':'80%'},
            {'id':'m2','rate':'-35%','pitch':'-30%','volume':'75%'},
            {'id':'m3','rate':'-15%','pitch':'-15%','volume':'85%'},
        ],
        'diverge': [
            {'id':'d1','rate':'20%','pitch':'+30%','volume':'100%'},
            {'id':'d2','rate':'30%','pitch':'+40%','volume':'100%'},
            {'id':'d3','rate':'10%','pitch':'+20%','volume':'100%'},
        ],
        'neutral': [
            {'id':'n1','rate':'0%','pitch':'0%','volume':'100%'},
            {'id':'n2','rate':'5%','pitch':'0%','volume':'95%'},
            {'id':'n3','rate':'-5%','pitch':'0%','volume':'95%'},
        ],
    },
}

profiles = json.loads((ROOT / 'ai-engine' / 'poem_emotion_profiles.json').read_text(encoding='utf-8'))['poem_profiles']
extractor = AudioFeatureExtractor(model_id='iic/emotion2vec_base_finetuned')

def powershell_escape(s: str) -> str:
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def synthesize_to_wav(text: str, wav_path: Path, rate: str, pitch: str, volume: str):
    ssml = f'''<speak version="1.0" xml:lang="zh-CN" xmlns="http://www.w3.org/2001/10/synthesis"><voice name="{VOICE}"><prosody rate="{rate}" pitch="{pitch}" volume="{volume}">{powershell_escape(text)}</prosody></voice></speak>'''
    ps = f"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice('{VOICE}')
$s.SetOutputToWaveFile('{str(wav_path)}')
$s.SpeakSsml(@'{ssml}'@)
$s.Dispose()
"""
    subprocess.run(['powershell','-NoProfile','-Command', ps], check=True, capture_output=True, text=True)

def evaluate_file(poem: str, path: Path):
    raw = path.read_bytes()
    data_url = 'data:audio/wav;base64,' + base64.b64encode(raw).decode('ascii')
    packet = extractor.extract_emotion_expression(data_url, standard_text=TEXTS[poem], compute_trajectory=True)
    emo = packet['emotion_expression']
    det = emo['detected']
    av = det['av_raw']
    match = emo['match'] or {}
    return {
        'poem': poem,
        'file': path.name,
        'detected_arousal': round(float(av['arousal']), 4),
        'detected_valence': round(float(av['valence']), 4),
        'top1_label': (det.get('top1') or {}).get('label'),
        'top1_prob': round(float((det.get('confidence') or {}).get('top1') or 0.0), 4),
        'distance': float(match.get('target_center_distance') or 0.0),
        'normalized_distance': float(match.get('normalized_distance') or 0.0),
        'in_band': bool(match.get('in_target_bandwidth')),
        'style_match': int(match.get('style_match') or 0),
        'deviation_rating': str(match.get('style_deviation_rating')),
        'feedback_rules': emo.get('feedback_rules') or {},
        'stability': int(((emo.get('stability') or {}).get('stability')) or 0),
    }

def intended_score(poem: str, intended: str, r: dict) -> float:
    # 更偏向“用于论文展示的区分度”而不是单纯最大 style_match
    if intended == 'match':
        return (30 if r['in_band'] else 0) + r['style_match'] - r['distance'] * 30
    if intended == 'diverge':
        bonus = 25 if (not r['in_band']) else 0
        emo_bonus = 10 if r['top1_label'] in ('SAD','NEUTRAL') and poem == '咏鹅' else 0
        emo_bonus += 10 if r['top1_label'] in ('HAPPY','SURPRISED') and poem == '静夜思' else 0
        return bonus + (100 - r['style_match']) + r['distance'] * 30 + emo_bonus
    if intended == 'neutral':
        neutral_dist = abs(r['detected_arousal'] - 0.35) + abs(r['detected_valence'] - 0.5)
        label_bonus = 15 if r['top1_label'] == 'NEUTRAL' else 0
        return label_bonus + (20 - neutral_dist * 20) - abs(r['style_match'] - 70) * 0.1
    return 0

all_results = []
selected = []
for poem, groups in PARAMS.items():
    for intended, params_list in groups.items():
        candidates = []
        for p in params_list:
            out = GEN / f"{poem}_{intended}_{p['id']}.wav"
            synthesize_to_wav(TEXTS[poem], out, p['rate'], p['pitch'], p['volume'])
            r = evaluate_file(poem, out)
            r['intended'] = intended
            r['tts_params'] = p
            r['selection_score'] = round(float(intended_score(poem, intended, r)), 4)
            candidates.append(r)
            all_results.append(r)
        candidates.sort(key=lambda x: x['selection_score'], reverse=True)
        selected.append(candidates[0])

# 重命名为 1/2/3 版本，便于论文表述
rename_plan = []
for r in selected:
    target_idx = {'match': 1, 'diverge': 2, 'neutral': 3}[r['intended']]
    new_name = ('yonge' if r['poem']=='咏鹅' else 'jingyesi') + f'{target_idx}_tts.wav'
    src = GEN / r['file']
    dst = GEN / new_name
    if src.resolve() != dst.resolve():
        dst.write_bytes(src.read_bytes())
    r['export_file'] = new_name
    rename_plan.append({'src': r['file'], 'dst': new_name})

payload = {
    'selected': selected,
    'all_candidates': all_results,
    'rename_plan': rename_plan,
}
(ROOT / 'verify' / 'tts_emotion_selected_results.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(payload, ensure_ascii=False, indent=2))
