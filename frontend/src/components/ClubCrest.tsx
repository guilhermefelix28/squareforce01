import { useState } from "react";
import { clubLogoUrl } from "../api/endpoints";

/** Iniciais do clube para o ícone padrão (GDD seção 2: escudo ausente -> iniciais). */
export function clubInitials(name: string): string {
  const stop = new Set(["de", "da", "do", "das", "dos", "e", "fc", "sc", "ec", "saf"]);
  const words = name
    .replace(/[()]/g, " ")
    .split(/\s+/)
    .filter((w) => w && !stop.has(w.toLowerCase()));
  const letters = words.length >= 2 ? words[0][0] + words[1][0] : (words[0] ?? "?").slice(0, 2);
  return letters.toUpperCase();
}

export function ClubCrest({ clubUid, name, size = 40 }: { clubUid: number; name: string; size?: number }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <span className="crest crest--fallback" style={{ width: size, height: size }} aria-label={`Escudo de ${name}`}>
        {clubInitials(name)}
      </span>
    );
  }
  return (
    <img
      className="crest"
      src={clubLogoUrl(clubUid)}
      alt={`Escudo de ${name}`}
      width={size}
      height={size}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}
