"""Resume parsing service."""

import hashlib
import os
from typing import Dict, Any, Optional
from pathlib import Path
import PyPDF2
import docx
import pdfplumber
from packages.common.logging import get_logger
from packages.database.models import Resume
from packages.database.connection import get_db

logger = get_logger(__name__)


class ResumeParser:
    """Parse resumes from PDF/DOCX files."""
    
    def __init__(self, storage_path: str = "./storage/resumes"):
        """Initialize resume parser.
        
        Args:
            storage_path: Path to store resume files
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    def _calculate_hash(self, content: bytes) -> str:
        """Calculate content hash."""
        return hashlib.sha256(content).hexdigest()
    
    def _extract_text_pdf(self, file_path: Path) -> str:
        """Extract text from PDF file."""
        text = ""
        
        # Try pdfplumber first (better for complex PDFs)
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or ""
            if text.strip():
                return text
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {e}")
        
        # Fallback to PyPDF2
        try:
            with open(file_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text()
            return text
        except Exception as e:
            logger.error(f"PyPDF2 extraction failed: {e}")
            raise
    
    def _extract_text_docx(self, file_path: Path) -> str:
        """Extract text from DOCX file."""
        try:
            doc = docx.Document(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text
        except Exception as e:
            logger.error(f"DOCX extraction failed: {e}")
            raise
    
    def _parse_sections(self, text: str) -> Dict[str, Any]:
        """Parse resume into structured sections.
        
        This is a basic implementation. In production, you might use
        more sophisticated NLP or LLM-based parsing.
        """
        sections = {
            "contact": {},
            "experience": [],
            "education": [],
            "skills": [],
            "summary": ""
        }
        
        lines = text.split("\n")
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Detect section headers (basic heuristic)
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in ["experience", "work experience", "employment"]):
                current_section = "experience"
            elif any(keyword in line_lower for keyword in ["education", "academic"]):
                current_section = "education"
            elif any(keyword in line_lower for keyword in ["skills", "technical skills", "competencies"]):
                current_section = "skills"
            elif any(keyword in line_lower for keyword in ["summary", "objective", "profile"]):
                current_section = "summary"
            elif current_section:
                if current_section == "experience":
                    sections["experience"].append(line)
                elif current_section == "education":
                    sections["education"].append(line)
                elif current_section == "skills":
                    # Extract skills (comma-separated or bullet points)
                    skills = [s.strip() for s in line.replace(",", "|").split("|")]
                    sections["skills"].extend(skills)
                elif current_section == "summary":
                    sections["summary"] += line + " "
        
        return sections
    
    def parse_resume(
        self,
        file_content: bytes,
        file_name: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Parse resume file.
        
        Args:
            file_content: File content as bytes
            file_content: File name
            user_id: User ID
        
        Returns:
            Parsed resume data
        """
        # Calculate content hash
        content_hash = self._calculate_hash(file_content)
        
        # Determine file type
        file_ext = Path(file_name).suffix.lower()
        if file_ext == ".pdf":
            file_type = "pdf"
        elif file_ext in [".docx", ".doc"]:
            file_type = "docx"
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
        
        # Save file
        file_path = self.storage_path / f"{content_hash}{file_ext}"
        file_path.write_bytes(file_content)
        
        # Extract text
        if file_type == "pdf":
            text = self._extract_text_pdf(file_path)
        else:
            text = self._extract_text_docx(file_path)
        
        # Parse sections
        parsed_sections = self._parse_sections(text)
        
        return {
            "file_path": str(file_path),
            "file_name": file_name,
            "file_type": file_type,
            "content_hash": content_hash,
            "text_content": text,
            "parsed_data": parsed_sections
        }
