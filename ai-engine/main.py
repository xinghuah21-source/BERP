from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
import os

from evaluator import get_evaluator, Evaluator

app = FastAPI(title="BERP AI Evaluation Engine")

class EvaluationRequest(BaseModel):
    audio_base64: str
    standard_text: str
    language: str = "zh"
    user_baseline: Optional[Dict[str, Any]] = None


class CalibrationResponse(BaseModel):
    baseline_arousal: float
    baseline_valence: float
    audio_quality: Optional[Dict[str, Any]] = None
    detected: Optional[Dict[str, Any]] = None

class ErrorDetail(BaseModel):
    type: str
    position: int
    expected: str
    actual: str

class Breakdown(BaseModel):
    accuracy: int
    pronunciation: int
    fluency: int
    semantic: int

class EvaluationResponse(BaseModel):
    total_score: int
    breakdown: Breakdown
    error_details: List[ErrorDetail]
    feedback: str
    transcript: str
    confidence: float = 0.0
    segments: List[Dict[str, Any]] = Field(default_factory=list)
    duration: float = 0.0
    emotion_schema_version: Optional[str] = None
    emotion_expression: Optional[Dict[str, Any]] = None
    intelligent_feedback: Optional[Dict[str, Any]] = None
    fallback_note: Optional[str] = None

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "env": os.getenv("ENV", ""),
        "xunfei_configured": bool(os.getenv("XUNFEI_APP_ID") and os.getenv("XUNFEI_API_KEY") and os.getenv("XUNFEI_API_SECRET")),
    }

@app.post("/evaluate", response_model=EvaluationResponse)
def evaluate_audio(request: EvaluationRequest, evaluator: Evaluator = Depends(get_evaluator)):
    try:
        result = evaluator.evaluate(
            audio_base64=request.audio_base64,
            standard_text=request.standard_text,
            language=request.language,
            user_baseline=request.user_baseline,
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluation failed: {str(e)}"
        )


@app.post("/calibrate_emotion", response_model=CalibrationResponse)
def calibrate_emotion(request: EvaluationRequest, evaluator: Evaluator = Depends(get_evaluator)):
    try:
        return evaluator.calibrate_baseline(
            audio_base64=request.audio_base64,
            sample_text=request.standard_text,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Calibration failed: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
