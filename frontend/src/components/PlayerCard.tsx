import { useState, type CSSProperties, type ReactNode } from "react";
import { playerPhotoUrl } from "../api/endpoints";
import { displayPosition, sector } from "../domain/positions";
import { ClubCrest } from "./ClubCrest";

/** Selo de posição colorido por setor (GOL laranja, defesa azul, meio verde, ataque vermelho). */
export function PositionBadge({ position, size = "md" }: { position: string; size?: "sm" | "md" }) {
  return (
    <span className={`pos-badge pos-badge--${sector(position)} pos-badge--${size}`}>{displayPosition(position)}</span>
  );
}

const photoSize = (size: number) => ({ "--photo-size": `${size}px` }) as CSSProperties;

/**
 * Silhueta genérica (busto de jogador com camisa de gola em V), a MESMA para todos os atletas sem foto na base.
 * Ocupa o mesmo círculo que a foto real.
 */
export function PlayerSilhouette({ size = 64 }: { size?: number }) {
  return (
    <span className="photo photo--fallback photo--silhouette" style={photoSize(size)} aria-hidden data-testid="player-silhouette">
      <svg viewBox="0 0 64 64" width="100%" height="100%" preserveAspectRatio="xMidYMax meet">
        <path className="sil__body" d="M8 64c0-13 8.5-20.5 19-22.5h10C47.5 43.5 56 51 56 64z" />
        <rect className="sil__body" x="27.5" y="33" width="9" height="9" rx="3" />
        <ellipse className="sil__body" cx="32" cy="24" rx="10.5" ry="12" />
        <path className="sil__collar" d="M26 42.5l6 7.5 6-7.5" />
      </svg>
    </span>
  );
}

/** Foto do atleta (Graphics/Faces) ou a silhueta genérica, no mesmo diâmetro. */
export function PlayerPhoto({ id, hasPhoto = true, size = 64 }: { id: number; name?: string; hasPhoto?: boolean; size?: number }) {
  const [failed, setFailed] = useState(!hasPhoto);
  if (failed) return <PlayerSilhouette size={size} />;
  return (
    <img className="photo" style={photoSize(size)} src={playerPhotoUrl(id)} alt="" width={size} height={size} loading="lazy" onError={() => setFailed(true)} />
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
