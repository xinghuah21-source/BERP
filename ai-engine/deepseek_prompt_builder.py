import json
from typing import Any, Dict


def build_prompt(structured_data: Dict[str, Any]) -> str:
    emo = structured_data.get("emotion_expression") or {}
    scores = emo.get("scores") or {}
    detected = emo.get("detected") or {}
    target = emo.get("target") or {}
    match = emo.get("match") or {}
    stability = emo.get("stability") or {}
    feedback_rules = emo.get("feedback_rules") or {}
    aq = emo.get("audio_quality") or {}
    calibration = emo.get("calibration") or {}
    breakdown = structured_data.get("breakdown") or {}

    conf_top1 = None
    try:
        conf_top1 = float((detected.get("confidence") or {}).get("top1"))
    except Exception:
        conf_top1 = None

    expected_style_match = match.get("style_match")
    expected_stability = stability.get("stability")
    calibration_mode = match.get("calibration_mode") or calibration.get("mode") or "default"
    baseline = (calibration.get("user_baseline") or structured_data.get("user_baseline") or {}) if calibration_mode == "baseline" else {}
    student_offset = match.get("student_offset") or {}
    target_offset = match.get("target_offset") or {}

    calibration_block = ""
    if calibration_mode == "baseline":
        calibration_block = f"""

## 个体校准信息（已启用）
- 校准模式：baseline
- 学生基线 arousal：{baseline.get("baseline_arousal", "N/A")}
- 学生基线 valence：{baseline.get("baseline_valence", "N/A")}
- 学生偏移：arousal={student_offset.get("arousal", "N/A")}，valence={student_offset.get("valence", "N/A")}
- 目标偏移：arousal={target_offset.get("arousal", "N/A")}，valence={target_offset.get("valence", "N/A")}
- 引导重点：向学生解释情感表达的关键是契合诗歌意境，而不是一味追求更激动或更低沉
"""

    return f"""你是一位拥有30年经验的语文特级教师。请基于以下已由算法精确计算的客观数据，给出背诵评测与改进建议。

## 核心约束（不可违背）
1. 所有分数已由算法计算，你禁止改写任何分值
2. 你禁止编造音频细节（例如“听到叹气”“第3秒有停顿”），只能引用下方明确提供的数据
3. 你的职责：解释这些数据意味着什么 + 给出具体可操作的改进建议
4. 如果风格匹配 >= 80，你必须明确肯定“情感表达与诗歌意境较贴合”，禁止输出“过于平淡”“不太符合”“明显偏离”等相反表述
5. 如果风格匹配在 60-79，只能描述为“有轻微偏差”或“感染力还能增强”，禁止写成“明显不符”

## 识别文本
{structured_data.get("transcript", "无")}

## 标准原文
{structured_data.get("reference", "无")}

## 客观评分（禁止改写）
- 准确度：{breakdown.get("accuracy", "N/A")}/100
- 流畅度：{breakdown.get("fluency", "N/A")}/100
- 发音：{breakdown.get("pronunciation", "N/A")}/100
- 内容完整性：{breakdown.get("semantic", "N/A")}/100

## 情感指标（已计算，禁止改写）
- 激活度：{scores.get("arousal_score", "N/A")}/100
- 愉悦度：{scores.get("valence_score", "N/A")}/100
- 风格匹配：{match.get("style_match", "N/A")}/100
- 匹配模式：{calibration_mode}
- 是否在目标带宽内：{match.get("in_target_bandwidth", "N/A")}
- 情绪稳定性：{expected_stability if expected_stability is not None else "N/A"}/100
- 情感置信度（top1）：{conf_top1 if conf_top1 is not None else "N/A"}

## 规则结论（已计算）
- 激活度状态：{feedback_rules.get("arousal_status", "N/A")}
- 愉悦度状态：{feedback_rules.get("valence_status", "N/A")}
- 风格差距：{feedback_rules.get("style_gap", "N/A")}
- 稳定性状态：{feedback_rules.get("stability_status", "N/A")}

## 音频质量
- 时长：{aq.get("duration_seconds", "N/A")}s
- 时长是否有效：{aq.get("duration_valid", "N/A")}

## 诗歌信息
- 标题：{target.get("poem_title", structured_data.get("poem_title", "无"))}
- 标准风格：{", ".join((target.get("tags") or []))}{calibration_block}

## 输出要求（严格JSON）
- 严格 JSON
- 不得输出除 JSON 以外的任何文本

{{
  "overall_comment": "总体评语，50字内，亲切如师长，既肯定又指出核心问题",
  "emotion_feedback": "针对情感表达的专业点评；若风格匹配>=80，必须明确肯定贴合；若60-79，仅描述轻微偏差；若<60，再指出明显差距",
  "suggestions": ["建议1", "建议2", "建议3"],
  "poetic_insight": "从诗意理解角度，评价学生是否真正理解了这首诗的情感",
  "master_comparison": "与名家朗诵的简要对比，指出可借鉴之处（不要编造具体名家内容）",
  "used_metrics": {{
    "accuracy": {int(breakdown.get("accuracy") or 0)},
    "fluency": {int(breakdown.get("fluency") or 0)},
    "pronunciation": {int(breakdown.get("pronunciation") or 0)},
    "semantic": {int(breakdown.get("semantic") or 0)},
    "style_match": {int(expected_style_match or 0)},
    "stability": {int(expected_stability or 0)}
  }}
}}
"""


def parse_deepseek_json(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    try:
        obj = json.loads(raw)
    except Exception:
        try:
            obj = json.loads(raw, strict=False)
        except Exception:
            s = raw
            if s.startswith("```"):
                s = s.strip("`")
                if s.startswith("json"):
                    s = s[4:].lstrip()
            l = s.find("{")
            r = s.rfind("}")
            if l == -1 or r == -1 or r <= l:
                raise
            obj = json.loads(s[l : r + 1], strict=False)
    if not isinstance(obj, dict):
        raise ValueError("deepseek_output_not_object")
    for k in ("overall_comment", "emotion_feedback", "suggestions", "used_metrics"):
        if k not in obj:
            raise ValueError(f"deepseek_output_missing_{k}")
    if not isinstance(obj.get("suggestions"), list):
        raise ValueError("deepseek_output_suggestions_not_list")
    if not isinstance(obj.get("used_metrics"), dict):
        raise ValueError("deepseek_output_used_metrics_not_object")
    return obj
