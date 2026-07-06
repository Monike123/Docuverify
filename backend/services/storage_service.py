import shutil
from pathlib import Path

from fastapi import HTTPException, UploadFile

from config import ACCEPTED_EXTENSIONS, MAX_UPLOAD_BYTES, TEMP_UPLOADS

# Leading "magic bytes" per accepted file type. Used to reject files whose real
# content does not match their extension.
_MAGIC = {
    ".pdf": [b"%PDF"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
}


def ensure_dirs():
    TEMP_UPLOADS.mkdir(parents=True, exist_ok=True)


def validate_upload(doc_type: str, filename: str) -> str:
    if doc_type not in ACCEPTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Invalid doc_type: {doc_type}")
    ext = Path(filename).suffix.lower()
    if ext not in ACCEPTED_EXTENSIONS[doc_type]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid extension {ext} for {doc_type}. Accepted: {sorted(ACCEPTED_EXTENSIONS[doc_type])}",
        )
    return ext


def _check_magic(ext: str, head: bytes) -> bool:
    signatures = _MAGIC.get(ext)
    if not signatures:
        return True
    return any(head.startswith(sig) for sig in signatures)


async def save_upload(doc_id: str, file: UploadFile) -> Path:
    ensure_dirs()
    dest_dir = TEMP_UPLOADS / doc_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    # Never trust the client filename for the path; only use its extension.
    ext = Path(file.filename or "upload.bin").suffix.lower()
    dest = dest_dir / f"original{ext}"

    written = 0
    first_chunk = True
    with dest.open("wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            if first_chunk:
                if not _check_magic(ext, chunk):
                    f.close()
                    shutil.rmtree(dest_dir, ignore_errors=True)
                    raise HTTPException(
                        status_code=400,
                        detail="File content does not match its extension.",
                    )
                first_chunk = False
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                f.close()
                shutil.rmtree(dest_dir, ignore_errors=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Max {MAX_UPLOAD_BYTES // (1024 * 1024)}MB.",
                )
            f.write(chunk)

    if written == 0:
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="Empty file.")

    return dest


def get_upload_path(doc_id: str) -> Path | None:
    dest_dir = TEMP_UPLOADS / doc_id
    if not dest_dir.exists():
        return None
    files = list(dest_dir.glob("original.*"))
    return files[0] if files else None


def delete_upload(doc_id: str):
    dest_dir = TEMP_UPLOADS / doc_id
    if dest_dir.exists():
        shutil.rmtree(dest_dir, ignore_errors=True)
