/**
 * Inicia o backend real (uvicorn) com banco SQLite temporário para os testes e2e.
 * Python: variável SQUADFORCE_PYTHON ou ../.venv (Windows/Linux).
 */
import { spawn, type ChildProcess } from "node:child_process";
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import type { TestProject } from "vitest/node";

declare module "vitest" {
  export interface ProvidedContext {
    backendUrl: string;
  }
}

const ROOT = resolve(__dirname, "../../..");

function pythonPath(): string {
  if (process.env.SQUADFORCE_PYTHON) return process.env.SQUADFORCE_PYTHON;
  const win = join(ROOT, ".venv", "Scripts", "python.exe");
  return existsSync(win) ? win : join(ROOT, ".venv", "bin", "python");
}

function freePort(): Promise<number> {
  return new Promise((ok, fail) => {
    const srv = createServer();
    srv.listen(0, "127.0.0.1", () => {
      const port = (srv.address() as { port: number }).port;
      srv.close(() => ok(port));
    });
    srv.on("error", fail);
  });
}

let proc: ChildProcess | undefined;
let tmp: string | undefined;

export async function setup(project: TestProject) {
  const port = await freePort();
  tmp = mkdtempSync(join(tmpdir(), "squadforce-e2e-"));
  proc = spawn(pythonPath(), ["-m", "services.gateway", "--port", String(port)], {
    cwd: ROOT,
    env: { ...process.env, SQUADFORCE_DB_PATH: join(tmp, "e2e.db"), SQUADFORCE_GRAPHICS_DIR: join(ROOT, "Graphics") },
    stdio: "pipe",
  });
  let log = "";
  proc.stdout?.on("data", (d) => (log += d));
  proc.stderr?.on("data", (d) => (log += d));
  const url = `http://127.0.0.1:${port}`;
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    try {
      if ((await fetch(`${url}/api/health`)).ok) {
        project.provide("backendUrl", url);
        return;
      }
    } catch {
      await new Promise((r) => setTimeout(r, 250));
    }
  }
  proc.kill();
  throw new Error(`Backend não iniciou em 30 s:\n${log}`);
}

export async function teardown() {
  proc?.kill();
  await new Promise((r) => setTimeout(r, 300));
  if (tmp) rmSync(tmp, { recursive: true, force: true });
}
