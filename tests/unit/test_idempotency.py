"""IdempotencyStore: execução única, replay, reuso indevido de chave e expiração."""

import threading

import pytest

from services.gateway.idempotency import IdempotencyStore, validate_key
from squadforce_shared.errors import AppError, ErrorCode


def test_same_key_same_request_runs_once():
    store, calls = IdempotencyStore(), []

    def fn():
        calls.append(1)
        return 201, {"n": len(calls)}

    assert store.execute("s", "chave-0001", "fp", fn) == (201, {"n": 1}, False)
    assert store.execute("s", "chave-0001", "fp", fn) == (201, {"n": 1}, True)
    assert len(calls) == 1


def test_same_key_different_request_is_rejected():
    store = IdempotencyStore()
    store.execute("s", "chave-0001", "fp1", lambda: (200, {}))
    with pytest.raises(AppError) as e:
        store.execute("s", "chave-0001", "fp2", lambda: (200, {}))
    assert e.value.code is ErrorCode.IDEMPOTENCY_KEY_REUSED


def test_scopes_are_independent():
    store = IdempotencyStore()
    store.execute("a", "chave-0001", "fp1", lambda: (200, {"a": 1}))
    assert store.execute("b", "chave-0001", "fp2", lambda: (200, {"b": 1}))[1] == {"b": 1}


def test_retryable_errors_are_not_memoized():
    store, attempts = IdempotencyStore(), []

    def flaky():
        attempts.append(1)
        if len(attempts) == 1:
            raise AppError(409, ErrorCode.IMPORT_IN_PROGRESS, "ocupado", retryable=True)
        return 200, {"ok": True}

    with pytest.raises(AppError):
        store.execute("s", "chave-0001", "fp", flaky)
    assert store.execute("s", "chave-0001", "fp", flaky) == (200, {"ok": True}, False)


def test_validation_errors_are_memoized():
    store, attempts = IdempotencyStore(), []

    def invalid():
        attempts.append(1)
        raise AppError(422, ErrorCode.VALIDATION_ERROR, "inválido")

    with pytest.raises(AppError):
        store.execute("s", "chave-0001", "fp", invalid)
    for _ in range(2):  # repetições devolvem a mesma resposta 422 sem reexecutar
        status, body, replayed = store.execute("s", "chave-0001", "fp", invalid)
        assert status == 422 and replayed is True and body["error"]["code"] == "VALIDATION_ERROR"
    assert len(attempts) == 1


def test_concurrent_duplicate_is_reported_in_progress():
    store = IdempotencyStore()
    started, release = threading.Event(), threading.Event()

    def slow():
        started.set()
        release.wait(5)
        return 200, {}

    t = threading.Thread(target=store.execute, args=("s", "chave-0001", "fp", slow))
    t.start()
    started.wait(5)
    with pytest.raises(AppError) as e:
        store.execute("s", "chave-0001", "fp", slow)
    assert e.value.code is ErrorCode.REQUEST_IN_PROGRESS and e.value.retryable
    release.set()
    t.join()


def test_entries_expire():
    now = [0.0]
    store = IdempotencyStore(ttl_seconds=10, clock=lambda: now[0])
    store.execute("s", "chave-0001", "fp", lambda: (200, {"v": 1}))
    now[0] = 11
    assert store.execute("s", "chave-0001", "fp", lambda: (200, {"v": 2}))[1] == {"v": 2}


@pytest.mark.parametrize("bad", [None, "", "curta", "x" * 129, "com espaço 123"])
def test_key_validation(bad):
    with pytest.raises(AppError) as e:
        validate_key(bad)
    assert e.value.code is ErrorCode.IDEMPOTENCY_KEY_REQUIRED
