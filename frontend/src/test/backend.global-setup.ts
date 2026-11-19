/**
 * Inicia o backend real (uvicorn) com banco SQLite temporário para os testes e2e.
 * Python: variável SQUADFORCE_PYTHON ou ../.venv (Windows/Linux).
 */
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import type { TestProject } from "vitest/node";

declare module "vitest" {
  export interface ProvidedContext {
    backendUrl: string;
    /** Segundo backend real com relógio acelerado (SQUADFORCE_CLOCK_SCALE) para a jornada completa. */
    fastBackendUrl: string;
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

const procs: ChildProcess[] = [];
const tmps: string[] = [];

async function startServer(name: string, extraEnv: Record<string, string>): Promise<string> {
  const port = await freePort();
  const tmp = mkdtempSync(join(tmpdir(), `squadforce-${name}-`));
  tmps.push(tmp);
  const proc = spawn(pythonPath(), ["-m", "services.gateway", "--port", String(port)], {
    cwd: ROOT,
    env: {
      ...process.env,
      SQUADFORCE_DB_PATH: join(tmp, "e2e.db"),
      SQUADFORCE_GRAPHICS_DIR: join(ROOT, "Graphics"),
      // sem SQUADFORCE_AUCTION_MODEL: o servidor carrega o AuctionModel OFICIAL (padrão)
      PYTHONPATH: join(ROOT, "tests"),
      ...extraEnv,
    },
    stdio: "pipe",
  });
  procs.push(proc);
  let log = "";
  proc.stdout?.on("data", (d) => (log += d));
  proc.stderr?.on("data", (d) => (log += d));
  const url = `http://127.0.0.1:${port}`;
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    try {
      if ((await fetch(`${url}/api/health`)).ok) return url;
    } catch {
      await new Promise((r) => setTimeout(r, 250));
    }
  }
  proc.kill();
  throw new Error(`Backend ${name} não iniciou em 30 s:
${log}`);
}

export async function setup(project: TestProject) {
  const [real, fast] = await Promise.all([
    startServer("e2e", {}),
    // relógio 25× mais rápido (leilão, mercado e partida ao vivo); partidas em processos reais
    startServer("journey", { SQUADFORCE_CLOCK_SCALE: "25", SQUADFORCE_MATCH_WORKERS: "2" }),
  ]);
  project.provide("backendUrl", real);
  project.provide("fastBackendUrl", fast);
}

/** Encerra o servidor E seus processos filhos (pool de partidas). No Windows, kill() não derruba a árvore. */
function killTree(p: ChildProcess) {
  if (p.pid == null) return;
  if (process.platform === "win32") spawnSync("taskkill", ["/PID", String(p.pid), "/T", "/F"], { stdio: "ignore" });
  else p.kill();
}

export async function teardown() {
  procs.forEach(killTree);
  await new Promise((r) => setTimeout(r, 300));
  tmps.forEach((t) => rmSync(t, { recursive: true, force: true }));
}
