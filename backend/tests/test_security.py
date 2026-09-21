from __future__ import annotations

import uuid

from app import security


def test_a_password_hashes_to_something_that_is_not_the_password():
    hashed = security.hash_password("correct horse battery staple")
    assert "correct horse battery staple" not in hashed


def test_the_right_password_verifies():
    hashed = security.hash_password("s3cret-password")
    assert security.verify_password("s3cret-password", hashed) is True


def test_the_wrong_password_does_not_verify():
    hashed = security.hash_password("s3cret-password")
    assert security.verify_password("wrong-password", hashed) is False


def test_the_same_password_hashes_differently_each_time():
    assert security.hash_password("shared") != security.hash_password("shared")


def test_a_malformed_hash_fails_closed_rather_than_raising():
    assert security.verify_password("anything", "not-a-real-hash") is False


def test_a_token_round_trips_its_claims():
    user_id = uuid.uuid4()
    token = security.create_token(user_id, "alice")

    claims = security.verify_token(token)

    assert claims == {"user_id": user_id, "username": "alice"}


def test_a_tampered_token_is_rejected():
    token = security.create_token(uuid.uuid4(), "alice")
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")

    assert security.verify_token(tampered) is None


def test_garbage_is_rejected_without_raising():
    assert security.verify_token("not.a.valid.token") is None
    assert security.verify_token("") is None


def test_an_expired_token_is_rejected(monkeypatch):
    token = security.create_token(uuid.uuid4(), "alice")
    real_time = security.time.time()
    monkeypatch.setattr(security.time, "time", lambda: real_time + 10**9)

    assert security.verify_token(token) is None
