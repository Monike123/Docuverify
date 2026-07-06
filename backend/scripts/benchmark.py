"""Benchmark YOLO/OCR pipeline on AI_mask sample images."""
import csv
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.document_service import analyze_aadhaar, analyze_pan  # noqa: E402

WORKSPACE = BACKEND.parent.parent
AI_MASK = WORKSPACE / "AI_mask" / "AI_mask"
OUT_DIR = BACKEND / "benchmark_reports"


def run_image(path: Path, doc_type: str) -> dict:
    doc_id = str(uuid.uuid4())
    if doc_type == "aadhaar":
        result = analyze_aadhaar(str(path), doc_id)
    else:
        result = analyze_pan(str(path), doc_id)
    ocr_confs = []
    for val in result.get("extracted_fields", {}).values():
        if isinstance(val, dict) and val.get("ocr_confidence") is not None:
            ocr_confs.append(val["ocr_confidence"])
    return {
        "file": path.name,
        "doc_type": doc_type,
        "score": result["confidence_score"],
        "status": result["status"],
        "flags": result["flags"],
        "detection_flags": [f for f in result["flags"] if f.startswith("MISSING_YOLO_")],
        "ocr_confidences": ocr_confs,
        "pan_validated": result.get("extracted_fields", {}).get("pan_validated"),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(1, 5):
        p = AI_MASK / f"a{i}.jpg"
        if p.exists():
            rows.append(run_image(p, "aadhaar"))
    pan = AI_MASK / "p1.jpg"
    if pan.exists():
        rows.append(run_image(pan, "pan"))

    real_dir = BACKEND / "tests" / "fixtures" / "real"
    if real_dir.exists():
        for p in sorted(real_dir.iterdir()):
            if p.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                rows.append(run_image(p, "aadhaar"))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = OUT_DIR / f"benchmark_{ts}.json"
    csv_path = OUT_DIR / f"benchmark_{ts}.csv"

    summary = {
        "generated_at": ts,
        "aadhaar_count": sum(1 for r in rows if r["doc_type"] == "aadhaar"),
        "pan_validated_rate": sum(1 for r in rows if r.get("pan_validated")) / max(
            1, sum(1 for r in rows if r["doc_type"] == "pan")
        ),
        "rows": rows,
    }
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["file", "doc_type", "score", "status", "flags", "detection_flags", "ocr_confidences", "pan_validated"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "flags": ";".join(row["flags"]),
                    "detection_flags": ";".join(row["detection_flags"]),
                    "ocr_confidences": ";".join(str(c) for c in row["ocr_confidences"]),
                }
            )

    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")
    for row in rows:
        print(f"  {row['file']}: {row['status']} ({row['score']}) flags={row['flags'][:3]}")


if __name__ == "__main__":
    main()
