"""
INEI SMART-CORE - Document Repository Service
Handles institutional directives, PEI, PAT, technical guides, workshop manuals.
"""

from typing import Dict, Any, List, Optional
from app.database.connection import get_db

class DocumentService:
    @staticmethod
    def get_documents(category: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_db() as conn:
            query = """
                SELECT d.*, u.full_name as uploader_name, u.role as uploader_role
                FROM documents d
                LEFT JOIN users u ON d.uploaded_by = u.id
                WHERE 1=1
            """
            params = []
            if category and category != "TODOS":
                query += " AND d.category = ?"
                params.append(category)

            query += " ORDER BY d.created_at DESC"
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def create_document(
        title: str,
        category: str,
        file_path: str,
        file_size_kb: float = 150.0,
        uploaded_by: Optional[int] = 1,
        is_public: int = 1
    ) -> Dict[str, Any]:
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO documents (title, category, file_path, file_size_kb, uploaded_by, is_public)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (title, category, file_path, file_size_kb, uploaded_by, is_public)
            )
            doc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            return {"success": True, "document_id": doc_id, "message": "Documento institucional registrado con éxito."}

    @staticmethod
    def update_document(
        document_id: int,
        title: str,
        category: str,
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        with get_db() as conn:
            if file_path:
                conn.execute(
                    """
                    UPDATE documents
                    SET title = ?, category = ?, file_path = ?
                    WHERE id = ?
                    """, (title, category, file_path, document_id)
                )
            else:
                conn.execute(
                    """
                    UPDATE documents
                    SET title = ?, category = ?
                    WHERE id = ?
                    """, (title, category, document_id)
                )
            return {"success": True, "message": "Documento actualizado correctamente."}

    @staticmethod
    def delete_document(document_id: int) -> Dict[str, Any]:
        with get_db() as conn:
            conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            return {"success": True, "message": "Documento eliminado correctamente."}


document_service = DocumentService()
