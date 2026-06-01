import json
from pathlib import Path
import sys

sys.path.insert(0, r'e:\game\BERP\verify')
from ai_engine_path import import_ai_engine_evaluator
from ai_engine_local_scoring import score_text_only

mod = import_ai_engine_evaluator()
standard = '床前明月光，疑是地上霜。举头望明月，低头思故乡。'
transcript = '床前明月光，疑是地上霜'

alignment = mod._summarize_alignment(standard, transcript)
semantic, content_features = mod._compute_content_score(standard, transcript, alignment)
out = score_text_only(standard_text=standard, transcript=transcript)
result = {
    'standard': standard,
    'transcript': transcript,
    'alignment': alignment,
    'content_features': content_features,
    'semantic_from_core': semantic,
    'score_text_only': out,
}
Path(r'e:\game\BERP\verify\case2_summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
