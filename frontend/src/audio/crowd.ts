/**
 * Sons do estádio sintetizados no navegador (Web Audio): sem arquivos de áudio externos.
 * - Gol: explosão da torcida (ruído filtrado com envelope) + "coro" curto; mais contido para gol do adversário.
 * - Apito: início/intervalo/fim.
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

function noiseBuffer(ac: AudioContext, seconds: number): AudioBuffer {
  const buf = ac.createBuffer(2, Math.floor(ac.sampleRate * seconds), ac.sampleRate);
  for (let ch = 0; ch < 2; ch++) {
    const d = buf.getChannelData(ch);
    let b = 0;
    for (let i = 0; i < d.length; i++) {
      // ruído "rosado" simples: soa como multidão, não como chiado
      b = 0.97 * b + 0.03 * (Math.random() * 2 - 1);
      d[i] = b * 6;
    }
  }
  return buf;
}

/** Torcida explodindo no gol. `own` = gol do seu time (mais alto e longo). */
export function playGoal(own: boolean) {
  const ac = audio();
  if (!ac) return;
  const t = ac.currentTime;
  const dur = own ? 4.2 : 2.2;
  const peak = own ? 0.9 : 0.35;
  const src = ac.createBufferSource();
  src.buffer = noiseBuffer(ac, dur);
  const band = ac.createBiquadFilter();
  band.type = "bandpass";
  band.frequency.setValueAtTime(700, t);
  band.frequency.linearRampToValueAtTime(1100, t + 0.6);
  band.Q.value = 0.6;
  const gain = ac.createGain();
  gain.gain.setValueAtTime(0.0001, t);
  gain.gain.exponentialRampToValueAtTime(peak, t + 0.25);
  gain.gain.setValueAtTime(peak, t + dur * 0.45);
  gain.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  src.connect(band).connect(gain).connect(ac.destination);
  src.start(t);
  src.stop(t + dur);
  if (own) {
    // coro curto "GOOOL": vozes em quinta, vibrato leve
    [196, 294, 392].forEach((f, i) => {
      const o = ac.createOscillator();
      o.type = "sawtooth";
      o.frequency.setValueAtTime(f, t + 0.3);
      o.frequency.linearRampToValueAtTime(f * 0.94, t + 2.4);
      const lp = ac.createBiquadFilter();
      lp.type = "lowpass";
      lp.frequency.value = 900;
      const g = ac.createGain();
      g.gain.setValueAtTime(0.0001, t + 0.3);
      g.gain.exponentialRampToValueAtTime(0.05 / (i + 1), t + 0.6);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 2.5);
      o.connect(lp).connect(g).connect(ac.destination);
      o.start(t + 0.3);
      o.stop(t + 2.6);
    });
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
