"""Guards for the seed script's published demo credentials."""

from pydantic import EmailStr, TypeAdapter

from app import seed

_email_adapter = TypeAdapter(EmailStr)


def test_demo_email_is_loginable() -> None:
    """The seeded demo account must pass the same EmailStr validation the login
    endpoint applies — otherwise the printed credentials can't actually log in."""
    _email_adapter.validate_python(seed.DEMO_EMAIL)


def test_demo_password_meets_min_length() -> None:
    # Registration enforces an 8-char minimum; keep the demo password consistent.
    assert len(seed.DEMO_PASSWORD) >= 8
