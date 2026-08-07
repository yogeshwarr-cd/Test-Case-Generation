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


def test_parse_stories_heading_structure_and_multiline_criteria():
    doc = """
Practice Page Requirements Document

US-1: View Practice Page
User Story
As a user, I want to access the Practice page so that I can interact with the available automation testing elements.

Acceptance Criteria
- The Practice page loads successfully.
- The page title is displayed correctly.
- All major UI sections are visible.

US-2: Verify Page Content
User Story
As a user, I want to view all practice sections and UI elements so that I can perform different testing activities.

Acceptance Criteria
- Practice components are displayed.
- No UI section is missing.
- The page is scrollable without layout issues.
"""
    stories = parse_stories(doc)
    assert len(stories) == 2

    assert stories[0]["id"] == "US-1"
    assert stories[0]["text"] == "As a user, I want to access the Practice page so that I can interact with the available automation testing elements."
    assert stories[0]["acceptance_criteria"] == [
        "The Practice page loads successfully.",
        "The page title is displayed correctly.",
        "All major UI sections are visible.",
    ]

    assert stories[1]["id"] == "US-2"
    assert stories[1]["text"] == "As a user, I want to view all practice sections and UI elements so that I can perform different testing activities."
    assert stories[1]["acceptance_criteria"] == [
        "Practice components are displayed.",
        "No UI section is missing.",
        "The page is scrollable without layout issues.",
    ]


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

