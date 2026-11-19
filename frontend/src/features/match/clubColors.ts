/**
 * Cores dos clubes para o campinho ao vivo. A base importada não tem cores de clube, então elas são extraídas
 * do PRÓPRIO ESCUDO (Graphics/Clubes): primária = tom mais frequente nos pixels visíveis; secundária = o tom
 * mais frequente que seja bem diferente da primária. Regra do responsável: mandante joga com a primária; o
 * visitante também, salvo se for parecida com a do mandante, quando usa a secundária.
 */
import { useEffect, useState } from "react";
import { clubLogoUrl } from "../../api/endpoints";

export type Rgb = [number, number, number];
export interface ClubColors {
  primary: Rgb;
  secondary: Rgb;
}

/** Cores de reserva quando o escudo não existe ou não pôde ser lido. */
export const FALLBACK_HOME: ClubColors = { primary: [153, 250, 8], secondary: [255, 255, 255] };
export const FALLBACK_AWAY: ClubColors = { primary: [235, 238, 242], secondary: [30, 60, 140] };

export const distance = (a: Rgb, b: Rgb): number => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
/** Duas cores "iguais" para fins de uniforme (o adversário seria confundido em campo). */
export const SIMILAR = 90;

/** Primária e secundária a partir de pixels RGBA (ignora transparência; agrupa tons próximos). */
export function dominantColors(rgba: ArrayLike<number>): ClubColors | null {
  const buckets = new Map<number, { n: number; r: number; g: number; b: number }>();
  for (let i = 0; i + 3 < rgba.length; i += 4) {
    if (rgba[i + 3] < 160) continue;
    const [r, g, b] = [rgba[i], rgba[i + 1], rgba[i + 2]];
    const key = ((r >> 5) << 6) | ((g >> 5) << 3) | (b >> 5);
    const cur = buckets.get(key) ?? { n: 0, r: 0, g: 0, b: 0 };
    cur.n += 1;
    cur.r += r;
    cur.g += g;
    cur.b += b;
    buckets.set(key, cur);
  }
  const ranked = [...buckets.values()]
    .sort((a, b) => b.n - a.n)
    .map((c) => [Math.round(c.r / c.n), Math.round(c.g / c.n), Math.round(c.b / c.n)] as Rgb);
  if (ranked.length === 0) return null;
  const primary = ranked[0];
  const secondary = ranked.find((c) => distance(c, primary) >= SIMILAR * 1.4) ?? (luminance(primary) > 0.5 ? [20, 20, 20] as Rgb : [250, 250, 250] as Rgb);
  return { primary, secondary };
}

/** Cor de cada time em campo: mandante = primária; visitante = primária, ou secundária se parecida com a do mandante. */
export function kitColors(home: ClubColors, away: ClubColors): [Rgb, Rgb] {
  const awayKit = distance(home.primary, away.primary) < SIMILAR ? away.secondary : away.primary;
  return [home.primary, awayKit];
}

export function luminance([r, g, b]: Rgb): number {
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
}
/** Texto legível sobre a cor (preto em cores claras, branco nas escuras). */
export const inkFor = (c: Rgb): string => (luminance(c) > 0.55 ? "#0b0f0a" : "#ffffff");
export const css = ([r, g, b]: Rgb): string => `rgb(${r}, ${g}, ${b})`;

const cache = new Map<number, Promise<ClubColors | null>>();

/** Lê o escudo (mesma origem: /api/assets) num canvas pequeno e extrai as cores. */
export function loadCrestColors(uid: number): Promise<ClubColors | null> {
  let p = cache.get(uid);
  if (!p) {
    p = new Promise<ClubColors | null>((resolve) => {
      if (typeof Image === "undefined" || typeof document === "undefined") return resolve(null);
      const img = new Image();
      img.onload = () => {
        try {
          const size = 32;
          const canvas = document.createElement("canvas");
          canvas.width = size;
          canvas.height = size;
          const ctx = canvas.getContext("2d");
          if (!ctx) return resolve(null);
          ctx.drawImage(img, 0, 0, size, size);
          resolve(dominantColors(ctx.getImageData(0, 0, size, size).data));
        } catch {
          resolve(null);
        }
      };
      img.onerror = () => resolve(null);
      img.src = clubLogoUrl(uid);
    });
    cache.set(uid, p);
  }
  return p;
}

/** Cores dos dois times da partida (com reserva enquanto o escudo carrega ou se não houver escudo). */
export function useKitColors(homeUid: number, awayUid: number): [Rgb, Rgb] {
  const [colors, setColors] = useState<[ClubColors, ClubColors]>([FALLBACK_HOME, FALLBACK_AWAY]);
  useEffect(() => {
    let alive = true;
    void Promise.all([loadCrestColors(homeUid), loadCrestColors(awayUid)]).then(([h, a]) => {
      if (alive) setColors([h ?? FALLBACK_HOME, a ?? FALLBACK_AWAY]);
    });
    return () => {
      alive = false;
    };
  }, [homeUid, awayUid]);
  return kitColors(colors[0], colors[1]);
}
