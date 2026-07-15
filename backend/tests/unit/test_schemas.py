from app.schemas.common import InputPayload
from app.core.config import Settings


def test_cors_origins_accept_comma_separated_values() -> None:
    settings = Settings(
        _env_file=None,
        cors_origins="http://localhost:3000,http://localhost:5173",
    )

    assert settings.cors_origins == [
        "http://localhost:3000",
        "http://localhost:5173",
    ]


def test_cors_origins_accept_json_array() -> None:
    settings = Settings(
        _env_file=None,
        cors_origins='["http://localhost:3000","http://localhost:5173"]',
    )

    assert settings.cors_origins == [
        "http://localhost:3000",
        "http://localhost:5173",
    ]


def test_cors_origins_accept_single_value() -> None:
    settings = Settings(_env_file=None, cors_origins="http://localhost:3000")

    assert settings.cors_origins == ["http://localhost:3000"]


def test_input_payload_defaults_are_not_shared() -> None:
    first = InputPayload()
    second = InputPayload()

    first.user_stories.append({"id": "US-1"})

    assert second.user_stories == []
