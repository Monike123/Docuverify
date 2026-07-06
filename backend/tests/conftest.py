import json
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
WORKSPACE = BACKEND.parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
AI_MASK = WORKSPACE / "AI_mask" / "AI_mask"


@pytest.fixture(scope="session", autouse=True)
def ensure_fixtures():
    manifest = FIXTURES / "manifest.json"
    if not manifest.exists():
        subprocess.run([sys.executable, str(Path(__file__).parent / "generate_fixtures.py")], check=True)
    yield


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def manifest(fixtures_dir) -> dict:
    return json.loads((fixtures_dir / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture
def aadhaar_images() -> list[Path]:
    paths = [AI_MASK / f"a{i}.jpg" for i in range(1, 5)]
    return [p for p in paths if p.exists()]


@pytest.fixture
def pan_image() -> Path | None:
    p = AI_MASK / "p1.jpg"
    return p if p.exists() else None
