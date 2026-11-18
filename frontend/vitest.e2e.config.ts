import { defineConfig } from "vitest/config";

// Testes de comunicação REAL frontend <-> backend: inicia o uvicorn com banco temporário.
export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.e2e.test.ts"],
    globalSetup: ["./src/test/backend.global-setup.ts"],
    testTimeout: 60_000,
    hookTimeout: 60_000,
  },
});
