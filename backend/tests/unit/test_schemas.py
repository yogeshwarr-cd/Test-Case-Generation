from app.schemas.common import InputPayload


def test_input_payload_defaults_are_not_shared() -> None:
    first = InputPayload()
    second = InputPayload()

    first.user_stories.append({"id": "US-1"})

    assert second.user_stories == []
