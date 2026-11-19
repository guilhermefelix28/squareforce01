import { useState, type ReactNode } from "react";
import { playerPhotoUrl } from "../api/endpoints";
import { displayPosition, sector } from "../domain/positions";
import { ClubCrest } from "./ClubCrest";

/** Selo de posição colorido por setor (GOL laranja, defesa azul, meio verde, ataque vermelho). */
export function PositionBadge({ position, size = "md" }: { position: string; size?: "sm" | "md" }) {
  return (
    <span className={`pos-badge pos-badge--${sector(position)} pos-badge--${size}`}>{displayPosition(position)}</span>
  );
}

/** Silhueta genérica (jogador chutando a bola), a MESMA para todos os atletas sem foto na base. */
export function PlayerSilhouette({ size = 64 }: { size?: number }) {
  return (
    <span className="photo photo--fallback photo--silhouette" style={{ width: size, height: size }} aria-hidden data-testid="player-silhouette">
      <svg viewBox="0 0 64 64" width="78%" height="78%" fill="currentColor">
        <circle cx="34" cy="10" r="6.5" />
        <g stroke="currentColor" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" fill="none">
          <path d="M32 21 L28 37" />
          <path d="M32 22 L22 28 L15 25" />
          <path d="M32 22 L41 27 L47 23" />
          <path d="M28 37 L20 46 L13 46" />
          <path d="M28 37 L38 45 L45 53" />
        </g>
        <circle cx="53" cy="56" r="5.5" />
      </svg>
    </span>
  );
}

/** Foto do atleta (Graphics/Faces) ou a silhueta genérica. */
export function PlayerPhoto({ id, hasPhoto = true, size = 64 }: { id: number; name?: string; hasPhoto?: boolean; size?: number }) {
  const [failed, setFailed] = useState(!hasPhoto);
  if (failed) return <PlayerSilhouette size={size} />;
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
        {age != null && variant === "full" && <span className="pcard__age">{age} anos</span>}
      </div>
      <PlayerPhoto id={id} name={name} hasPhoto={hasPhoto} size={variant === "full" ? 104 : 40} />
      <strong className="pcard__name">{name}</strong>
      {variant === "full" && club ? (
        <span className="pcard__origin" title={`Clube de origem: ${club.name}`}>
          {club.uid != null && <ClubCrest clubUid={club.uid} name={club.name} size={26} />}
          <span className="pcard__club">{club.name}</span>
        </span>
      ) : (
        <span className="pcard__meta">
          {age != null && <span>{age} anos</span>}
          {club && <span className="pcard__club">{club.name}</span>}
        </span>
      )}
      {badge}
      {footer && <div className="pcard__foot">{footer}</div>}
    </div>
  );
}
