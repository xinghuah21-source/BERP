import math


EMOTION_PROTOTYPES = {
    "ANGRY": {"arousal": 0.90, "valence": 0.20, "label_cn": "愤怒"},
    "DISGUSTED": {"arousal": 0.60, "valence": 0.10, "label_cn": "厌恶"},
    "FEARFUL": {"arousal": 0.85, "valence": 0.10, "label_cn": "恐惧"},
    "HAPPY": {"arousal": 0.75, "valence": 0.85, "label_cn": "愉悦"},
    "NEUTRAL": {"arousal": 0.35, "valence": 0.50, "label_cn": "平静"},
    "OTHER": {"arousal": 0.50, "valence": 0.50, "label_cn": "其他"},
    "SAD": {"arousal": 0.20, "valence": 0.15, "label_cn": "悲伤"},
    "SURPRISED": {"arousal": 0.82, "valence": 0.70, "label_cn": "惊讶"},
    "UNKNOWN": {"arousal": 0.45, "valence": 0.45, "label_cn": "未知"},
}

LABEL_ALIASES = {
    "ANGRY": "ANGRY",
    "生气": "ANGRY",
    "DISGUST": "DISGUSTED",
    "DISGUSTED": "DISGUSTED",
    "厌恶": "DISGUSTED",
    "FEAR": "FEARFUL",
    "FEARFUL": "FEARFUL",
    "恐惧": "FEARFUL",
    "HAPPY": "HAPPY",
    "开心": "HAPPY",
    "NEUTRAL": "NEUTRAL",
    "中立": "NEUTRAL",
    "平静": "NEUTRAL",
    "OTHER": "OTHER",
    "其他": "OTHER",
    "SAD": "SAD",
    "难过": "SAD",
    "悲伤": "SAD",
    "SURPRISED": "SURPRISED",
    "吃惊": "SURPRISED",
    "惊讶": "SURPRISED",
    "UNKNOWN": "UNKNOWN",
    "<UNK>": "UNKNOWN",
    "UNK": "UNKNOWN",
    "未知": "UNKNOWN",
}


def normalize_emotion_label(label: str) -> str:
    raw = (label or "").strip()
    if "/" in raw:
        parts = [p.strip() for p in raw.split("/") if p.strip()]
    else:
        parts = [raw]

    candidates = []
    for part in parts:
        candidates.append(part)
        candidates.append(part.upper())
    for candidate in candidates:
        mapped = LABEL_ALIASES.get(candidate)
        if mapped:
            return mapped
    return raw.upper()


def probs_to_av(probs: dict[str, float]) -> dict:
    merged: dict[str, float] = {}
    for k, v in probs.items():
        if v <= 0:
            continue
        norm_key = normalize_emotion_label(k)
        merged[norm_key] = merged.get(norm_key, 0.0) + float(v)

    keys = [k for k, v in merged.items() if v > 0]
    if not keys:
        return {
            "arousal": 0.35,
            "valence": 0.50,
            "confidence_top1": 0.0,
            "confidence_entropy": 0.0,
        }

    total = sum(merged[k] for k in keys)
    norm = {k: (merged[k] / total) for k in keys}

    A = 0.0
    V = 0.0
    for k, p in norm.items():
        proto = EMOTION_PROTOTYPES.get(k)
        if proto is None:
            continue
        A += p * float(proto["arousal"])
        V += p * float(proto["valence"])

    top1 = max(norm.values()) if norm else 0.0
    n = len(norm)
    ent = 0.0
    for p in norm.values():
        ent -= p * math.log(p + 1e-12)
    ent_norm = ent / (math.log(n) + 1e-12) if n > 1 else 0.0
    conf_entropy = 1.0 - ent_norm if n > 1 else 1.0

    return {
        "arousal": A,
        "valence": V,
        "confidence_top1": float(top1),
        "confidence_entropy": float(conf_entropy),
    }
