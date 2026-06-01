import json
import math
from pathlib import Path

profiles = json.loads(Path(r'e:\game\BERP\ai-engine\poem_emotion_profiles.json').read_text(encoding='utf-8'))
prof = profiles['poem_profiles']['静夜思']['profiles']['内敛型']
target = prof['target']
tol = prof['tolerance']
detected = {'arousal': 0.85, 'valence': 0.75}

da = (detected['arousal'] - target['arousal']) / max(tol.get('sigma_arousal', 0.2), 0.05)
dv = (detected['valence'] - target['valence']) / max(tol.get('sigma_valence', 0.2), 0.05)
dist = math.sqrt(da * da + dv * dv)
style = 100.0 * math.exp(-(dist * dist))
result = {
    'target': target,
    'tolerance': tol,
    'detected': detected,
    'delta_standardized': {'arousal': round(da, 4), 'valence': round(dv, 4)},
    'normalized_distance': round(dist, 4),
    'style_match_score': round(style, 6),
    'style_match_score_int': int(round(style)),
}
Path(r'e:\game\BERP\verify\case3_summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
