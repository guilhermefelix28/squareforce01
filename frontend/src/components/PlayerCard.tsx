import { useState, type ReactNode } from "react";
import { playerPhotoUrl } from "../api/endpoints";
import { displayPosition, sector } from "../domain/positions";
import { ClubCrest, clubInitials } from "./ClubCrest";

/** Selo de posição colorido por setor (GOL laranja, defesa azul, meio verde, ataque vermelho). */
export function PositionBadge({ position, size = "md" }: { position: string; size?: "sm" | "md" }) {
  return (
    <span className={`pos-badge pos-badge--${sector(position)} pos-badge--${size}`}>{displayPosition(position)}</span>
  );
}

/** Foto do atleta (Graphics/Faces) ou silhueta com iniciais. */
export function PlayerPhoto({ id, name, hasPhoto = true, size = 64 }: { id: number; name: string; hasPhoto?: boolean; size?: number }) {
  const [failed, setFailed] = useState(!hasPhoto);
  if (failed) {
    return (
      <span className="photo photo--fallback" style={{ width: size, height: size, fontSize: size * 0.3 }} aria-hidden>
        {clubInitials(name)}
      </span>
    );
  }
  return (
    <img className="photo" src={playerPhotoUrl(id)} alt="" width={size} height={size} loading="lazy" onError={() => setFailed(true)} />
  );
}

/**
 * Carta de jogador. Nunca mostra overall/atributos (GDD §5/§6): só dados públicos.
 * `variant`: full (leilão/mercado), compact (listas/campo).
 */
export function PlayerCard({
  id,
  name,
  position,
  age,
  club,
  hasPhoto,
  variant = "full",
  footer,
  badge,
  className = "",
}: {
  id: number;
  name: string;
  position: string;
  age?: number | null;
  club?: { uid?: number; name: string } | null;
  hasPhoto?: boolean;
  variant?: "full" | "compact";
  footer?: ReactNode;
  badge?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`pcard pcard--${variant} pcard--${sector(position)} ${className}`}>
      <div className="pcard__top">
        <PositionBadge position={position} size={variant === "full" ? "md" : "sm"} />
        {club?.uid != null && variant === "full" && <ClubCrest clubUid={club.uid} name={club.name} size={22} />}
      </div>
      <PlayerPhoto id={id} name={name} hasPhoto={hasPhoto} size={variant === "full" ? 76 : 40} />
      <strong className="pcard__name">{name}</strong>
      <span className="pcard__meta">
        {age != null && <span>{age} anos</span>}
        {club && <span className="pcard__club">{club.name}</span>}
      </span>
      {badge}
      {footer && <div className="pcard__foot">{footer}</div>}
    </div>
  );
}
