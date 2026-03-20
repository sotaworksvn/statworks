"""POST /upload — Data Ingestion endpoint (F-01)."""

from __future__ import annotations

import uuid
from pathlib import PurePath

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File

from backend.models import ColumnMeta, UploadResponse
from backend.store import FileEntry, set_entry

router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ALLOWED_PRIMARY = {".xlsx", ".csv"}
ALLOWED_CONTEXT = {".docx", ".pptx"}
ALLOWED_ALL = ALLOWED_PRIMARY | ALLOWED_CONTEXT
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_extension(filename: str) -> str:
    """Return the lowercased file extension (e.g. '.xlsx')."""
    return PurePath(filename).suffix.lower()


def _parse_excel(content: bytes) -> pd.DataFrame:
    """Parse an .xlsx file into a DataFrame."""
    import io
    return pd.read_excel(io.BytesIO(content), engine="openpyxl")


def _parse_csv(content: bytes) -> pd.DataFrame:
    """Parse a .csv file into a DataFrame."""
    import io
    return pd.read_csv(io.BytesIO(content))


def _extract_docx_text(content: bytes) -> str:
    """Extract plain text from a .docx file."""
    import io
    from docx import Document

    doc = Document(io.BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_pptx_text(content: bytes) -> str:
    """Extract plain text from a .pptx file."""
    import io
    from pptx import Presentation

    prs = Presentation(io.BytesIO(content))
    lines: list[str] = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    text = paragraph.text.strip()
                    if text:
                        lines.append(text)
    return "\n".join(lines)


def _detect_columns(df: pd.DataFrame) -> list[ColumnMeta]:
    """Build column metadata list from a DataFrame."""
    cols: list[ColumnMeta] = []
    for col_name in df.columns:
        cols.append(
            ColumnMeta(
                name=str(col_name),
                dtype=str(df[col_name].dtype),
                is_numeric=bool(pd.api.types.is_numeric_dtype(df[col_name])),
            )
        )
    return cols


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=UploadResponse)
async def upload(files: list[UploadFile] = File(...)) -> UploadResponse:
    """Accept one or more files, parse data and context, return metadata."""

    # 1. Read all files and validate extensions + sizes
    file_data: list[tuple[str, str, bytes]] = []  # (filename, ext, content)

    for f in files:
        filename = f.filename or "unknown"
        ext = _get_extension(filename)

        # Extension check
        if ext not in ALLOWED_ALL:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type '{ext}'. Allowed: .xlsx, .csv, .docx, .pptx",
            )

        content = await f.read()

        # Size check
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File '{filename}' exceeds the 10 MB limit.",
            )

        file_data.append((filename, ext, content))

    # 2. Enforce exactly one primary file
    primary_files = [(fn, ext, data) for fn, ext, data in file_data if ext in ALLOWED_PRIMARY]
    if len(primary_files) == 0:
        raise HTTPException(
            status_code=422,
            detail="No primary data file (.xlsx or .csv) provided. At least one is required.",
        )
    if len(primary_files) > 1:
        raise HTTPException(
            status_code=422,
            detail="Only one primary data file (.xlsx or .csv) is allowed per upload.",
        )

    # 3. Parse primary file
    primary_fn, primary_ext, primary_content = primary_files[0]
    if primary_ext == ".xlsx":
        df = _parse_excel(primary_content)
    else:
        df = _parse_csv(primary_content)

    # Strip column name whitespace (but do NOT lowercase)
    df.columns = df.columns.str.strip()

    # 4. Parse context files
    context_parts: list[str] = []
    for fn, ext, data in file_data:
        if ext == ".docx":
            context_parts.append(_extract_docx_text(data))
        elif ext == ".pptx":
            context_parts.append(_extract_pptx_text(data))

    context_text: str | None = "\n".join(context_parts) if context_parts else None

    # 5. Build metadata
    columns = _detect_columns(df)
    row_count = len(df)
    file_id = str(uuid.uuid4())

    # 6. Store entry
    entry = FileEntry(
        file_id=file_id,
        dataframe=df,
        columns=[c.model_dump() for c in columns],
        row_count=row_count,
        context_text=context_text,
    )
    await set_entry(entry)

    return UploadResponse(
        file_id=file_id,
        columns=columns,
        row_count=row_count,
        context_extracted=context_text is not None,
    )
