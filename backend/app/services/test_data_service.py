import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

def _meaningful_words(text: str) -> set[str]:
    ignored = {
        "and", "or", "the", "a", "an", "of", "to", "in", "on", "at", "for", "with",
        "click", "press", "select", "choose", "check", "enter", "type", "fill",
        "button", "link", "field", "dropdown", "into", "from", "value",
    }
    return {w for w in re.findall(r"[A-Za-z0-9]+", text.lower()) if len(w) > 1 and w not in ignored}

class TestDataEngine:
    def __init__(self):
        pass

    def generate_value(self, data_type: str, variation: str) -> str:
        """Generate a deterministic test value based on type and variation."""
        dt = data_type.lower()
        var = variation.lower()

        if dt == "email":
            if var == "valid":
                return "test.user@example.com"
            elif var == "invalid":
                return "invalid-email-format"
            elif var == "empty":
                return ""
            elif var == "boundary":
                return "a@b.co"
            elif var == "duplicate":
                return "test.user@example.com"
            elif var == "special-character":
                return "test+special!#$@example.com"
            else:
                return "test.user@example.com"

        elif dt == "phone":
            if var == "valid":
                return "1234567890"
            elif var == "invalid":
                return "123-abc-456"
            elif var == "empty":
                return ""
            elif var == "boundary":
                return "1" * 7
            elif var == "duplicate":
                return "1234567890"
            elif var == "special-character":
                return "+1 (234) 567-8901 ext #123"
            else:
                return "1234567890"

        elif dt == "number":
            if var == "valid":
                return "42"
            elif var == "invalid":
                return "forty-two"
            elif var == "empty":
                return ""
            elif var == "boundary":
                return "999999"
            elif var == "duplicate":
                return "42"
            elif var == "special-character":
                return "42.00%"
            else:
                return "42"

        elif dt == "date/time":
            if var == "valid":
                return "2026-08-27"
            elif var == "invalid":
                return "2026-13-45"
            elif var == "empty":
                return ""
            elif var == "boundary":
                return "1970-01-01"
            elif var == "duplicate":
                return "2026-08-27"
            elif var == "special-character":
                return "2026-08-27T22:29:42+05:30"
            else:
                return "2026-08-27"

        elif dt == "address":
            if var == "valid":
                return "123 Main St, Springfield"
            elif var == "invalid":
                return "St"
            elif var == "empty":
                return ""
            elif var == "boundary":
                return "1 St"
            elif var == "duplicate":
                return "123 Main St, Springfield"
            elif var == "special-character":
                return "123 Main St #4B & Blvd. / Suite 12!"
            else:
                return "123 Main St, Springfield"

        elif dt == "ids":
            if var == "valid":
                return "ID-98765"
            elif var == "invalid":
                return "id"
            elif var == "empty":
                return ""
            elif var == "boundary":
                return "ID-999999999999999999"
            elif var == "duplicate":
                return "ID-98765"
            elif var == "special-character":
                return "ID_#987-abc"
            else:
                return "ID-98765"

        else: # text/name or fallback
            if var == "valid":
                return "John Doe"
            elif var == "invalid":
                return "J"
            elif var == "empty":
                return ""
            elif var == "boundary":
                return "A" * 255
            elif var == "duplicate":
                return "John Doe"
            elif var == "special-character":
                return "John O'Connor-Smith!@#"
            else:
                return "John Doe"

    def validate_value(self, data_type: str, variation: str, value: str) -> bool:
        """Validate value format according to its type and variation."""
        dt = data_type.lower()
        var = variation.lower()

        if var == "empty":
            return value == ""

        if dt == "email":
            if var in ("valid", "duplicate", "boundary", "special-character"):
                return "@" in value and "." in value.split("@")[-1]
            elif var == "invalid":
                return "@" not in value or "." not in value.split("@")[-1]

        elif dt == "phone":
            if var in ("valid", "duplicate", "boundary"):
                digits = "".join(c for c in value if c.isdigit())
                return len(digits) >= 7
            elif var == "invalid":
                digits = "".join(c for c in value if c.isdigit())
                return len(digits) < 7

        elif dt == "number":
            if var in ("valid", "duplicate", "boundary"):
                try:
                    float(value)
                    return True
                except ValueError:
                    return False
            elif var == "invalid":
                try:
                    float(value)
                    return False
                except ValueError:
                    return True

        elif dt == "date/time":
            if var in ("valid", "duplicate", "boundary"):
                return bool(re.match(r"^\d{4}-\d{2}-\d{2}", value))
            elif var == "invalid":
                return not re.match(r"^\d{4}-\d{2}-\d{2}", value)

        return True

    def determine_data_type(self, element: Dict[str, Any], action: str) -> str:
        """Infer required test data type from crawl element properties and step action."""
        input_type = (element.get("input_type") or "").lower()
        tag = (element.get("tag") or "").lower()
        name = (element.get("name") or "").lower()
        label = (element.get("label") or "").lower()
        placeholder = (element.get("placeholder") or "").lower()
        elem_id = (element.get("element_id") or "").lower()
        
        combo = f"{name} {label} {placeholder} {elem_id}".strip()
        
        if input_type == "email" or "email" in combo:
            return "email"
        elif input_type in ("tel", "phone") or "phone" in combo or "mobile" in combo or "telephone" in combo:
            return "phone"
        elif input_type in ("number", "range") or "number" in combo or "amount" in combo or "price" in combo or "quantity" in combo:
            return "number"
        elif input_type in ("date", "time", "datetime-local") or "date" in combo or "time" in combo or "dob" in combo or "birth" in combo:
            return "date/time"
        elif "address" in combo or "street" in combo or "zip" in combo or "postal" in combo or "city" in combo or "state" in combo:
            return "address"
        elif "id" in combo or "uuid" in combo or "code" in combo or "identifier" in combo:
            return "ids"
        elif "name" in combo or "user" in combo or "first" in combo or "last" in combo:
            return "text/name"
        else:
            return "text/name"

    def determine_variation(self, test_case: Dict[str, Any], action: str) -> str:
        """Determine what variation (valid, invalid, empty, etc.) is appropriate based on test case context."""
        title = (test_case.get("title") or "").lower()
        desc = (test_case.get("description") or "").lower()
        act = action.lower()
        
        combo = f"{title} {desc} {act}"
        
        if "invalid" in combo:
            return "invalid"
        elif "empty" in combo or "blank" in combo or "missing" in combo or "clear" in combo:
            return "empty"
        elif "boundary" in combo or "limit" in combo or "max" in combo or "min" in combo:
            return "boundary"
        elif "duplicate" in combo or "existing" in combo or "already" in combo:
            return "duplicate"
        elif "special" in combo or "character" in combo or "unicode" in combo or "symbol" in combo:
            return "special-character"
        else:
            return "valid"

    def is_sensitive_field(self, element: Dict[str, Any]) -> bool:
        """Check if the field is a password, secret, token, or API key."""
        input_type = (element.get("input_type") or "").lower()
        name = (element.get("name") or "").lower()
        label = (element.get("label") or "").lower()
        placeholder = (element.get("placeholder") or "").lower()
        elem_id = (element.get("element_id") or "").lower()
        
        combo = f"{name} {label} {placeholder} {elem_id}".strip()
        
        return input_type == "password" or any(token in combo for token in ("password", "secret", "token", "apikey", "api_key", "credential"))

    def get_test_data_for_case(
        self,
        test_case: Dict[str, Any],
        discovered_elements: List[Dict[str, Any]],
        credentials: Any = None,
        all_elements: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[Dict[str, Any], str | None]:
        """
        Analyze a test case and generate/reuse test data.
        Returns:
            (test_data_map, blocked_reason)
        """
        test_data_map = {}
        blocked_reason = None

        identities = []
        for element in (discovered_elements or []):
            words = _meaningful_words(
                " ".join(
                    str(element.get(key) or "")
                    for key in ("name", "label", "test_id", "placeholder", "visible_text")
                )
            )
            identities.append((element, words))

        all_identities = []
        if all_elements:
            for element in all_elements:
                words = _meaningful_words(
                    " ".join(
                        str(element.get(key) or "")
                        for key in ("name", "label", "test_id", "placeholder", "visible_text")
                    )
                )
                all_identities.append((element, words))

        existing_data = test_case.get("test_data") or {}

        for step in test_case.get("steps", []):
            action = str(step.get("action") or "")
            lowered = action.lower()
            
            if not any(token in lowered for token in ("enter", "type", "fill")):
                continue

            phrase = self._locator_phrase(action)
            action_words = _meaningful_words(action)

            # Match to discovered elements
            best_element = None
            best_score = 0
            for element, words in identities:
                score = len(action_words & words)
                if score > best_score:
                    best_score = score
                    best_element = element

            # Fallback to all site elements (cross-page inventory match)
            if not best_element and all_identities:
                for element, words in all_identities:
                    score = len(action_words & words)
                    if score > best_score:
                        best_score = score
                        best_element = element

            if not best_element:
                # Handle auth credentials gracefully if mentioned in action
                if any(k in lowered for k in ("username", "user", "email", "login", "password")):
                    best_element = {
                        "tag": "input",
                        "name": "password" if "password" in lowered else "username",
                        "input_type": "password" if "password" in lowered else "text",
                    }
                else:
                    blocked_reason = f"Required input field matching '{phrase}' was not found in crawl evidence."
                    return {}, blocked_reason

            field_key = phrase or best_element.get("name") or best_element.get("label") or "input_field"
            
            data_type = self.determine_data_type(best_element, action)
            variation = self.determine_variation(test_case, action)
            sensitive = self.is_sensitive_field(best_element)

            reused_val = None
            status = "generated"

            if field_key in existing_data:
                reused_val = existing_data[field_key]
                if isinstance(reused_val, dict):
                    reused_val = reused_val.get("value")
                status = "reused"

            value = ""
            if sensitive:
                status = "reused" if credentials else "generated"
                ident_val = None
                pass_val = None
                if credentials:
                    if hasattr(credentials, "get_identifier") and credentials.get_identifier:
                        ident_val = credentials.get_identifier
                    elif isinstance(credentials, dict):
                        ident_val = credentials.get("identifier") or credentials.get("email") or credentials.get("username")
                    if hasattr(credentials, "password") and credentials.password:
                        pass_val = credentials.password.get_secret_value() if hasattr(credentials.password, "get_secret_value") else str(credentials.password)
                    elif isinstance(credentials, dict):
                        p = credentials.get("password")
                        pass_val = p.get_secret_value() if hasattr(p, "get_secret_value") else (str(p) if p else None)

                is_password_field = "password" in field_key.lower() or "password" in (best_element.get("input_type") or "").lower()
                
                if is_password_field:
                    if pass_val:
                        value = pass_val
                    else:
                        is_login_tc = any(token in test_case.get("title", "").lower() for token in ("login", "signin", "sign-in", "log-in"))
                        if is_login_tc:
                            blocked_reason = "Authentication credentials are required but were not provided."
                            return {}, blocked_reason
                        else:
                            value = "Password123!"
                            status = "generated"
                else:
                    if ident_val:
                        value = ident_val
                    else:
                        value = "test.user@example.com"
                        status = "generated"
            else:
                if reused_val is not None:
                    value = reused_val
                else:
                    value = self.generate_value(data_type, variation)

            valid = self.validate_value(data_type, variation, value)
            if not valid and status == "generated":
                value = self.generate_value(data_type, "valid")

            test_data_map[field_key] = {
                "value": value,
                "data_type": data_type,
                "variation": variation,
                "status": status,
                "sensitive": sensitive
            }

        return test_data_map, None

    @staticmethod
    def _locator_phrase(action: str) -> str:
        ignored = {
            "click", "press", "select", "choose", "check", "enter", "type",
            "fill", "button", "link", "field", "dropdown", "into", "from",
            "with", "the", "on", "in", "value",
        }
        quoted = re.findall(r"['\"]([^'\"]+)['\"]", action)
        lowered = action.lower()
        target = (
            quoted[0]
            if quoted and any(t in lowered for t in ("click", "press"))
            else re.sub(r"['\"][^'\"]+['\"]", "", action)
        )
        words = [
            w for w in re.findall(r"[A-Za-z0-9]+", target)
            if len(w) > 1 and w.lower() not in ignored
        ]
        return " ".join(words)

test_data_engine = TestDataEngine()
