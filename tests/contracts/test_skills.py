"""Verifica as 11 Skills do projeto: frontmatter válido, nome = pasta, seções obrigatórias e links existentes."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / ".claude" / "skills"
REQUIRED = [
    "game-design-rules", "project-architecture", "database-import", "session-management",
    "auction-system", "trading-system", "bot-intelligence", "match-engine",
    "competition-system", "frontend-ui", "testing-validation",
]
SECTIONS = [
    "Finalidade", "Quando utilizar", "Responsabilidades", "Regras do Game Design aplicáveis",
    "Contratos e dependências", "Procedimentos recomendados", "Restrições e comportamentos proibidos",
    "Critérios de teste", "Referências",
]


def parse(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    assert m, f"{path}: frontmatter YAML ausente"
    meta = {}
    for line in m.group(1).splitlines():
        key, _, value = line.partition(":")
        assert _, f"{path}: linha de frontmatter inválida: {line!r}"
        meta[key.strip()] = value.strip()
    return meta, m.group(2)


@pytest.mark.parametrize("name", REQUIRED)
def test_skill_is_valid(name):
    path = SKILLS_DIR / name / "SKILL.md"
    assert path.exists()
    meta, body = parse(path)
    assert meta.get("name") == name
    assert re.fullmatch(r"[a-z0-9-]{1,64}", meta["name"])
    assert 40 <= len(meta.get("description", "")) <= 1024
    for section in SECTIONS:
        assert re.search(rf"^## {re.escape(section)}", body, re.M), f"{name}: seção '{section}' ausente"
    links = re.findall(r"\]\(([^)#]+)\)", body)
    assert links, f"{name}: sem referências"
    for link in links:
        assert (path.parent / link).resolve().exists(), f"{name}: link quebrado {link}"


def test_game_design_rules_is_referenced_by_claude_md():
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    for name in REQUIRED:
        assert name in claude
