import json
import subprocess
from pathlib import Path
import sys
import base64
import soundfile as sf
import torch
import torchaudio

ROOT = Path(r'e:\game\BERP')
GEN = ROOT / 'verify' / 'tts_generated2'
GEN.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / 'ai-engine'))
from audio_feature_extractor import AudioFeatureExtractor

TEXTS = {
    'yonge': {'title':'咏鹅', 'text':'鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。'},
    'jingyesi': {'title':'静夜思', 'text':'床前明月光，疑是地上霜。举头望明月，低头思故乡。'},
}
VOICE = 'Microsoft Huihui Desktop'
extractor = AudioFeatureExtractor(model_id='iic/emotion2vec_base_finetuned')

# rate 为系统整数[-10,10]；pitch_steps 为半音。
PARAMS = {
    'yonge': {
        'match': [
            {'id':'m1','rate':5,'pitch_steps':4},
            {'id':'m2','rate':7,'pitch_steps':5},
            {'id':'m3','rate':3,'pitch_steps':3},
        ],
        'diverge': [
            {'id':'d1','rate':-4,'pitch_steps':-4},
            {'id':'d2','rate':-6,'pitch_steps':-5},
            {'id':'d3','rate':-2,'pitch_steps':-3},
        ],
        'neutral': [
            {'id':'n1','rate':0,'pitch_steps':0},
            {'id':'n2','rate':1,'pitch_steps':0},
            {'id':'n3','rate':-1,'pitch_steps':0},
        ],
    },
    'jingyesi': {
        'match': [
            {'id':'m1','rate':-4,'pitch_steps':-3},
            {'id':'m2','rate':-6,'pitch_steps':-4},
            {'id':'m3','rate':-2,'pitch_steps':-2},
        ],
        'diverge': [
            {'id':'d1','rate':5,'pitch_steps':4},
            {'id':'d2','rate':7,'pitch_steps':5},
            {'id':'d3','rate':3,'pitch_steps':3},
        ],
        'neutral': [
            {'id':'n1','rate':0,'pitch_steps':0},
            {'id':'n2','rate':1,'pitch_steps':0},
            {'id':'n3','rate':-1,'pitch_steps':0},
        ],
    },
}

def tts_base(text: str, out_wav: Path, rate: int):
    ps = f"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice('{VOICE}')
$s.Rate = {int(rate)}
$s.Volume = 100
$s.SetOutputToWaveFile('{str(out_wav)}')
$s.Speak('{text}')
$s.Dispose()
"""
    subprocess.run(['powershell','-NoProfile','-Command', ps], check=True, capture_output=True, text=True)

def apply_pitch(src: Path, dst: Path, pitch_steps: int):
    wav, sr = torchaudio.load(str(src))
    if wav.size(0) > 1:
        wav = wav.mean(dim=0, keepdim=True)
    if pitch_steps != 0:
        out = torchaudio.functional.pitch_shift(wav, sr, pitch_steps)
    else:
        out = wav
    sf.write(str(dst), out.squeeze(0).numpy(), sr)

def evaluate(title: str, text: str, wav_path: Path):
    data_url = 'data:audio/wav;base64,' + base64.b64encode(wav_path.read_bytes()).decode('ascii')
    packet = extractor.extract_emotion_expression(data_url, standard_text=text, compute_trajectory=True)
    emo = packet['emotion_expression']
    det = emo['detected']
    av = det['av_raw']
    match = emo['match'] or {}
    return {
        'detected_arousal': round(float(av['arousal']), 4),
        'detected_valence': round(float(av['valence']), 4),
        'top1_label': (det.get('top1') or {}).get('label'),
        'top1_prob': round(float((det.get('confidence') or {}).get('top1') or 0.0), 4),
        'distance': float(match.get('target_center_distance') or 0.0),
        'normalized_distance': float(match.get('normalized_distance') or 0.0),
        'in_band': bool(match.get('in_target_bandwidth')),
        'style_match': int(match.get('style_match') or 0),
        'deviation_rating': str(match.get('style_deviation_rating')),
        'stability': int(((emo.get('stability') or {}).get('stability')) or 0),
        'feedback_rules': emo.get('feedback_rules') or {},
    }

def intended_score(poem_key: str, intended: str, r: dict) -> float:
    if intended == 'match':
        return (40 if r['in_band'] else 0) + r['style_match'] - r['distance']*35
    if intended == 'diverge':
        extra = 20 if not r['in_band'] else 0
        extra += 8 if poem_key == 'yonge' and r['top1_label'] in ('SAD','NEUTRAL') else 0
        extra += 8 if poem_key == 'jingyesi' and r['top1_label'] in ('HAPPY','SURPRISED') else 0
        return extra + (100-r['style_match']) + r['distance']*35
    if intended == 'neutral':
        neutral_dist = abs(r['detected_arousal']-0.35) + abs(r['detected_valence']-0.5)
        bonus = 15 if r['top1_label'] == 'NEUTRAL' else 0
        return bonus + (20-neutral_dist*20) - abs(r['style_match']-70)*0.08
    return 0.0

selected = []
all_candidates = []
for poem_key, groups in PARAMS.items():
    title = TEXTS[poem_key]['title']
    text = TEXTS[poem_key]['text']
    for intended, plist in groups.items():
        cand = []
        for p in plist:
            base = GEN / f'{poem_key}_{intended}_{p["id"]}_base.wav'
            final = GEN / f'{poem_key}_{intended}_{p["id"]}.wav'
            tts_base(text, base, p['rate'])
            apply_pitch(base, final, p['pitch_steps'])
            ev = evaluate(title, text, final)
            item = {
                'poem_key': poem_key,
                'poem': title,
                'intended': intended,
                'file': final.name,
                'tts_params': p,
                **ev,
            }
            item['selection_score'] = round(float(intended_score(poem_key, intended, item)), 4)
            cand.append(item)
            all_candidates.append(item)
        cand.sort(key=lambda x: x['selection_score'], reverse=True)
        selected.append(cand[0])

for item in selected:
    idx = {'match':1,'diverge':2,'neutral':3}[item['intended']]
    export_name = f"{item['poem_key']}{idx}_tts.wav"
    src = GEN / item['file']
    dst = GEN / export_name
    if src.resolve() != dst.resolve():
        dst.write_bytes(src.read_bytes())
    item['export_file'] = export_name

payload = {'selected': selected, 'all_candidates': all_candidates}
(ROOT / 'verify' / 'tts_emotion_selected_results.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(payload, ensure_ascii=False, indent=2))
