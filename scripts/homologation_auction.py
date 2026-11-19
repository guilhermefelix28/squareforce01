"""Homologação do leilão com o AuctionModel oficial (critérios L1–L6 de docs/homologacao/criterios.md §6).

Leilões completos simulados na base real: Liga 20, Liga 10, Copa 8 e Copa 32, 50 sementes cada. Todos os
clubes são bots, exceto o clube do usuário, que fica passivo (não dá lances) e é excluído das métricas dos bots.

Uso: .venv/Scripts/python scripts/homologation_auction.py [--seeds 50] [--workers 10] [--out docs/homologacao/leilao.md]
"""

from __future__ import annotations

import argparse
import random
import statistics as st
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "shared" / "python")]

from services.auction.engine import AuctionEngine  # noqa: E402
from services.auction.model import AuctionModelError  # noqa: E402
from services.auction.official_model import OfficialAuctionModel  # noqa: E402
from services.auction.rules import INITIAL_BUDGET  # noqa: E402
from services.bot_ai.evaluation import squad_quality  # noqa: E402
from services.data.service import DataService  # noqa: E402
from squadforce_shared.domain.competition import CompetitionFormat  # noqa: E402

CONFIGS = (("Liga 20", CompetitionFormat.LEAGUE, 20), ("Liga 10", CompetitionFormat.LEAGUE, 10),
           ("Copa 8", CompetitionFormat.CUP, 8), ("Copa 32", CompetitionFormat.CUP, 32))
_POOL = None
_CLUBS = None


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _init(overrides: dict | None = None) -> None:
    global _POOL, _CLUBS
    if overrides:  # SÓ para lotes exploratórios (parâmetros provisórios da IA); o lote oficial usa os padrões
        import services.bot_ai.auction_bot as bot

        import importlib

        for k, v in overrides.items():
            mod, _, attr = k.rpartition(".")
            if attr == "APPROVED_BOT_PROFILES":  # tuplas -> BotProfile
                from services.auction.model import BotProfile

                v = {name: BotProfile(*vals) for name, vals in v.items()}
            setattr(importlib.import_module(mod) if mod else bot, attr, v)
    ds = DataService(ROOT / "database" / "squadforce.db", None)
    _POOL = ds.load_player_profiles()
    _CLUBS = sorted({p.club_uid for p in _POOL})


def run_one(args: tuple[str, CompetitionFormat, int, int]) -> dict:
    label, fmt, n, seed = args
    rng = random.Random(seed)
    clubs = list(_CLUBS)
    while len(clubs) < n:  # Copa 32 com 40 clubes reais: basta sortear
        clubs += _CLUBS
    participants = rng.sample(sorted(set(clubs)), n) if n <= len(set(clubs)) else clubs[:n]
    clock = Clock()
    t0 = time.perf_counter()
    try:
        eng = AuctionEngine(participants=participants, user_club_uid=participants[0], fmt=fmt, num_clubs=n,
                            pool=_POOL, model=OfficialAuctionModel(), rng=random.Random(seed), clock=clock)
        eng.start()
        while eng.phase == "running":
            clock.now += 0.5
            eng.tick()
    except AuctionModelError as exc:
        return {"label": label, "seed": seed, "model_error": str(exc)}
    m = eng.model
    clubs_out = []
    owners = Counter()
    for uid, c in eng.clubs.items():
        squad = [eng.players[k.player_id] for k in c.contracts]
        owners.update(k.player_id for k in c.contracts)
        auction = [k for k in c.contracts if k.source == "auction"]
        clubs_out.append({
            "uid": uid, "bot": c.is_bot, "personality": c.personality, "size": len(c.contracts), "budget": c.budget,
            "auction_spent": sum(k.price for k in auction),
            "price_to_value": [k.price / eng.market_value[k.player_id] for k in auction],
            "starters": squad_quality(squad, m).starters,
        })
    offered = Counter()
    for r in eng.results:
        for pid in (*[s[0] for s in r.sales], *r.unsold):
            offered[pid] += 1
    return {
        "label": label, "seed": seed, "model_error": None, "clubs": clubs_out,
        "duplicates": sum(1 for v in owners.values() if v > 1),
        "offered": len(offered), "offered_ok": sum(1 for pid in offered if eng.unsold_counts.get(pid, 0) <= 2),
        "rounds": len(eng.results), "reason": eng.finish_reason, "seconds": time.perf_counter() - t0,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=50)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--out", default=None)
    ap.add_argument("--seed-base", type=int, default=10_000, help="lote oficial: 10000; exploratórios: outro valor")
    ap.add_argument("--competition-weight", type=float, default=None)
    ap.add_argument("--sampling-power", type=float, default=None)
    ap.add_argument("--set", action="append", help="exploratório: modulo.ATRIBUTO=literal")
    a = ap.parse_args()
    overrides = {k: v for k, v in (("COMPETITION_WEIGHT", a.competition_weight), ("SAMPLING_POWER", a.sampling_power))
                 if v is not None}
    for item in a.set or ():  # exploratório: modulo.ATRIBUTO=literal
        k, _, v = item.partition("=")
        overrides[k] = __import__("ast").literal_eval(v)
    jobs = [(label, fmt, n, a.seed_base + s) for label, fmt, n in CONFIGS for s in range(a.seeds)]
    t0 = time.perf_counter()
    with ProcessPoolExecutor(a.workers, initializer=_init, initargs=(overrides,)) as ex:
        res = list(ex.map(run_one, jobs))
    elapsed = time.perf_counter() - t0

    errors = [r for r in res if r["model_error"]]
    ok = [r for r in res if not r["model_error"]]
    all_clubs = [c for r in ok for c in r["clubs"]]
    bots = [c for c in all_clubs if c["bot"]]
    l1 = sum(c["size"] == 18 and c["budget"] >= 0 for c in all_clubs) / max(1, len(all_clubs))
    l1_dup = sum(r["duplicates"] for r in ok)
    spend = [c["auction_spent"] / INITIAL_BUDGET for c in bots]
    l3 = st.median(spend)
    l4 = sum(r["offered_ok"] for r in ok) / max(1, sum(r["offered"] for r in ok))
    by_pers = defaultdict(list)
    ratio = defaultdict(list)
    for c in bots:
        by_pers[c["personality"]].append(c["auction_spent"])
        ratio[c["personality"]] += c["price_to_value"]
    mean_spend = {k: st.mean(v) for k, v in by_pers.items()}
    mean_ratio = {k: st.mean(v) for k, v in ratio.items() if v}
    others = [v for k, v in mean_ratio.items() if k != "opportunist"]
    l5 = mean_spend["aggressive"] > mean_spend["conservative"] and mean_ratio["opportunist"] < st.mean(others)
    gaps = []
    for r in ok:
        q = [c["starters"] for c in r["clubs"] if c["bot"]]
        gaps.append((max(q) - min(q)) / st.median(q))
    l6 = st.median(gaps)

    rows = [
        ("L1", "Clubes com 18 atletas, saldo ≥ 0, sem duplicação", "100%",
         f"{l1:.1%}, {l1_dup} duplicações", l1 == 1.0 and l1_dup == 0),
        ("L2", "AuctionModelError", "0", str(len(errors)), not errors),
        ("L3", "Mediana do gasto no leilão (bots)", "50%–95%", f"{l3:.1%}", 0.50 <= l3 <= 0.95),
        ("L4", "Oferecidos com ≤ 2 aparições sem venda", "≥ 60%", f"{l4:.1%}", l4 >= 0.60),
        ("L5", "Agressivo gasta mais que Conservador; Oportunista paga menos/valor", "sim",
         "gasto médio " + ", ".join(f"{k} R$ {v/1e6:.1f} mi" for k, v in sorted(mean_spend.items()))
         + "; preço/valor " + ", ".join(f"{k} {v:.2f}" for k, v in sorted(mean_ratio.items())), l5),
        ("L6", "Diferença de titulares melhor × pior bot (mediana)", "≤ 25%", f"{l6:.1%}", l6 <= 0.25),
    ]
    per_cfg = defaultdict(list)
    for r in ok:
        per_cfg[r["label"]].append(r)
    lines = [
        "# Homologação do leilão com o `AuctionModel` oficial",
        "",
        f"Modelo `{OfficialAuctionModel.version if hasattr(OfficialAuctionModel, 'version') else ''}`. "
        f"{len(res)} leilões completos na base real ({len(_load_count())} atletas), {elapsed:.0f} s. Critérios fixados "
        "antes da medição em `criterios.md` §6.",
        "",
        "| # | Critério | Limite | Observado | Resultado |",
        "|---|---|---|---|---|",
        *[f"| {a} | {b} | {c} | {d} | {'✅' if e else '❌'} |" for a, b, c, d, e in rows],
        "",
        "## Por configuração",
        "",
        "| Configuração | Leilões | Rodadas (média) | Encerramento | Gasto mediano dos bots | Tempo médio |",
        "|---|---|---|---|---|---|",
    ]
    for label, _, _ in CONFIGS:
        rs = per_cfg[label]
        reasons = Counter(r["reason"] for r in rs)
        sp = st.median(c["auction_spent"] / INITIAL_BUDGET for r in rs for c in r["clubs"] if c["bot"])
        lines.append(f"| {label} | {len(rs)} | {st.mean(r['rounds'] for r in rs):.0f} | "
                     f"{', '.join(f'{k} {v}' for k, v in reasons.items())} | {sp:.1%} | "
                     f"{st.mean(r['seconds'] for r in rs):.1f} s |")
    text = "\n".join(lines) + "\n"
    print(text)
    if errors:
        print("Erros do modelo:", *{e["model_error"] for e in errors}, sep="\n  ")
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")


def _load_count():
    if _POOL is None:
        _init()
    return _POOL


if __name__ == "__main__":
    main()
