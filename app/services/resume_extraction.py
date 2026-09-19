from io import BytesIO
from pathlib import Path

import fitz
from docx import Document

supported_extensions= {'.pdf','.docx','.txt'}

def extract_resume_text(filename:str,file_bytes:bytes)->str:
    """ Extracts plain text from a pdf,docx or txt resume """

    extension = Path(filename).suffix.lower()

    if extension not in supported_extensions:
        supported= ", ".join(sorted(supported_extensions))
        raise ValueError(
            f"Unsupported file type: {extension or 'missing extension'}."
            f"Supported types are: {supported}")

    if not file_bytes:
        raise ValueError("The uploaded file is empty")

    if extension == '.pdf':
        text=_extract_pdf_text(file_bytes)
    elif extension == '.docx':
        text=_extract_docx_text(file_bytes)
    else:
        text=_extract_txt_text(file_bytes)

    cleaned_text=_clean_text(text)

    if not cleaned_text:
        raise ValueError("No readable text was found in the uploaded file.")

    return cleaned_text


def _extract_pdf_text(file_bytes:bytes)->str:
    """Extracts text from all pages of a a pdf"""

    document=fitz.open(stream=file_bytes, filetype="pdf")

    try:
        page_text= [page.get_text() for page in document]
    finally:
        document.close()

    return '\n'.join(page_text)
    
def _extract_docx_text(file_bytes:bytes)->str:
    """Extracts paragraph text from a docx document"""

    document=Document(BytesIO(file_bytes))
    paragraphs=[paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]

    return '\n'.join(paragraphs)

def _extract_txt_text(file_bytes:bytes)->str:
    """Decode a plain-text resume."""

    return file_bytes.decode('utf-8', errors='replace')

def _clean_text(text:str)->str:
    """Normalizes whitespace while preserving separate lines"""

    lines=[line.strip() for line in text.splitlines()]
    non_empty_lines=[line for line in lines if line]

    return '\n'.join(non_empty_lines)