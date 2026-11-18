import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { configureApi } from "../api/client";

configureApi({ retryDelayMs: 0 });

// Node 26 expõe um localStorage experimental (indefinido sem --localstorage-file) que encobre o do jsdom.
class MemoryStorage implements Storage {
  private m = new Map<string, string>();
  get length() { return this.m.size; }
  clear() { this.m.clear(); }
  getItem(k: string) { return this.m.has(k) ? this.m.get(k)! : null; }
  key(i: number) { return [...this.m.keys()][i] ?? null; }
  removeItem(k: string) { this.m.delete(k); }
  setItem(k: string, v: string) { this.m.set(k, String(v)); }
}
const storage = new MemoryStorage();
Object.defineProperty(globalThis, "localStorage", { value: storage, configurable: true });
Object.defineProperty(window, "localStorage", { value: storage, configurable: true });
// O canal WebSocket é testado no backend e no teste e2e; no jsdom fica desativado.
vi.stubGlobal("WebSocket", undefined);

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  localStorage.clear();
});
