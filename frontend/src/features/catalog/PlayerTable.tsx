import { useEffect, useState } from "react";
import { ApiError } from "../../api/client";
import { listPlayers } from "../../api/endpoints";
import { Notice } from "../../components/Notice";
import { POSITION_ORDER, displayPosition } from "../../domain/positions";
import type { PlayerPage } from "../../types/api";

const PAGE = 25;

export function PlayerTable({ clubUid, refreshToken }: { clubUid: number | null; refreshToken: number }) {
  const [search, setSearch] = useState("");
  const [position, setPosition] = useState("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<PlayerPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => setOffset(0), [clubUid, search, position]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const p = await listPlayers({
          club_uid: clubUid ?? undefined,
          position: position || undefined,
          search: search.trim() || undefined,
          limit: PAGE,
          offset,
        });
        if (!cancelled) {
          setPage(p);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof ApiError ? e.message : "Erro ao consultar jogadores.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [clubUid, search, position, offset, refreshToken]);

  const total = page?.total ?? 0;
  return (
    <div className="players">
      <div className="toolbar">
        <label className="field">
          <span>Buscar</span>
          <input type="search" value={search} placeholder="Nome do jogador" onChange={(e) => setSearch(e.target.value)} />
        </label>
        <label className="field">
          <span>Posição natural</span>
          <select value={position} onChange={(e) => setPosition(e.target.value)}>
            <option value="">Todas</option>
            {POSITION_ORDER.map((p) => (
              <option key={p} value={p}>
                {displayPosition(p)}
              </option>
            ))}
          </select>
        </label>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      <div className="table-wrap" aria-busy={loading}>
        <table>
          <thead>
            <tr>
              <th>Jogador</th>
              <th>Pos.</th>
              <th className="hide-sm">Secund.</th>
              <th className="num">Idade</th>
              <th>Clube</th>
            </tr>
          </thead>
          <tbody>
            {page?.items.map((p) => (
              <tr key={p.unique_id}>
                <td>
                  <span className="player-name">{p.name}</span>
                  <span className="muted small hide-sm"> #{p.unique_id}</span>
                </td>
                <td>{p.natural_positions.map(displayPosition).join(", ")}</td>
                <td className="hide-sm">{p.accomplished_positions.map(displayPosition).join(", ") || "—"}</td>
                <td className="num">{p.age}</td>
                <td>{p.club_short_name}</td>
              </tr>
            ))}
            {page && !page.items.length && (
              <tr>
                <td colSpan={5} className="muted">
                  Nenhum jogador encontrado.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="pager">
        <span className="muted small">
          {total ? `${offset + 1}–${Math.min(offset + PAGE, total)} de ${total}` : "0 jogadores"}
        </span>
        <div>
          <button type="button" className="btn btn--ghost btn--small" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
            Anterior
          </button>
          <button type="button" className="btn btn--ghost btn--small" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>
            Próxima
          </button>
        </div>
      </div>
    </div>
  );
}
