import json
import base64
from pathlib import Path
import sys

ROOT = Path(r'e:\game\BERP')
sys.path.insert(0, str(ROOT / 'ai-engine'))
from audio_feature_extractor import AudioFeatureExtractor

TESTS = [
    ('咏鹅', ROOT / 'test_video' / 'yonge1.wav', '匹配样本', '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。'),
    ('咏鹅', ROOT / 'test_video' / 'yonge2.webm', '背离样本', '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。'),
    ('咏鹅', ROOT / 'test_video' / 'yonge3.webm', '中性样本', '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。'),
    ('静夜思', ROOT / 'test_video' / 'jingyesi1.wav', '匹配样本', '床前明月光，疑是地上霜。举头望明月，低头思故乡。'),
    ('静夜思', ROOT / 'test_video' / 'jingyesi2.webm', '背离样本', '床前明月光，疑是地上霜。举头望明月，低头思故乡。'),
    ('静夜思', ROOT / 'test_video' / 'jingyesi3.webm', '中性样本', '床前明月光，疑是地上霜。举头望明月，低头思故乡。'),
]

extractor = AudioFeatureExtractor(model_id='iic/emotion2vec_base_finetuned')
profiles = json.loads((ROOT / 'ai-engine' / 'poem_emotion_profiles.json').read_text(encoding='utf-8'))['poem_profiles']
rows = []
for poem, path, sample_type, text in TESTS:
    suffix = path.suffix.lower()
    mime = 'audio/wav' if suffix == '.wav' else 'application/octet-stream'
    data_url = f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode('ascii')
    packet = extractor.extract_emotion_expression(data_url, standard_text=text, compute_trajectory=True)
    emo = packet['emotion_expression']
    target = emo['target'] or {}
    match = emo['match'] or {}
    detected = emo['detected'] or {}
    av = (detected.get('av_raw') or {})
    profile_name = target.get('profile')
    bw = target.get('bandwidth') or {}
    rows.append({
        'poem': poem,
        'profile': profile_name,
        'target_arousal': round(float((target.get('target_av_raw') or {}).get('arousal') or 0.0), 3),
        'target_valence': round(float((target.get('target_av_raw') or {}).get('valence') or 0.0), 3),
        'bandwidth': {
            'arousal_min': bw.get('arousal_min'), 'arousal_max': bw.get('arousal_max'),
            'valence_min': bw.get('valence_min'), 'valence_max': bw.get('valence_max')
        },
        'file': path.name,
        'sample_type': sample_type,
        'detected_arousal': round(float(av.get('arousal') or 0.0), 4),
        'detected_valence': round(float(av.get('valence') or 0.0), 4),
        'distance': match.get('target_center_distance'),
        'normalized_distance': match.get('normalized_distance'),
        'in_band': match.get('in_target_bandwidth'),
        'within_tolerance': match.get('within_tolerance'),
        'style_match': match.get('style_match'),
        'deviation_rating': match.get('style_deviation_rating'),
        'top1_label': (detected.get('top1') or {}).get('label'),
        'top1_prob': round(float((detected.get('confidence') or {}).get('top1') or 0.0), 4),
        'stability': ((emo.get('stability') or {}).get('stability')),
        'feedback_rules': emo.get('feedback_rules'),
    })

out = ROOT / 'verify' / 'emotion_style_actual_results.json'
out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(rows, ensure_ascii=False, indent=2))
