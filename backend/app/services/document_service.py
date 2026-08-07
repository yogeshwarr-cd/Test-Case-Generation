from __future__ import annotations

import io
import re
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from fastapi import HTTPException, UploadFile
from pydantic import BaseModel, Field
from pypdf import PdfReader

try:
    from docx import Document
except ImportError:  # pragma: no cover - optional dependency fallback
    Document = None

from app.core.config import settings
from app.llm.client import build_llm_client
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
            reader = PdfReader(io.BytesIO(data))
            pages = []
            for page in reader.pages:
                try:
                    page_text = page.extract_text()
                except Exception:
                    page_text = ""
                pages.append(page_text or "")
            text = "\n".join(pages)
        elif extension == ".docx":
            if not data.startswith(b"PK"):
                raise ValueError("invalid DOCX signature")
            if Document is not None:
                document = Document(io.BytesIO(data))
                lines = []
                for paragraph in document.paragraphs:
                    paragraph_text = (paragraph.text or "").strip()
                    if not paragraph_text:
                        continue
                    style_name = (getattr(paragraph.style, "name", "") or "").lower()
                    if "bullet" in style_name:
                        paragraph_text = f"• {paragraph_text}"
                    elif "number" in style_name:
                        paragraph_text = f"1. {paragraph_text}"
                    lines.append(paragraph_text)
                text = "\n".join(lines)
            else:
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
    cleaned = re.sub(
        r"^\s*(?:AC\s*[-#:]?\s*\d+\s*[:\.-]?|[-*•–—]|\(?\d+(?:\.\d+)*[.)]|[A-Za-z][.)])\s*",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()


def parse_stories(text: str) -> list[dict]:
    story_id_heading = re.compile(
        r"^\s*(?:US|STORY|USER\s+STORY|AS)\s*[-#:]?\s*(?P<id>\d+(?:\.\d+)*)\b(?:\s*[:\-]\s*(?P<body>.*))?$",
        re.IGNORECASE,
    )
    story_label = re.compile(
        r"^\s*(?:user\s*story|story)\s*[:\-]?\s*(?P<body>.*)?$",
        re.IGNORECASE,
    )
    acceptance_label = re.compile(
        r"^\s*(?:acceptance\s+criteria|acceptance\s+criterion|ac\s+criteria|\bac\b)\s*[:\-]?\s*(?P<body>.*)?$",
        re.IGNORECASE,
    )
    ac_item_header = re.compile(
        r"^\s*AC\s*[-#:]?\s*(?P<id>\d+(?:\.\d+)*)\b\s*[:\.-]?\s*(?P<body>.*)$",
        re.IGNORECASE,
    )
    bullet_line = re.compile(
        r"^\s*(?:[-*•–—]|\(?\d+(?:\.\d+)*[.)]|[A-Za-z][.)])\s+(?P<body>.+)$"
    )
    as_a_story = re.compile(
        r"^\s*as\s+an?\s+.+?\s+i\s+want\s+.+",
        re.IGNORECASE,
    )

    stories: list[dict] = []
    current: dict | None = None
    current_criterion_lines: list[str] | None = None
    in_story_section = False
    in_criteria_section = False

    def start_story(story_id: str | None = None, title: str | None = None) -> dict:
        return {
            "id": story_id or f"US-{len(stories) + 1}",
            "title": title or "",
            "text_lines": [],
            "acceptance_criteria": [],
        }

    def flush_criterion() -> None:
        nonlocal current_criterion_lines
        if current is None or current_criterion_lines is None:
            current_criterion_lines = None
            return
        criterion_text = " ".join(line.strip() for line in current_criterion_lines if line.strip()).strip()
        if criterion_text:
            current["acceptance_criteria"].append(criterion_text)
        current_criterion_lines = None

    def flush_story() -> None:
        nonlocal current, current_criterion_lines, in_story_section, in_criteria_section
        if current is None:
            return
        flush_criterion()
        story_text = "\n".join(line.strip() for line in current["text_lines"] if line.strip()).strip()
        if not story_text and current.get("title"):
            story_text = current["title"].strip()
        stories.append(
            {
                "id": current["id"],
                "text": story_text,
                "acceptance_criteria": current["acceptance_criteria"],
            }
        )
        current = None
        current_criterion_lines = None
        in_story_section = False
        in_criteria_section = False

    lines = [raw.strip() for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    for line in lines:
        if not line:
            continue

        # Check US Heading (e.g. US-1: View Practice Page or US-1)
        story_heading = story_id_heading.match(line)
        if story_heading:
            flush_story()
            story_id_num = story_heading.group("id")
            heading_body = (story_heading.group("body") or "").strip()

            clean_body = heading_body
            if clean_body:
                sub_label = story_label.match(clean_body)
                if sub_label:
                    clean_body = (sub_label.group("body") or "").strip()
                else:
                    sub_ac = acceptance_label.match(clean_body)
                    if sub_ac:
                        clean_body = ""

            current = start_story(f"US-{story_id_num}", title=clean_body)
            in_story_section = True
            in_criteria_section = False
            if clean_body and as_a_story.match(clean_body):
                current["text_lines"].append(clean_body)
            continue

        # Check Story Label (e.g. User Story: As a user...)
        story_match = story_label.match(line)
        if story_match:
            body = (story_match.group("body") or "").strip()
            if current is None:
                current = start_story()
            elif body and (current["text_lines"] or current["acceptance_criteria"]):
                flush_story()
                current = start_story()
            flush_criterion()
            in_story_section = True
            in_criteria_section = False
            if body:
                current["text_lines"].append(body)
            continue

        # Check Acceptance Criteria Header (e.g. Acceptance Criteria: or AC:)
        acceptance_match = acceptance_label.match(line)
        if acceptance_match:
            if current is not None:
                body = (acceptance_match.group("body") or "").strip()
                flush_criterion()
                in_story_section = False
                in_criteria_section = True
                if body:
                    cleaned_body = _clean_line(body)
                    if cleaned_body:
                        current_criterion_lines = [cleaned_body]
            continue

        # Check AC item header (e.g. AC-1: Valid credentials...)
        ac_item = ac_item_header.match(line)
        if ac_item:
            if current is not None:
                flush_criterion()
                in_story_section = False
                in_criteria_section = True
                body = _clean_line(ac_item.group("body") or "")
                if body:
                    current_criterion_lines = [body]
            continue

        # Check "As a user..." statement starting a new story if outside or inside criteria
        if as_a_story.match(line):
            if current is None:
                current = start_story()
                in_story_section = True
                in_criteria_section = False
                current["text_lines"].append(line)
                continue
            elif in_criteria_section:
                flush_story()
                current = start_story()
                in_story_section = True
                in_criteria_section = False
                current["text_lines"].append(line)
                continue

        if current is None:
            continue

        # If currently in Acceptance Criteria section
        if in_criteria_section:
            bullet_match = bullet_line.match(line)
            if bullet_match:
                flush_criterion()
                current_criterion_lines = [_clean_line(bullet_match.group("body"))]
                continue

            if current_criterion_lines is None:
                current_criterion_lines = [line]
            else:
                prev_line = current_criterion_lines[-1].strip()
                if prev_line and prev_line[-1] in ".!?;:" and line[0].isupper():
                    flush_criterion()
                    current_criterion_lines = [line]
                else:
                    current_criterion_lines.append(line)
            continue

        # If currently in Story section
        if in_story_section:
            bullet_match = bullet_line.match(line)
            if bullet_match and not current["text_lines"]:
                flush_criterion()
                in_story_section = False
                in_criteria_section = True
                current_criterion_lines = [_clean_line(bullet_match.group("body"))]
                continue

            current["text_lines"].append(line)

    flush_story()

    stories = [story for story in stories if story["text"] or story["acceptance_criteria"]]
    if not stories:
        raise HTTPException(
            422,
            "No user stories were found. Use a 'User Story:' heading or the 'As a ... I want ...' format.",
        )
    if any(not story["text"].strip() for story in stories):
        raise HTTPException(422, "Each user story must contain text.")
    if any(not story["acceptance_criteria"] for story in stories):
        raise HTTPException(422, "Each user story must have at least one acceptance criterion.")
    return stories


class ExtractedUserStory(BaseModel):
    id: str = Field(default="", description="User story ID, e.g., US-1")
    text: str = Field(description="User story description")
    acceptance_criteria: list[str] = Field(description="List of acceptance criteria for this user story")


class ExtractedDocumentStories(BaseModel):
    stories: list[ExtractedUserStory] = Field(description="List of extracted user stories with acceptance criteria")


async def parse_stories_with_llm(text: str) -> list[dict]:
    client = build_llm_client(task="generation")
    system_prompt = (
        "You are an expert document parser. Extract all User Stories and their corresponding "
        "Acceptance Criteria from the provided document text. "
        "Do not include document titles or administrative headers. "
        "Return schema-compliant JSON only."
    )
    user_prompt = f"Extract all user stories and acceptance criteria from this text:\n\n{text[:12000]}"
    try:
        response = await client.generate_structured_output(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=ExtractedDocumentStories,
        )
        stories = []
        for idx, item in enumerate(response.stories, 1):
            text_content = item.text.strip()
            ac_list = [ac.strip() for ac in item.acceptance_criteria if ac and ac.strip()]
            if text_content and ac_list:
                stories.append(
                    {
                        "id": f"US-{idx}",
                        "text": text_content,
                        "acceptance_criteria": ac_list,
                    }
                )
        if not stories:
            raise ValueError("LLM returned no valid user stories")
        return stories
    except Exception as exc:
        raise HTTPException(
            422,
            "No user stories were found. Use a 'User Story:' heading or the 'As a ... I want ...' format.",
        ) from exc


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
        try:
            stories = parse_stories(text)
        except HTTPException as exc:
            try:
                stories = await parse_stories_with_llm(text)
            except Exception:
                raise exc
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
