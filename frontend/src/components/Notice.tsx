import type { ReactNode } from "react";

export type NoticeKind = "success" | "error" | "warning" | "info";

export function Notice({
  kind,
  title,
  children,
  onDismiss,
}: {
  kind: NoticeKind;
  title?: string;
  children?: ReactNode;
  onDismiss?: () => void;
}) {
  return (
    <div className={`notice notice--${kind}`} role={kind === "error" ? "alert" : "status"}>
      <div className="notice__body">
        {title && <strong className="notice__title">{title}</strong>}
        {children && <div>{children}</div>}
      </div>
      {onDismiss && (
        <button type="button" className="btn btn--ghost btn--small" onClick={onDismiss} aria-label="Fechar aviso">
          ✕
        </button>
      )}
    </div>
  );
}
