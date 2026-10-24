"""FR-002: password policy enforces a minimum length of 20 characters,
at both account creation and password change."""
from asset_dashboard.auth.passwords import hash_password, validate_password_policy, verify_password


def test_rejects_password_shorter_than_20_chars():
    errors = validate_password_policy("short-but-strong-19c")  # 21 chars, control: should pass
    assert errors == []

    errors = validate_password_policy("tooshort123")  # < 20 chars
    assert errors
    assert any("20" in e for e in errors)


def test_accepts_password_of_exactly_20_chars():
    pw = "a" * 20
    assert validate_password_policy(pw) == []


def test_hash_and_verify_roundtrip():
    pw = "correct-horse-battery-staple!!"
    hashed = hash_password(pw)
    assert hashed != pw  # never store plaintext (FR-003)
    assert verify_password(hashed, pw) is True
    assert verify_password(hashed, "wrong-password-wrong-password") is False
