"""SessionManager: formatos válidos, sessão única, versão e trava de importação."""

import threading

import pytest

from services.session.manager import SessionManager
from squadforce_shared.contracts import CompetitionConfig
from squadforce_shared.errors import AppError, ErrorCode


class FakeCatalog:
    def __init__(self, clubs: int = 40, ready: bool = True):
        self.clubs = clubs
        self.ready = ready

    def club_count(self):
        return self.clubs

    def club_exists(self, uid):
        return 1 <= uid <= self.clubs

    def catalog_ready(self):
        return self.ready


def cfg(**kw):
    base = {"format": "league", "num_clubs": 10, "user_club_uid": 1, "league_rounds": "double"}
    base.update(kw)
    return CompetitionConfig(**base)


@pytest.fixture
def mgr():
    return SessionManager(FakeCatalog())


@pytest.mark.parametrize("n", [2, 3, 11, 19, 20])
def test_league_accepts_2_to_20(mgr, n):
    s = mgr.create(cfg(num_clubs=n), confirm_replace=True)
    assert s.status == "active" and s.config.num_clubs == n


@pytest.mark.parametrize("n", [0, 1, 21, 32, -4])
def test_league_rejects_out_of_range(mgr, n):
    with pytest.raises(AppError) as e:
        mgr.create(cfg(num_clubs=n))
    assert e.value.code is ErrorCode.INVALID_COMPETITION_CONFIG


def test_league_requires_rounds(mgr):
    with pytest.raises(AppError) as e:
        mgr.create(cfg(league_rounds=None))
    assert e.value.details["field"] == "league_rounds"


@pytest.mark.parametrize("n", [2, 4, 8, 16, 32])
def test_cup_accepts_powers(mgr, n):
    assert mgr.create(cfg(format="cup", num_clubs=n, league_rounds=None), confirm_replace=True).config.num_clubs == n


@pytest.mark.parametrize("n", [1, 3, 6, 10, 20, 64])
def test_cup_rejects_other_sizes(mgr, n):
    with pytest.raises(AppError) as e:
        mgr.create(cfg(format="cup", num_clubs=n, league_rounds=None))
    assert e.value.code is ErrorCode.INVALID_COMPETITION_CONFIG


def test_cup_rejects_rounds(mgr):
    with pytest.raises(AppError):
        mgr.create(cfg(format="cup", num_clubs=8, league_rounds="single"))


def test_cannot_exceed_available_clubs():
    m = SessionManager(FakeCatalog(clubs=10))
    with pytest.raises(AppError) as e:
        m.create(cfg(format="cup", num_clubs=16, league_rounds=None))
    assert "10 clubes" in e.value.message


def test_user_club_must_exist(mgr):
    with pytest.raises(AppError) as e:
        mgr.create(cfg(user_club_uid=999))
    assert e.value.code is ErrorCode.CLUB_NOT_FOUND


def test_requires_imported_catalog():
    with pytest.raises(AppError) as e:
        SessionManager(FakeCatalog(ready=False)).create(cfg())
    assert e.value.code is ErrorCode.CATALOG_EMPTY


def test_single_active_session_and_replace_requires_confirmation(mgr):
    first = mgr.create(cfg())
    with pytest.raises(AppError) as e:
        mgr.create(cfg())
    assert e.value.code is ErrorCode.SESSION_ALREADY_ACTIVE
    assert mgr.active().id == first.id  # nada mudou
    second = mgr.create(cfg(), confirm_replace=True)
    assert second.id != first.id
    assert mgr.get(first.id).status == "closed"
    assert mgr.active().id == second.id


def test_close_increments_version_and_is_idempotent(mgr):
    s = mgr.create(cfg())
    assert s.version == 1
    closed = mgr.close(s.id)
    assert closed.status == "closed" and closed.version == 2 and closed.closed_at
    assert mgr.close(s.id).version == 2
    assert not mgr.has_active


def test_close_with_stale_version_conflicts(mgr):
    s = mgr.create(cfg())
    with pytest.raises(AppError) as e:
        mgr.close(s.id, expected_version=7)
    assert e.value.code is ErrorCode.VERSION_CONFLICT and e.value.retryable
    assert mgr.active().id == s.id


def test_unknown_session_is_not_found(mgr):
    with pytest.raises(AppError) as e:
        mgr.get("nao-existe")
    assert e.value.status_code == 404


def test_import_guard_blocks_during_active_session(mgr):
    mgr.create(cfg())
    with pytest.raises(AppError) as e:
        with mgr.import_guard():
            pass
    assert e.value.code is ErrorCode.IMPORT_BLOCKED_ACTIVE_COMPETITION


def test_import_guard_serializes_imports_and_blocks_session_creation(mgr):
    with mgr.import_guard():
        with pytest.raises(AppError) as e:
            with mgr.import_guard():
                pass
        assert e.value.code is ErrorCode.IMPORT_IN_PROGRESS and e.value.retryable
        with pytest.raises(AppError) as e2:
            mgr.create(cfg())
        assert e2.value.code is ErrorCode.IMPORT_IN_PROGRESS
    # liberada após a importação
    with mgr.import_guard():
        pass


def test_concurrent_creation_yields_exactly_one_session(mgr):
    results, errors = [], []
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()
        try:
            results.append(mgr.create(cfg()))
        except AppError as e:
            errors.append(e.code)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(results) == 1
    assert errors == [ErrorCode.SESSION_ALREADY_ACTIVE] * 7
