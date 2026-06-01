import importlib.util
import sys
from pathlib import Path


def import_ai_engine_evaluator():
    root = Path(r"E:\game\BERP\ai-engine").resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location("ai_engine_evaluator", str(root / "evaluator.py"))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot_load_ai_engine_evaluator")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ai_engine_evaluator"] = mod
    spec.loader.exec_module(mod)
    return mod

