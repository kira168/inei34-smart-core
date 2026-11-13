"""
INEI SMART-CORE - Document Repository Router
"""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path
import os
import shutil
from app.auth.rbac import get_current_user, require_role
from app.services.document_service import document_service

router = APIRouter(prefix="/api/documents", tags=["Documents"])

class DocumentCreateRequest(BaseModel):
    title: str
    category: str
    file_path: str = "/storage/docs/documento.pdf"
    file_size_kb: float = 240.0
    is_public: int = 1

class DocumentUpdateRequest(BaseModel):
    title: str
    category: str
    file_path: Optional[str] = None

@router.get("")
def get_documents(category: Optional[str] = None, user: dict = Depends(get_current_user)):
    return document_service.get_documents(category)

@router.post("")
def upload_document(
    req: DocumentCreateRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE", "SECRETARÍA", "SECRETARIA"]))
):
    return document_service.create_document(
        title=req.title,
        category=req.category,
        file_path=req.file_path,
        file_size_kb=req.file_size_kb,
        uploaded_by=user.get("id", 1),
        is_public=req.is_public
    )

@router.put("/{document_id}")
def update_document(
    document_id: int,
    req: DocumentUpdateRequest,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "DOCENTE", "SECRETARÍA", "SECRETARIA"]))
):
    return document_service.update_document(
        document_id=document_id,
        title=req.title,
        category=req.category,
        file_path=req.file_path
    )

@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    user: dict = Depends(require_role(["ADMINISTRADOR", "DIRECTOR", "SECRETARÍA", "SECRETARIA"]))
):
    return document_service.delete_document(document_id)

@router.post("/upload-file")
async def upload_document_file_binary(file: UploadFile = File(...)):
    """Guarda físicamente el archivo subido en public/uploads y retorna su ruta pública."""
    from app.main import STATIC_DIR
    uploads_dir = STATIC_DIR / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    safe_filename = Path(file.filename).name
    dest_path = uploads_dir / safe_filename
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {
        "status": "success",
        "filename": safe_filename,
        "url": f"/uploads/{safe_filename}",
        "size": os.path.getsize(dest_path)
    }
