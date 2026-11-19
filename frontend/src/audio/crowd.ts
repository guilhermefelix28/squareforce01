/**
 * Sons do estádio.
 * - Gol: grito de torcida (public/sounds/goal-crowd.mp4, a partir de 3,5 s); mais baixo para gol do adversário.
 * - Apito: sintetizado (Web Audio) no início/intervalo/fim.
 * Liga/desliga lembrado no navegador (padrão: ligado).
 */
import { useEffect, useState } from "react";

const KEY = "squadforce.sound";
let ctx: AudioContext | null = null;
const listeners = new Set<(on: boolean) => void>();

export function soundEnabled(): boolean {
  try {
    return localStorage.getItem(KEY) !== "off";
  } catch {
    return true;
  }
}

export function setSoundEnabled(on: boolean) {
  try {
    localStorage.setItem(KEY, on ? "on" : "off");
  } catch {
    /* ignora */
  }
  listeners.forEach((l) => l(on));
}

export function useSound() {
  const [on, setOn] = useState(soundEnabled);
  useEffect(() => {
    listeners.add(setOn);
    return () => void listeners.delete(setOn);
  }, []);
  return { on, toggle: () => setSoundEnabled(!on) };
}

function audio(): AudioContext | null {
  if (!soundEnabled()) return null;
  const Ctor = (globalThis as { AudioContext?: typeof AudioContext; webkitAudioContext?: typeof AudioContext }).AudioContext
    ?? (globalThis as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  try {
    ctx ??= new Ctor();
    if (ctx.state === "suspended") void ctx.resume();
    return ctx;
  } catch {
    return null;
  }
}

/** Grito de gol fornecido pelo responsável (vídeo MP4; só o áudio é usado). Toca o trecho a partir de 3,5 s. */
export const GOAL_SOUND_URL = "/sounds/goal-crowd.mp4";
export const GOAL_START_S = 3.5;
/** Duração do trecho tocado e do fade final (segundos). */
export const GOAL_LENGTH_S = 3;
const GOAL_FADE_S = 0.7;
let goalClip: HTMLAudioElement | null = null;

function newClip(Ctor: typeof Audio): HTMLAudioElement {
  const clip = new Ctor(GOAL_SOUND_URL);
  clip.preload = "auto";
  return clip;
}

/** Carrega o som do gol antes do primeiro gol (evita atraso no primeiro grito). */
export function preloadGoal() {
  const Ctor = (globalThis as { Audio?: typeof Audio }).Audio;
  if (!Ctor || !soundEnabled()) return;
  try {
    goalClip ??= newClip(Ctor);
    goalClip.load?.();
  } catch {
    /* sem áudio */
  }
}

/** Toca [início, início + duração] com o volume pedido e fade no fim. */
function playSegment(clip: HTMLAudioElement, volume: number) {
  const go = () => {
    clip.currentTime = GOAL_START_S;
    clip.volume = volume;
    const p = clip.play();
    if (p && typeof p.catch === "function") p.catch(() => undefined); // autoplay bloqueado: silêncio
    const steps = 7;
    const fadeStart = (GOAL_LENGTH_S - GOAL_FADE_S) * 1000;
    for (let i = 1; i <= steps; i++) {
      setTimeout(() => {
        clip.volume = Math.max(0, volume * (1 - i / steps));
        if (i === steps) clip.pause();
      }, fadeStart + (GOAL_FADE_S * 1000 * i) / steps);
    }
  };
  if (clip.readyState >= 1) go();
  else clip.addEventListener("loadedmetadata", go, { once: true }); // só dá para posicionar após os metadados
}

/** Torcida explodindo no gol. `own` = gol do seu time (volume cheio); gol do adversário bem mais baixo. */
export function playGoal(own: boolean) {
  if (!soundEnabled()) return;
  const Ctor = (globalThis as { Audio?: typeof Audio }).Audio;
  if (!Ctor) return;
  try {
    goalClip ??= newClip(Ctor);
    const clip = goalClip.paused ? goalClip : (goalClip.cloneNode(true) as HTMLAudioElement);
    playSegment(clip, own ? 1 : 0.35);
  } catch {
    /* navegador sem áudio: o jogo segue */
  }
}

/** Apito do árbitro: `times` toques curtos (fim de jogo = 3). */
export function playWhistle(times = 1) {
  const ac = audio();
  if (!ac) return;
  for (let k = 0; k < times; k++) {
    const t = ac.currentTime + k * 0.38;
    const len = k === times - 1 && times > 1 ? 0.6 : 0.26;
    const o = ac.createOscillator();
    o.type = "square";
    o.frequency.setValueAtTime(2900, t);
    const lfo = ac.createOscillator();
    lfo.frequency.value = 38;
    const lfoGain = ac.createGain();
    lfoGain.gain.value = 120;
    lfo.connect(lfoGain).connect(o.frequency);
    const g = ac.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.08, t + 0.02);
    g.gain.setValueAtTime(0.08, t + len - 0.05);
    g.gain.exponentialRampToValueAtTime(0.0001, t + len);
    o.connect(g).connect(ac.destination);
    o.start(t);
    lfo.start(t);
    o.stop(t + len);
    lfo.stop(t + len);
  }
}
