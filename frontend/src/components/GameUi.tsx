import { useEffect, useRef, type ReactNode } from "react";

/** Barra da ação principal (rodapé fixo): a próxima coisa a fazer no jogo. */
export function ActionBar({ children, hint }: { children: ReactNode; hint?: ReactNode }) {
  return (
    <div className="action-bar" role="region" aria-label="Próxima ação">
      {hint && <span className="action-bar__hint">{hint}</span>}
      <div className="action-bar__buttons">{children}</div>
    </div>
  );
}

/** Letreiro de abertura de fase (ex.: "RODADA 7"). */
export function PhaseBanner({ kicker, title, children }: { kicker?: ReactNode; title: ReactNode; children?: ReactNode }) {
  return (
    <header className="phase-banner">
      {kicker && <span className="phase-banner__kicker">{kicker}</span>}
      <h1 className="phase-banner__title">{title}</h1>
      {children && <div className="phase-banner__sub">{children}</div>}
    </header>
  );
}

/** Painel sobreposto (gaveta à direita; tela cheia no celular). Esc fecha; foco vai para o painel. */
export function Drawer({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="drawer-backdrop" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="drawer" role="dialog" aria-modal="true" aria-label={title} tabIndex={-1} ref={ref}>
        <header className="drawer__head">
          <h2>{title}</h2>
          <button type="button" className="btn btn--ghost btn--small" onClick={onClose} aria-label="Fechar painel">
            ✕ Fechar
          </button>
        </header>
        <div className="drawer__body">{children}</div>
      </div>
    </div>
  );
}

export const STEPS = [
  { id: "tatica", label: "Tática" },
  { id: "leilao", label: "Leilão" },
  { id: "mercado", label: "Mercado" },
  { id: "temporada", label: "Temporada" },
  { id: "fim", label: "Fim" },
] as const;

export function phaseStep(phase: string | undefined, hasFormation: boolean): (typeof STEPS)[number]["id"] | null {
  switch (phase) {
    case "setup":
      return hasFormation ? "leilao" : "tatica";
    case "auction":
      return "leilao";
    case "squad_completion":
    case "trading":
      return "mercado";
    case "competition":
      return "temporada";
    case "finished":
      return "fim";
    default:
      return null;
  }
}

/** Indicador de etapas da competição na barra superior. */
export function PhaseStepper({ current }: { current: ReturnType<typeof phaseStep> }) {
  const idx = STEPS.findIndex((s) => s.id === current);
  return (
    <ol className="stepper" aria-label="Etapas da competição">
      {STEPS.map((s, i) => (
        <li key={s.id} className={i < idx ? "is-done" : i === idx ? "is-current" : ""} aria-current={i === idx ? "step" : undefined}>
          <span className="stepper__dot" aria-hidden>{i < idx ? "✓" : i + 1}</span>
          <span className="stepper__label">{s.label}</span>
        </li>
      ))}
    </ol>
  );
}
