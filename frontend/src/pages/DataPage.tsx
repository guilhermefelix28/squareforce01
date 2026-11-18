import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { listClubs } from "../api/endpoints";
import { Notice } from "../components/Notice";
import { ClubList } from "../features/catalog/ClubList";
import { PlayerTable } from "../features/catalog/PlayerTable";
import { ImportCard } from "../features/imports/ImportCard";
import type { Club } from "../types/api";

export function DataPage({ importsBlocked, onDataChanged }: { importsBlocked: boolean; onDataChanged: () => void }) {
  const [clubs, setClubs] = useState<Club[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState(0);

  const load = useCallback(async () => {
    try {
      setClubs((await listClubs()).items);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao carregar clubes.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, token]);

  const imported = () => {
    setToken((t) => t + 1);
    onDataChanged();
  };

  return (
    <div className="stack">
      <section>
        <h2>Importação de bases</h2>
        <p className="muted small">
          O arquivo é validado antes de qualquer alteração. Com erro crítico, nada é gravado e a base atual é mantida.
          O Excel é lido apenas em memória — nenhuma cópia é armazenada.
        </p>
        <div className="grid-2">
          <ImportCard base="clubs" blocked={importsBlocked} onImported={imported} />
          <ImportCard base="players" blocked={importsBlocked} onImported={imported} />
        </div>
      </section>

      <section className="card">
        <h2>Clubes ({clubs.length})</h2>
        {error && <Notice kind="error">{error}</Notice>}
        <ClubList clubs={clubs} selected={selected} onSelect={setSelected} />
      </section>

      <section className="card">
        <h2>
          Jogadores
          {selected && ` · ${clubs.find((c) => c.club_uid === selected)?.short_name ?? ""}`}
        </h2>
        <PlayerTable clubUid={selected} refreshToken={token} />
      </section>
    </div>
  );
}
