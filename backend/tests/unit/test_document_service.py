import io
import zipfile

import pytest
from fastapi import HTTPException

from app.services.document_service import extract_text, parse_stories, payload_from_stories


SAMPLE = """User Story: As a customer, I want to sign in
Acceptance Criteria:
- Valid credentials open the dashboard
- Invalid credentials show an error

Story: As an administrator, I want to lock accounts
AC:
1. Five failures lock the account
"""


def test_parse_stories_preserves_criteria_relationships():
    stories = parse_stories(SAMPLE)
    payload = payload_from_stories(stories)

    assert len(stories) == 2
    assert stories[0]["acceptance_criteria"] == [
        "Valid credentials open the dashboard",
        "Invalid credentials show an error",
    ]
    assert payload["acceptance_criteria"][0]["user_story_id"] == "US-1"
    assert payload["acceptance_criteria"][-1]["user_story_id"] == "US-2"


def test_parse_rejects_missing_stories_and_missing_criteria():
    with pytest.raises(HTTPException, match="No user stories"):
        parse_stories("Acceptance Criteria: It works")
    with pytest.raises(HTTPException, match="at least one acceptance"):
        parse_stories("User Story: As a user I want access")


def test_extract_txt_validates_content_and_type():
    assert extract_text("stories.txt", "text/plain", SAMPLE.encode()) == SAMPLE.strip()
    with pytest.raises(HTTPException, match="Unsupported"):
        extract_text("stories.exe", "application/octet-stream", b"MZ")
    with pytest.raises(HTTPException, match="could not be parsed"):
        extract_text("stories.txt", "text/plain", b"\x00binary")


def test_extract_docx_without_writing_uploaded_bytes_to_disk():
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body><w:p><w:r><w:t>User Story: Login</w:t></w:r></w:p></w:body></w:document>'
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
    assert extract_text(
        "stories.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        output.getvalue(),
    ) == "User Story: Login"
