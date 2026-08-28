import pytest
from app.services.test_data_service import test_data_engine
from app.services.automation_service import _python_source
from app.schemas.automation_schema import PlaywrightAuthentication
from pydantic import SecretStr

def test_determine_data_type():
    el_email = {"tag": "input", "input_type": "text", "name": "user_email", "label": "Email Address"}
    assert test_data_engine.determine_data_type(el_email, "") == "email"

    el_phone = {"tag": "input", "input_type": "tel", "name": "phone_num"}
    assert test_data_engine.determine_data_type(el_phone, "") == "phone"

    el_text = {"tag": "input", "input_type": "text", "name": "comment"}
    assert test_data_engine.determine_data_type(el_text, "") == "text/name"

def test_determine_variation():
    tc_invalid = {"title": "Submit Form with invalid email", "description": "Ensure form validation works"}
    assert test_data_engine.determine_variation(tc_invalid, "Enter email") == "invalid"

    tc_boundary = {"title": "Submit boundary quantity", "description": "Ensure boundary limits"}
    assert test_data_engine.determine_variation(tc_boundary, "Enter qty") == "boundary"

    tc_valid = {"title": "Normal flow", "description": "Happy path"}
    assert test_data_engine.determine_variation(tc_valid, "Enter value") == "valid"

def test_generate_and_validate():
    val = test_data_engine.generate_value("email", "valid")
    assert test_data_engine.validate_value("email", "valid", val) is True
    
    val_inv = test_data_engine.generate_value("email", "invalid")
    assert test_data_engine.validate_value("email", "invalid", val_inv) is True

    val_phone = test_data_engine.generate_value("phone", "boundary")
    assert len(val_phone) >= 7

def test_no_data_required():
    tc = {
        "title": "Click Login",
        "steps": [
            {"step_number": 1, "action": "Click the login button", "expected_result": "Login form shown"}
        ]
    }
    td, blocked = test_data_engine.get_test_data_for_case(tc, [])
    assert td == {}
    assert blocked is None

def test_data_required_valid_generated():
    tc = {
        "title": "Login Happy Path",
        "steps": [
            {"step_number": 1, "action": 'Fill in the "email" field with email', "expected_result": "Value filled"}
        ]
    }
    elements = [
        {"tag": "input", "input_type": "email", "name": "email", "label": "Email Address"}
    ]
    td, blocked = test_data_engine.get_test_data_for_case(tc, elements)
    assert blocked is None
    assert "email" in td
    assert td["email"]["data_type"] == "email"
    assert td["email"]["variation"] == "valid"
    assert td["email"]["status"] == "generated"
    assert "@" in td["email"]["value"]

def test_data_reused():
    tc = {
        "title": "Login with configured email",
        "steps": [
            {"step_number": 1, "action": 'Fill in the "email" field with email', "expected_result": "Value filled"}
        ],
        "test_data": {
            "email": "configured.user@example.com"
        }
    }
    elements = [
        {"tag": "input", "input_type": "email", "name": "email", "label": "Email Address"}
    ]
    td, blocked = test_data_engine.get_test_data_for_case(tc, elements)
    assert blocked is None
    assert td["email"]["value"] == "configured.user@example.com"
    assert td["email"]["status"] == "reused"

def test_missing_crawl_evidence_blocked():
    tc = {
        "title": "Fill age",
        "steps": [
            {"step_number": 1, "action": 'Fill in the "age" field', "expected_result": "Value filled"}
        ]
    }
    elements = [
        {"tag": "input", "input_type": "text", "name": "username"}
    ]
    td, blocked = test_data_engine.get_test_data_for_case(tc, elements)
    assert blocked is not None
    assert "not found in crawl evidence" in blocked

def test_credentials_reused_and_masked():
    tc = {
        "title": "Perform login",
        "steps": [
            {"step_number": 1, "action": 'Fill password field', "expected_result": "Filled"}
        ]
    }
    elements = [
        {"tag": "input", "input_type": "password", "name": "password"}
    ]
    credentials = PlaywrightAuthentication(
        auth_mode="credentials",
        email="real.user@example.com",
        password=SecretStr("supersecret123")
    )
    td, blocked = test_data_engine.get_test_data_for_case(tc, elements, credentials=credentials)
    assert blocked is None
    assert td["password"]["value"] == "supersecret123"
    assert td["password"]["sensitive"] is True
    assert td["password"]["status"] == "reused"

def test_sensitive_login_blocked_if_no_credentials():
    tc = {
        "title": "Submit login form",
        "steps": [
            {"step_number": 1, "action": 'Fill password field', "expected_result": "Filled"}
        ]
    }
    elements = [
        {"tag": "input", "input_type": "password", "name": "password"}
    ]
    td, blocked = test_data_engine.get_test_data_for_case(tc, elements, credentials=None)
    assert blocked is not None
    assert "credentials are required" in blocked

def test_python_source_embeds_test_data():
    tc = {
        "test_case_id": "TC-TEST-1",
        "title": "Fill form",
        "steps": [
            {"step_number": 1, "action": "Fill in the name", "expected_result": "Success"}
        ]
    }
    td = {
        "name": {
            "value": "Jane Doe",
            "data_type": "text/name",
            "variation": "valid",
            "status": "generated",
            "sensitive": False
        }
    }
    source = _python_source(tc, "https://example.com/", test_data=td)
    assert "TEST_DATA" in source
    assert "Jane Doe" in source

def test_python_source_masks_sensitive_credentials():
    tc = {
        "test_case_id": "TC-TEST-2",
        "title": "Fill password",
        "steps": [
            {"step_number": 1, "action": "Fill the password field", "expected_result": "Success"}
        ]
    }
    td = {
        "password": {
            "value": "mypass123",
            "data_type": "text/name",
            "variation": "valid",
            "status": "generated",
            "sensitive": True
        }
    }
    source = _python_source(tc, "https://example.com/", test_data=td)
    assert "mypass123" not in source
    assert "PLAYWRIGHT_PASSWORD" in source
    assert "import os" in source
