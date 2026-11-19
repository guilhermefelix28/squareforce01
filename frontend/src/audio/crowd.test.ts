import { afterEach, describe, expect, it, vi } from "vitest";

/** AudioContext falso (apito) e Audio falso (grito da torcida): registram o que foi tocado sem emitir som. */
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
    createGain = node;
    createOscillator = node;
    resume = vi.fn();
  }
  const played: { src: string; volume: number; at: number }[] = [];
  const clips: FakeAudio[] = [];
  class FakeAudio {
    paused = true;
    currentTime = 0;
    volume = 1;
    readyState = 1; // metadados carregados
    preload = "";
    constructor(public src: string) { clips.push(this); }
    play() {
      this.paused = false;
      played.push({ src: this.src, volume: this.volume, at: this.currentTime });
      return Promise.resolve();
    }
    pause() { this.paused = true; }
    load() {}
    addEventListener() {}
    cloneNode() { return new FakeAudio(this.src); }
  }
  (globalThis as { AudioContext?: unknown }).AudioContext = Ctx;
  (globalThis as { Audio?: unknown }).Audio = FakeAudio;
  return { created, played, clips };
}

const realAudio = (globalThis as { Audio?: unknown }).Audio;
afterEach(() => {
  vi.resetModules();
  delete (globalThis as { AudioContext?: unknown }).AudioContext;
  (globalThis as { Audio?: unknown }).Audio = realAudio;
  localStorage.removeItem("squadforce.sound");
});

describe("som da torcida", () => {
  it("toca a gravação no gol quando ligado (padrão) e fica em silêncio quando desligado", async () => {
    const { created, played, clips } = fakeAudio();
    const { playGoal, playWhistle, setSoundEnabled, soundEnabled, GOAL_SOUND_URL } = await import("./crowd");
    expect(soundEnabled()).toBe(true);
    setSoundEnabled(false);
    playGoal(true);
    playWhistle(3);
    expect(played).toHaveLength(0);
    expect(created).not.toHaveBeenCalled();
    setSoundEnabled(true);
    vi.useFakeTimers();
    playGoal(true);
    playGoal(false); // o primeiro ainda toca: um segundo clipe sobreposto
    // trecho a partir de 3,5 s do arquivo fornecido
    expect(played).toEqual([{ src: GOAL_SOUND_URL, volume: 1, at: 3.5 }, { src: GOAL_SOUND_URL, volume: 0.35, at: 3.5 }]);
    expect(GOAL_SOUND_URL).toBe("/sounds/goal-crowd.mp4");
    vi.advanceTimersByTime(2_000);
    expect(clips[0].paused).toBe(false);
    vi.advanceTimersByTime(1_100); // 3 s depois: fade concluído e pausa
    expect(clips.every((c) => c.paused && c.volume === 0)).toBe(true);
    vi.useRealTimers();
    playWhistle(1);
    playWhistle(1);
    expect(created).toHaveBeenCalledTimes(1); // um único contexto de áudio reaproveitado
    expect(localStorage.getItem("squadforce.sound")).toBe("on");
  });

  it("sem áudio no navegador não quebra o jogo", async () => {
    delete (globalThis as { Audio?: unknown }).Audio;
    const { playGoal, playWhistle } = await import("./crowd");
    expect(() => playGoal(true)).not.toThrow();
    expect(() => playWhistle(1)).not.toThrow();
  });
});
