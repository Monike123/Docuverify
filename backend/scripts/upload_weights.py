"""One-time helper to upload YOLO weights to a Hugging Face Hub model repo.

Usage (PowerShell):
    $env:HF_TOKEN="hf_xxx"            # a write token from https://huggingface.co/settings/tokens
    $env:HF_REPO_ID="<user>/docverify-weights"
    .\.venv\Scripts\python.exe scripts\upload_weights.py

The backend later downloads these files at startup via huggingface_hub.hf_hub_download
when the local weight paths are not present (e.g. on Render).
"""
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from config import AADHAAR_WEIGHT_FILE, AADHAAR_WEIGHTS, PAN_WEIGHT_FILE, PAN_WEIGHTS  # noqa: E402


def main() -> None:
    repo_id = os.getenv("HF_REPO_ID")
    token = os.getenv("HF_TOKEN")
    if not repo_id or not token:
        sys.exit("Set HF_REPO_ID and HF_TOKEN environment variables first.")

    from huggingface_hub import HfApi, create_repo

    uploads = [
        (Path(AADHAAR_WEIGHTS), AADHAAR_WEIGHT_FILE),
        (Path(PAN_WEIGHTS), PAN_WEIGHT_FILE),
    ]
    missing = [str(src) for src, _ in uploads if not src.exists()]
    if missing:
        sys.exit(f"Local weight file(s) not found: {missing}")

    create_repo(repo_id, repo_type="model", token=token, exist_ok=True, private=False)
    api = HfApi(token=token)

    for src, dest_name in uploads:
        print(f"Uploading {src} -> {repo_id}/{dest_name}")
        api.upload_file(
            path_or_fileobj=str(src),
            path_in_repo=dest_name,
            repo_id=repo_id,
            repo_type="model",
        )

    print(f"Done. Weights available at https://huggingface.co/{repo_id}")


if __name__ == "__main__":
    main()
