"""E2E smoke test for Aadhaar and PAN using AI_mask sample images."""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
WORKSPACE = BACKEND.parent.parent
sys.path.insert(0, str(BACKEND))

from services.document_service import analyze_document

AADHAAR_IMG = WORKSPACE / "AI_mask" / "AI_mask" / "a1.jpg"
PAN_IMG = WORKSPACE / "AI_mask" / "AI_mask" / "p1.jpg"


def run():
    if not AADHAAR_IMG.exists():
        print("SKIP: a1.jpg not found")
        return 1
    r = analyze_document("aadhaar", str(AADHAAR_IMG), "test-aadhaar")
    print("Aadhaar:", r["status"], r["confidence_score"], r["flags"][:3])
    assert r["confidence_score"] > 0

    if PAN_IMG.exists():
        r2 = analyze_document("pan", str(PAN_IMG), "test-pan")
        print("PAN:", r2["status"], r2["confidence_score"], r2["flags"][:3])
        assert r2["confidence_score"] > 0

    print("E2E OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
