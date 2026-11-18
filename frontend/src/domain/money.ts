const full = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });

/** R$ 1.250.000 */
export const formatMoney = (v: number): string => full.format(v);

/** R$ 1,25 mi · R$ 500 mil */
export function formatMoneyShort(v: number): string {
  if (Math.abs(v) >= 1_000_000) {
    const mi = v / 1_000_000;
    return `R$ ${mi.toLocaleString("pt-BR", { maximumFractionDigits: 2 })} mi`;
  }
  if (Math.abs(v) >= 1_000) return `R$ ${(v / 1_000).toLocaleString("pt-BR", { maximumFractionDigits: 0 })} mil`;
  return full.format(v);
}

/** Lê "1.500.000", "1500000" ou "1,5 mi" → 1500000. Retorna NaN se inválido. */
export function parseMoney(text: string): number {
  const t = text.trim().toLowerCase().replace(/r\$\s*/, "");
  const mult = /\bmi$|milh/.test(t) ? 1_000_000 : /\bmil$/.test(t) ? 1_000 : 1;
  const num = t.replace(/[a-zçõ\s]/g, "");
  const normalized = mult > 1 ? num.replace(/\./g, "").replace(",", ".") : num.replace(/[.,]/g, "");
  const v = Number(normalized) * mult;
  return Number.isFinite(v) && normalized !== "" ? Math.round(v) : NaN;
}

export const formatClock = (ms: number): string => {
  const s = Math.max(0, Math.ceil(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};
