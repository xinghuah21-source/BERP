import json
from pathlib import Path
import sys

sys.path.insert(0, r'e:\game\BERP\verify')
from ai_engine_path import import_ai_engine_evaluator
from ai_engine_local_scoring import score_text_only

mod = import_ai_engine_evaluator()
standard = '床前明月光，疑是地上霜。举头望明月，低头思故乡。'
full_transcript = '床前明月光，疑是地上霜。举头望明月，低头思故乡。'
partial_transcript = '床前明月光，疑是地上霜'

full_alignment = mod._summarize_alignment(standard, full_transcript)
full_semantic_core, full_content = mod._compute_content_score(standard, full_transcript, full_alignment)
partial_alignment = mod._summarize_alignment(standard, partial_transcript)
partial_semantic_core, partial_content = mod._compute_content_score(standard, partial_transcript, partial_alignment)

result = {
    'full': {
        'core_semantic': full_semantic_core,
        'content_features': full_content,
        'score_text_only': score_text_only(standard_text=standard, transcript=full_transcript),
    },
    'partial': {
        'core_semantic': partial_semantic_core,
        'content_features': partial_content,
        'score_text_only': score_text_only(standard_text=standard, transcript=partial_transcript),
    }
}
Path(r'e:\game\BERP\verify\case2_compare.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
