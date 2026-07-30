from __future__ import annotations

import io
import re
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader

from app.core.config import settings
from app.services.cache_service import cache

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
ALLOWED_MIMES = {
    ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".txt": {"text/plain", "application/octet-stream"},
}


def extract_text(filename: str, content_type: str, data: bytes) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS or content_type.lower() not in ALLOWED_MIMES.get(extension, set()):
        raise HTTPException(415, "Unsupported document. Upload a PDF, DOCX, or TXT file.")
    try:
        if extension == ".pdf":
            if not data.startswith(b"%PDF"):
                raise ValueError("invalid PDF signature")
            text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
        elif extension == ".docx":
            if not data.startswith(b"PK"):
                raise ValueError("invalid DOCX signature")
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                xml = archive.read("word/document.xml")
            root = ElementTree.fromstring(xml)
            namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            text = "\n".join(
                "".join(node.text or "" for node in paragraph.iter(f"{{{namespace}}}t"))
                for paragraph in root.iter(f"{{{namespace}}}p")
            )
        else:
            if b"\x00" in data:
                raise ValueError("binary TXT content")
            text = data.decode("utf-8-sig")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            422,
            "The document could not be parsed. Check that it is not corrupted, encrypted, or scanned without selectable text.",
        ) from exc
    text = text.replace("\r\n", "\n").strip()
    if not text:
        raise HTTPException(422, "The document contains no extractable text.")
    return text


def _clean_line(value: str) -> str:
    return re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", value).strip()


def parse_stories(text: str) -> list[dict]:
    story_pattern = re.compile(
        r"^\s*(?:user\s*story|story)\s*(?:[#:]?\s*[\w.-]+)?\s*[:\-]\s*(.+)$", re.I
    )
    ac_heading = re.compile(
        r"^\s*(?:acceptance\s+criteria|acceptance\s+criterion|ac)\s*(?:[#:]?\s*\d+)?\s*[:\-]?\s*(.*)$",
        re.I,
    )
    as_a_story = re.compile(r"^\s*as\s+an?\s+.+?\s+i\s+want\s+.+", re.I)
    stories: list[dict] = []
    current: dict | None = None
    in_criteria = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        story_match = story_pattern.match(line)
        if story_match or as_a_story.match(line):
            current = {
                "id": f"US-{len(stories) + 1}",
                "text": _clean_line(story_match.group(1) if story_match else line),
                "acceptance_criteria": [],
            }
            stories.append(current)
            in_criteria = False
            continue
        criterion_match = ac_heading.match(line)
        if criterion_match and current:
            in_criteria = True
            inline = _clean_line(criterion_match.group(1))
            if inline:
                current["acceptance_criteria"].append(inline)
            continue
        if current and in_criteria:
            cleaned = _clean_line(line)
            if cleaned:
                current["acceptance_criteria"].append(cleaned)
    if not stories:
        raise HTTPException(
            422,
            "No user stories were found. Use a 'User Story:' heading or the 'As a ... I want ...' format.",
        )
    if any(not story["acceptance_criteria"] for story in stories):
        raise HTTPException(422, "Each user story must have at least one acceptance criterion.")
    return stories


def payload_from_stories(stories: list[dict]) -> dict:
    user_stories = []
    criteria = []
    for story in stories:
        story_id = str(story["id"])
        user_stories.append({"id": story_id, "text": str(story["text"])})
        for index, criterion in enumerate(story["acceptance_criteria"], 1):
            criteria.append(
                {"id": f"{story_id}-AC-{index}", "text": str(criterion), "user_story_id": story_id}
            )
    return {
        "user_stories": user_stories,
        "acceptance_criteria": criteria,
        "functional_requirements": [],
        "non_functional_requirements": [],
        "epics": [],
        "features": [],
        "business_rules": [],
        "dependencies": [],
        "constraints": [],
        "image_ids": [],
        "tech_stack": {},
    }


class DocumentService:
    @staticmethod
    def key(session_id: uuid.UUID) -> str:
        return cache.key("document-session", str(session_id))

    async def upload(self, document: UploadFile) -> dict:
        max_bytes = settings.document_max_size_mb * 1024 * 1024
        data = await document.read(max_bytes + 1)
        if not data:
            raise HTTPException(422, "The uploaded document is empty.")
        if len(data) > max_bytes:
            raise HTTPException(
                413, f"The document must be {settings.document_max_size_mb} MB or smaller."
            )
        text = extract_text(document.filename or "", document.content_type or "", data)
        stories = parse_stories(text)
        session_id = uuid.uuid4()
        record = {
            "session_id": str(session_id),
            "filename": Path(document.filename or "document").name,
            "content": text,
            "stories": stories,
            "input_payload": payload_from_stories(stories),
        }
        try:
            await cache.set_json_required(
                self.key(session_id), record, settings.document_session_ttl_seconds
            )
        except Exception as exc:
            raise HTTPException(
                503,
                "The document session could not be stored in Redis. Try again or use manual entry.",
            ) from exc
        return {
            **record,
            "content": text[:2000],
            "expires_in_seconds": settings.document_session_ttl_seconds,
        }

    async def update(self, session_id: uuid.UUID, stories: list[dict]) -> dict:
        record = await self.get(session_id)
        if not stories:
            raise HTTPException(422, "At least one user story is required.")
        if any(not str(item.get("text", "")).strip() for item in stories):
            raise HTTPException(422, "Each user story must contain text.")
        if any(
            not item.get("acceptance_criteria")
            or any(not str(criterion).strip() for criterion in item["acceptance_criteria"])
            for item in stories
        ):
            raise HTTPException(422, "Each user story must have at least one acceptance criterion.")
        normalized = [
            {
                "id": f"US-{index}",
                "text": str(item["text"]).strip(),
                "acceptance_criteria": [
                    str(criterion).strip() for criterion in item["acceptance_criteria"]
                ],
            }
            for index, item in enumerate(stories, 1)
        ]
        record.update(
            {"stories": normalized, "input_payload": payload_from_stories(normalized)}
        )
        try:
            await cache.set_json_required(
                self.key(session_id), record, settings.document_session_ttl_seconds
            )
        except Exception as exc:
            raise HTTPException(
                503, "The reviewed document session could not be saved to Redis."
            ) from exc
        return record

    async def get(self, session_id: uuid.UUID) -> dict:
        try:
            record = await cache.get_json_required(self.key(session_id))
        except Exception as exc:
            raise HTTPException(
                503, "Redis is unavailable. Try again or use manual entry."
            ) from exc
        if record is None:
            raise HTTPException(
                410,
                "This document session has expired. Upload the document again or use manual entry.",
            )
        return record


document_service = DocumentService()
