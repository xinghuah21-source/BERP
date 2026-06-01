import json
from pathlib import Path
import sys
sys.path.insert(0, r'e:\game\BERP\verify')
from ai_engine_path import import_ai_engine_evaluator
mod = import_ai_engine_evaluator()
STANDARD_JINGYESI = '床前明月光，疑是地上霜。举头望明月，低头思故乡。'
STANDARD_YONGE = '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。'

def score_core(standard_text, transcript):
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
    return {'breakdown': {'accuracy': accuracy_score, 'pronunciation': pronunciation, 'semantic': semantic}, 'content': content, 'error_head': errors[0] if errors else None}

out = {
 'TC-EVAL-02': score_core(STANDARD_JINGYESI, '床前明月光，疑是地上霜。举头忘明月，低头思故乡。'),
 'TC-EVAL-03': score_core(STANDARD_JINGYESI, '床前明月光，疑是地上霜'),
 'TC-EVAL-04': score_core(STANDARD_YONGE, '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。红掌拨清波。')
}
print(json.dumps(out, ensure_ascii=False, indent=2))
