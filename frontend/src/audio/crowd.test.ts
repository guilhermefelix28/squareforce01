import { afterEach, describe, expect, it, vi } from "vitest";

/** AudioContext falso: registra o que foi tocado sem emitir som. */
function fakeAudio() {
  const created = vi.fn();
  const node = () => ({
    connect: vi.fn().mockImplementation(function (this: unknown, n: unknown) { return n; }),
    start: vi.fn(), stop: vi.fn(),
    frequency: { value: 0, setValueAtTime: vi.fn(), linearRampToValueAtTime: vi.fn() },
    gain: { value: 0, setValueAtTime: vi.fn(), exponentialRampToValueAtTime: vi.fn() },
    Q: { value: 0 }, type: "", buffer: null,
  });
  class Ctx {
    currentTime = 0;
    sampleRate = 8000;
    state = "running";
    destination = {};
    constructor() { created(); }
    createBuffer = (_c: number, len: number) => ({ getChannelData: () => new Float32Array(len) });
    createBufferSource = node;
    createBiquadFilter = node;
    createGain = node;
    createOscillator = node;
    resume = vi.fn();
  }
  (globalThis as { AudioContext?: unknown }).AudioContext = Ctx;
  return created;
}

afterEach(() => {
  vi.resetModules();
  delete (globalThis as { AudioContext?: unknown }).AudioContext;
  localStorage.removeItem("squadforce.sound");
});

describe("som da torcida", () => {
  it("toca no gol quando ligado (padrão) e fica em silêncio quando desligado", async () => {
    const created = fakeAudio();
    const { playGoal, playWhistle, setSoundEnabled, soundEnabled } = await import("./crowd");
    expect(soundEnabled()).toBe(true);
    setSoundEnabled(false);
    playGoal(true);
    playWhistle(3);
    expect(created).not.toHaveBeenCalled();
    setSoundEnabled(true);
    playGoal(true);
    playGoal(false);
    expect(created).toHaveBeenCalledTimes(1); // um único contexto de áudio reaproveitado
    expect(localStorage.getItem("squadforce.sound")).toBe("on");
  });

  it("sem Web Audio no navegador não quebra o jogo", async () => {
    const { playGoal } = await import("./crowd");
    expect(() => playGoal(true)).not.toThrow();
  });
});
