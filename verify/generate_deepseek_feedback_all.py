import base64
import json
import urllib.request
from pathlib import Path
import sys

ROOT = Path(r'e:\game\BERP')
sys.path.insert(0, str(ROOT / 'ai-engine'))
from deepseek_client import DeepSeekClient
from deepseek_prompt_builder import build_prompt

STANDARD_YONGE = '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。'
STANDARD_JINGYESI = '床前明月光，疑是地上霜。举头望明月，低头思故乡。'


def post_ai(path: Path, standard_text: str):
    mime = 'audio/wav' if path.suffix.lower() == '.wav' else 'audio/webm'
    payload = {
        'audio_base64': f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode('utf-8'),
        'standard_text': standard_text,
        'language': 'zh',
    }
    req = urllib.request.Request('http://127.0.0.1:8001/evaluate', data=json.dumps(payload).encode('utf-8'), headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode('utf-8'))


def deepseek_for_case(case_id: str, transcript: str, reference: str, poem_title: str, breakdown: dict, note: str = ''):
    client = DeepSeekClient()
    structured_data = {
        'transcript': transcript,
        'reference': reference,
        'poem_title': poem_title,
        'breakdown': breakdown,
        'emotion_expression': {},
        'user_baseline': None,
        'timing_metrics': {},
    }
    prompt = build_prompt(structured_data)
    if note:
        prompt += f'\n\n## 补充说明\n- {note}\n'
    data = client.evaluate(prompt)
    return data if isinstance(data, dict) else {'error': client.last_error or 'deepseek_failed'}


def deepseek_for_progress(case_id: str, progress_data: dict):
    client = DeepSeekClient()
    prompt = f'''你是一名软件测试与智能教育系统分析专家。请根据以下测试结果，输出严格JSON点评。\n\n测试用例：{case_id} 评测进度反馈\n消息总数：{progress_data.get('message_count')}\n进度序列：{progress_data.get('progresses')}\n最终反馈：{progress_data.get('final_feedback')}\n最终转写：{progress_data.get('final_transcript')}\n\n输出JSON格式：\n{{\n  "overall_comment": "总体结论，40字内",\n  "emotion_feedback": "说明该用例不涉及情感朗读评分，可改写为进度反馈分析",\n  "suggestions": ["建议1", "建议2", "建议3"],\n  "poetic_insight": "说明该用例重点验证的系统能力",\n  "master_comparison": "说明与理想实时评测体验相比的结论",\n  "used_metrics": {{"accuracy": 0, "fluency": 0, "pronunciation": 0, "semantic": 0, "style_match": 0, "stability": 0}}\n}}'''
    data = client.evaluate(prompt)
    return data if isinstance(data, dict) else {'error': client.last_error or 'deepseek_failed'}

results = {}

# 真实链路完整点评
case1 = post_ai(ROOT / 'YongE.wav', STANDARD_YONGE)
results['TC-EVAL-01'] = case1.get('intelligent_feedback') or {'error': 'missing_feedback'}
case5 = post_ai(ROOT / 'test_video' / 'yonge1.wav', STANDARD_YONGE)
results['TC-EVAL-05'] = case5.get('intelligent_feedback') or {'error': 'missing_feedback'}
case6 = post_ai(ROOT / 'test_video' / 'yonge2.webm', STANDARD_YONGE)
results['TC-EVAL-06'] = case6.get('intelligent_feedback') or {'error': 'missing_feedback'}

# 本地评分用例补调 DeepSeek
results['TC-EVAL-02'] = deepseek_for_case(
    'TC-EVAL-02',
    '床前明月光，疑是地上霜。举头忘明月，低头思故乡。',
    STANDARD_JINGYESI,
    '静夜思',
    {'accuracy': 91, 'fluency': 85, 'pronunciation': 94, 'semantic': 100},
    '该用例重点验证错读字词的识别与定位，主要错误为“望”误读为“忘”。'
)
results['TC-EVAL-03'] = deepseek_for_case(
    'TC-EVAL-03',
    '床前明月光，疑是地上霜',
    STANDARD_JINGYESI,
    '静夜思',
    {'accuracy': 0, 'fluency': 70, 'pronunciation': 80, 'semantic': 50},
    '该用例重点验证漏读后两句时的评分下降与错误定位。'
)
results['TC-EVAL-04'] = deepseek_for_case(
    'TC-EVAL-04',
    '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。红掌拨清波。',
    STANDARD_YONGE,
    '咏鹅',
    {'accuracy': 89, 'fluency': 82, 'pronunciation': 96, 'semantic': 100},
    '该用例重点验证多读内容的识别与插入错误标注。'
)

# 进度反馈用例
progress_path = ROOT / 'verify' / 'tc_eval_ws_progress.json'
progress_data = json.loads(progress_path.read_text(encoding='utf-8'))
results['TC-EVAL-07'] = deepseek_for_progress('TC-EVAL-07', progress_data)

out = ROOT / 'verify' / 'tc_eval_deepseek_feedback.json'
out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(results, ensure_ascii=False, indent=2))
