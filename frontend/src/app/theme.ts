import { useEffect, useState } from "react";

export type Theme = "dark" | "light";
const KEY = "squadforce.theme";

/** Escuro é o padrão (decisão do responsável); o claro fica disponível pelo botão e é lembrado. */
export function initialTheme(): Theme {
  try {
    const stored = localStorage.getItem(KEY);
    if (stored === "dark" || stored === "light") return stored;
  } catch {
    /* sem armazenamento: padrão */
  }
  return "dark";
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(initialTheme);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  const toggle = () =>
    setTheme((t) => {
      const next = t === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(KEY, next);
      } catch {
        /* ignora */
      }
      return next;
    });
  return { theme, toggle };
}
