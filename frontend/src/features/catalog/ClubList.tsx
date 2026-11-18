import { ClubCrest } from "../../components/ClubCrest";
import type { Club } from "../../types/api";

export function ClubList({
  clubs,
  selected,
  onSelect,
}: {
  clubs: Club[];
  selected: number | null;
  onSelect: (uid: number | null) => void;
}) {
  if (!clubs.length) return <p className="muted">Nenhum clube importado.</p>;
  return (
    <ul className="club-grid">
      {clubs.map((c) => (
        <li key={c.club_uid}>
          <button
            type="button"
            className={`club-chip ${selected === c.club_uid ? "is-selected" : ""}`}
            aria-pressed={selected === c.club_uid}
            onClick={() => onSelect(selected === c.club_uid ? null : c.club_uid)}
            title={c.name}
          >
            <ClubCrest clubUid={c.club_uid} name={c.short_name} size={32} />
            <span className="club-chip__name">{c.short_name}</span>
            <span className="club-chip__count">{c.player_count}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
