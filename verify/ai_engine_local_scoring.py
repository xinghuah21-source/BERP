from typing import Any, Dict

from ai_engine_path import import_ai_engine_evaluator


evaluator_mod = import_ai_engine_evaluator()


def score_text_only(standard_text: str, transcript: str) -> Dict[str, Any]:
    _calculate_accuracy = evaluator_mod._calculate_accuracy
    evaluate_with_tolerance = evaluator_mod.evaluate_with_tolerance
    _generate_error_details = evaluator_mod._generate_error_details

    if not transcript:
        accuracy_score = 0
        pronunciation = 0
        fluency = 0
        semantic = 0
        accuracy = 0.0
    else:
        accuracy = _calculate_accuracy(standard_text, transcript)
        tolerance_accuracy, tolerance_semantic = evaluate_with_tolerance(standard_text, transcript)
        fluency = 100
        pronunciation = max(0, min(100, int(round(max(accuracy, tolerance_accuracy) - 5))))
        semantic = max(0, min(100, tolerance_semantic))
        accuracy_score = max(0, min(100, max(int(round(accuracy)), tolerance_accuracy)))

    error_details = _generate_error_details(standard_text, transcript)
    total_score = round((accuracy_score * 0.4) + (pronunciation * 0.3) + (fluency * 0.2) + (semantic * 0.1))
    return {
        "total_score": int(total_score),
        "breakdown": {"accuracy": int(accuracy_score), "pronunciation": int(pronunciation), "fluency": int(fluency), "semantic": int(semantic)},
        "error_details": error_details,
    }

