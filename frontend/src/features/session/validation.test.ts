import { describe, expect, it } from "vitest";
import { OPTIONS } from "../../test/fakeApi";
import type { CompetitionOptions, SessionCreate } from "../../types/api";
import { validateSessionConfig } from "./validation";

const opts = OPTIONS as CompetitionOptions;
const base: SessionCreate = { format: "league", num_clubs: 10, user_club_uid: 322, league_rounds: "single", confirm_replace: false };

describe("validateSessionConfig", () => {
  it.each([2, 11, 20])("Liga com %i clubes é válida", (n) => {
    expect(validateSessionConfig({ ...base, num_clubs: n }, opts)).toBeNull();
  });
  it.each([0, 1, 21, 2.5])("Liga com %s clubes é inválida", (n) => {
    expect(validateSessionConfig({ ...base, num_clubs: n }, opts)).not.toBeNull();
  });
  it.each([2, 4, 8, 16, 32])("Copa com %i é válida", (n) => {
    expect(validateSessionConfig({ ...base, format: "cup", league_rounds: null, num_clubs: n }, opts)).toBeNull();
  });
  it.each([3, 6, 12, 64])("Copa com %i é inválida", (n) => {
    expect(validateSessionConfig({ ...base, format: "cup", league_rounds: null, num_clubs: n }, opts)).toMatch(/Copa/);
  });
  it("exige clube do usuário e turnos na Liga", () => {
    expect(validateSessionConfig({ ...base, user_club_uid: 0 }, opts)).toMatch(/clube/);
    expect(validateSessionConfig({ ...base, league_rounds: null }, opts)).toMatch(/turno/);
  });
  it("respeita os clubes disponíveis", () => {
    expect(validateSessionConfig({ ...base, format: "cup", league_rounds: null, num_clubs: 32 }, { ...opts, eligible_clubs: 16 })).toMatch(/16/);
  });
});
