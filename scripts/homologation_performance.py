"""Medições de desempenho da homologação (Entrega 9). Critérios em docs/homologacao/criterios.md (definidos antes).

Sobe gateways REAIS em portas livres com bancos temporários (nunca usa o banco/servidor do usuário):
  A) relógio real: inicialização, leituras, lances no leilão;
  B) relógio 25× (somente teste) e 4 processos de partidas: mercado, Liga 20 clubes turno e returno via API,
     fase de Copa com 32 clubes, memória do gateway e dos workers;
  C) em processo: ganho do paralelismo (1 × 8 trabalhadores) numa fase de 16 partidas.
O leilão usa o MODELO FALSO de testes (fórmulas reais pendentes). Gera docs/homologacao/desempenho.md.
"""

from __future__ import annotations

import ctypes
import json
import os
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
XLSX = ROOT / "Dados" / "jogadores.xlsx"
RESULTS: dict = {}


# ------------------------------------------------------------------ utilidades
def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def rss_mb(pid: int) -> float:
    """Working set do processo (Windows: psapi; Linux: /proc)."""
    if os.name == "nt":
        class PMC(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong), ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
        h = ctypes.windll.kernel32.OpenProcess(0x0410, False, pid)
        if not h:
            return 0.0
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb)
        ctypes.windll.kernel32.CloseHandle(h)
        return pmc.WorkingSetSize / 2**20
    with open(f"/proc/{pid}/status") as f:
        for line in f:
            if line.startswith("VmRSS"):
                return int(line.split()[1]) / 1024
    return 0.0


def children(pid: int) -> list[int]:
    if os.name == "nt":
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              f"(Get-CimInstance Win32_Process -Filter 'ParentProcessId={pid}').ProcessId"],
                             capture_output=True, text=True).stdout
        return [int(x) for x in out.split() if x.strip().isdigit()]
    return []


def tree_mb(pid: int) -> dict:
    """Memória da ÁRVORE do servidor: no Windows o python do .venv é um lançador; o gateway real é filho dele e
    os processos de partidas são netos. Soma tudo e detalha por processo."""
    procs, todo = [], [pid]
    while todo:
        p = todo.pop()
        procs.append((p, round(rss_mb(p), 1)))
        todo.extend(children(p))
    return {"total_mb": round(sum(m for _, m in procs), 1), "processes_mb": [m for _, m in procs]}


class Server:
    def __init__(self, name: str, env: dict):
        self.port = free_port()
        self.tmp = tempfile.mkdtemp(prefix=f"sf-perf-{name}-")
        e = {**os.environ, "SQUADFORCE_DB_PATH": str(Path(self.tmp) / "perf.db"),
             "PYTHONPATH": str(ROOT / "tests"), **env}
        t0 = time.perf_counter()
        self.proc = subprocess.Popen([PY, "-m", "services.gateway", "--port", str(self.port)], cwd=ROOT, env=e,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.base = f"http://127.0.0.1:{self.port}"
        while True:
            try:
                if urllib.request.urlopen(f"{self.base}/api/health", timeout=1).status == 200:
                    break
            except Exception:
                if time.perf_counter() - t0 > 60:
                    raise RuntimeError("gateway não iniciou")
                time.sleep(0.05)
        self.startup = time.perf_counter() - t0

    def req(self, method: str, path: str, body=None, form_file: Path | None = None, idem=True):
        headers = {}
        data = None
        if form_file is not None:
            boundary = uuid.uuid4().hex
            data = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{form_file.name}\"\r\n"
                    "Content-Type: application/octet-stream\r\n\r\n").encode() + form_file.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        elif body is not None or method == "POST":
            data = json.dumps(body or {}).encode()
            headers["Content-Type"] = "application/json"
        if method == "POST" and idem:
            headers["Idempotency-Key"] = uuid.uuid4().hex
        r = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(r, timeout=600) as resp:
                payload = json.loads(resp.read() or b"null")
                status = resp.status
        except urllib.error.HTTPError as err:
            payload, status = json.loads(err.read() or b"null"), err.code
        return status, payload, (time.perf_counter() - t0) * 1000

    def stop(self) -> None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"], capture_output=True)
        else:
            self.proc.kill()
        self.proc.wait(10)


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


def lat(xs: list[float]) -> dict:
    return {"n": len(xs), "p50_ms": round(pct(xs, 50), 2), "p95_ms": round(pct(xs, 95), 2), "max_ms": round(max(xs), 2)}


def wait_phase(srv: Server, sid: str, phase: str, timeout=600):
    end = time.time() + timeout
    while time.time() < end:
        if srv.req("GET", f"/api/sessions/{sid}")[1]["phase"] == phase:
            return
        time.sleep(0.2)
    raise RuntimeError(f"fase {phase} não alcançada")


# ------------------------------------------------------------------ A: relógio real
def part_a() -> None:
    srv = Server("a", {"SQUADFORCE_MATCH_EXECUTOR": "process", "SQUADFORCE_MATCH_WORKERS": "4"})
    try:
        RESULTS["startup_s"] = round(srv.startup, 3)
        t0 = time.perf_counter()
        srv.req("POST", "/api/imports/clubs", form_file=XLSX)
        srv.req("POST", "/api/imports/players", form_file=XLSX)
        RESULTS["import_both_bases_s"] = round(time.perf_counter() - t0, 3)
        RESULTS["get_health"] = lat([srv.req("GET", "/api/health")[2] for _ in range(200)])
        RESULTS["get_catalog_players"] = lat([srv.req("GET", "/api/catalog/players?limit=50")[2] for _ in range(100)])
        _, s, _ = srv.req("POST", "/api/sessions", {"format": "league", "num_clubs": 20, "user_club_uid": 322, "league_rounds": "double"})
        sid = s["id"]
        RESULTS["get_session"] = lat([srv.req("GET", f"/api/sessions/{sid}")[2] for _ in range(200)])
        _, st, _ = srv.req("POST", f"/api/sessions/{sid}/auction/start")
        bids, statuses, reads = [], [], []
        deadline = time.time() + 40
        while time.time() < deadline and len(bids) < 120:
            _, st, ms = srv.req("GET", f"/api/sessions/{sid}/auction")
            reads.append(ms)
            rnd = st.get("round")
            if not rnd:
                continue
            for p in rnd["players"][:2]:
                code, _, ms = srv.req("POST", f"/api/sessions/{sid}/auction/bids",
                                      {"player_id": p["unique_id"], "amount": p["minimum_bid"] + 100_000 * len(bids), "round_number": rnd["number"]})
                bids.append(ms)
                statuses.append(code)
        RESULTS["post_bid"] = {**lat(bids), "status_counts": {str(k): statuses.count(k) for k in sorted(set(statuses))}}
        RESULTS["get_auction"] = lat(reads)
        RESULTS["memory_after_a"] = tree_mb(srv.proc.pid)
    finally:
        srv.stop()


# ------------------------------------------------------------------ B: jornada acelerada (somente teste)
def part_b() -> None:
    srv = Server("b", {"SQUADFORCE_CLOCK_SCALE": "25", "SQUADFORCE_MATCH_EXECUTOR": "process", "SQUADFORCE_MATCH_WORKERS": "4"})
    try:
        srv.req("POST", "/api/imports/clubs", form_file=XLSX)
        srv.req("POST", "/api/imports/players", form_file=XLSX)
        _, s, _ = srv.req("POST", "/api/sessions", {"format": "league", "num_clubs": 20, "user_club_uid": 322, "league_rounds": "double"})
        sid = s["id"]
        srv.req("POST", f"/api/sessions/{sid}/auction/start")
        wait_phase(srv, sid, "squad_completion")
        srv.req("POST", f"/api/sessions/{sid}/trading/start")
        _, squads, _ = srv.req("GET", f"/api/sessions/{sid}/trading/squads")
        mine = next(x for x in squads if x["is_user"])
        others = [x for x in squads if not x["is_user"]]
        props, cancels = [], []
        for i in range(30):
            o = others[i % len(others)]
            code, p, ms = srv.req("POST", f"/api/sessions/{sid}/trading/proposals", {
                "recipient_club_uid": o["club_uid"], "offered_player_id": mine["players"][i % 18]["unique_id"],
                "requested_player_id": o["players"][i % 18]["unique_id"], "money": 0})
            props.append(ms)
            if code == 200 and p.get("status") == "pending":
                _, _, ms = srv.req("POST", f"/api/sessions/{sid}/trading/proposals/{p['id']}/cancel")
                cancels.append(ms)
        RESULTS["post_proposal"] = lat(props)
        RESULTS["post_proposal_cancel"] = lat(cancels) if cancels else {"n": 0}
        wait_phase(srv, sid, "competition")
        srv.req("POST", f"/api/sessions/{sid}/season/start")
        rounds, t_all = [], time.perf_counter()
        while True:
            code, st, ms = srv.req("POST", f"/api/sessions/{sid}/season/play")
            if code != 200:
                raise RuntimeError(st)
            rounds.append(ms)
            _, st, _ = srv.req("POST", f"/api/sessions/{sid}/season/advance")
            if st["phase"] == "finished":
                break
        RESULTS["league20_round_play_ms"] = lat(rounds)
        RESULTS["league20_full_season_s"] = round(time.perf_counter() - t_all, 2)
        RESULTS["league20_matches"] = len(rounds) * 10
        RESULTS["get_season_stats"] = lat([srv.req("GET", f"/api/sessions/{sid}/season/stats")[2] for _ in range(50)])
        RESULTS["get_season_summary"] = lat([srv.req("GET", f"/api/sessions/{sid}/season/summary")[2] for _ in range(50)])
        RESULTS["memory_after_league20"] = tree_mb(srv.proc.pid)
        # Copa com 32 clubes (substitui a sessão, com confirmação)
        _, s, _ = srv.req("POST", "/api/sessions", {"format": "cup", "num_clubs": 32, "user_club_uid": 322, "league_rounds": None, "confirm_replace": True})
        sid = s["id"]
        srv.req("POST", f"/api/sessions/{sid}/auction/start")
        wait_phase(srv, sid, "squad_completion")
        srv.req("POST", f"/api/sessions/{sid}/trading/start")
        wait_phase(srv, sid, "competition")
        srv.req("POST", f"/api/sessions/{sid}/season/start")
        phases = []
        while True:
            code, st, ms = srv.req("POST", f"/api/sessions/{sid}/season/play")
            phases.append((len(st["fixtures"]), round(ms, 1)))
            _, st, _ = srv.req("POST", f"/api/sessions/{sid}/season/advance")
            if st["phase"] == "finished":
                break
        RESULTS["cup32_phase_play_ms"] = phases
        RESULTS["memory_after_cup32"] = tree_mb(srv.proc.pid)
    finally:
        srv.stop()


# ------------------------------------------------------------------ C: paralelismo em processo
def part_c() -> None:
    sys.path[:0] = [str(ROOT), str(ROOT / "shared" / "python"), str(ROOT / "tests")]
    from concurrent.futures import ProcessPoolExecutor

    from support.season_fixtures import make_season

    out = {}
    for workers in (1, 8):
        s = make_season("cup", 32, seed=5)
        with ProcessPoolExecutor(workers) as ex:
            ex.submit(int, 0).result()  # aquece os processos
            t0 = time.perf_counter()
            cpu0 = time.process_time()
            s.play(ex)
            out[workers] = {"wall_s": round(time.perf_counter() - t0, 3), "parent_cpu_s": round(time.process_time() - cpu0, 3)}
    out["speedup"] = round(out[1]["wall_s"] / out[8]["wall_s"], 2)
    out["cpus"] = os.cpu_count()
    RESULTS["parallel_cup32_first_phase"] = out


def main() -> None:
    t0 = time.perf_counter()
    part_a()
    part_b()
    part_c()
    RESULTS["total_s"] = round(time.perf_counter() - t0, 1)
    RESULTS["env"] = {"python": sys.version.split()[0], "os": os.name, "cpus": os.cpu_count()}
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "perf.json"
    out.write_text(json.dumps(RESULTS, indent=1), encoding="utf-8")
    print(json.dumps(RESULTS, indent=1))


if __name__ == "__main__":
    main()
