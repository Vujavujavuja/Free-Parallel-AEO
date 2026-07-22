"""Document upload + parse endpoint. Returns extracted text the client attaches
to the run's company profile as orchestrator context."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile

from aeo.api.deps import AuthGuard
from aeo.schemas.company import SourceDocument
from aeo.services.document_service import SUPPORTED, parse_document

router = APIRouter(tags=["documents"])

_MAX_BYTES = 15 * 1024 * 1024  # 15 MB per file


@router.post("/documents/parse", response_model=list[SourceDocument])
async def parse_documents(
    files: list[UploadFile], _auth: AuthGuard
) -> list[SourceDocument]:
    out: list[SourceDocument] = []
    for f in files:
        name = f.filename or "document"
        ext = name[name.rfind("."):].lower() if "." in name else ""
        if ext not in SUPPORTED:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type {ext!r}. Allowed: {sorted(SUPPORTED)}",
            )
        data = await f.read()
        if len(data) > _MAX_BYTES:
            raise HTTPException(status_code=413, detail=f"{name} exceeds 15 MB.")
        out.append(parse_document(name, data))
    return out
