"""
render.py — Renderiza o JSON gerado por generate_brief.py em HTML estático
e atualiza o site em docs/ (GitHub Pages root).

- docs/index.html              → versão mais recente
- docs/archive/YYYY-MM-DD.html → snapshot daquele dia
- docs/archive/index.html      → índice de todos os briefings

Roda após generate_brief.py no workflow do GitHub Actions.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape


ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build"
DOCS_DIR = ROOT / "docs"
ARCHIVE_DIR = DOCS_DIR / "archive"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def render_markdown(md_text: str) -> str:
    """
    Markdown → HTML com extensões: tables, nl2br para parágrafos densos,
    smarty para aspas curvas (estética editorial).
    """
    return markdown.markdown(
        md_text,
        extensions=["extra", "smarty", "sane_lists"],
        output_format="html5",
    )


def load_brief(json_path: Path) -> dict:
    return json.loads(json_path.read_text(encoding="utf-8"))


def get_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def list_archive_briefs() -> list[dict]:
    """Lê todos os JSONs do build/ e retorna ordenados desc por data."""
    briefs: list[dict] = []
    for p in sorted(BUILD_DIR.glob("*.json"), reverse=True):
        data = load_brief(p)
        briefs.append({
            "date_iso": data["date_iso"],
            "date_pt": data["date_pt"],
            "filename": f"{data['date_iso']}.html",
            # Pega só o primeiro item de "Top 3" como teaser
            "teaser": extract_first_top3(data["body_md"]),
        })
    return briefs


def extract_first_top3(md: str) -> str:
    """Pega a primeira bullet do bloco 'Top 3 do Dia' para usar como teaser no índice."""
    match = re.search(r"##\s*Top 3 do Dia\s*\n+([-*]\s*.+)", md)
    if not match:
        return ""
    first_bullet = match.group(1).strip()
    return re.sub(r"^[-*]\s*", "", first_bullet)


def render_brief_page(env: Environment, data: dict, is_latest: bool, archive: list[dict]) -> str:
    body_html = render_markdown(data["body_md"])
    template = env.get_template("brief.html.j2")
    return template.render(
        date_iso=data["date_iso"],
        date_pt=data["date_pt"],
        generated_at_br=data["generated_at_br"],
        body_html=body_html,
        citations=data.get("citations", []),
        is_latest=is_latest,
        archive=archive,
        model=data.get("model", ""),
    )


def render_archive_index(env: Environment, archive: list[dict]) -> str:
    template = env.get_template("archive.html.j2")
    return template.render(archive=archive)


def main() -> int:
    if not BUILD_DIR.exists():
        print(f"ERRO: {BUILD_DIR} não existe. Rode generate_brief.py primeiro.", file=sys.stderr)
        return 1

    json_files = sorted(BUILD_DIR.glob("*.json"), reverse=True)
    if not json_files:
        print("ERRO: nenhum brief encontrado em build/.", file=sys.stderr)
        return 2

    DOCS_DIR.mkdir(exist_ok=True)
    ARCHIVE_DIR.mkdir(exist_ok=True)

    # Copia o CSS para docs/assets/ (caso ainda não esteja lá)
    src_css = TEMPLATES_DIR / "style.css"
    if src_css.exists():
        (DOCS_DIR / "assets").mkdir(exist_ok=True)
        shutil.copy(src_css, DOCS_DIR / "assets" / "style.css")

    env = get_env()
    archive = list_archive_briefs()

    # Renderiza cada brief do build/ como página individual no archive/
    for jf in json_files:
        data = load_brief(jf)
        is_latest = (jf == json_files[0])
        html = render_brief_page(env, data, is_latest=is_latest, archive=archive)
        out = ARCHIVE_DIR / f"{data['date_iso']}.html"
        out.write_text(html, encoding="utf-8")
        print(f"[render] escrito {out.relative_to(ROOT)}")

    # O mais recente vira o index.html
    latest = load_brief(json_files[0])
    index_html = render_brief_page(env, latest, is_latest=True, archive=archive)
    (DOCS_DIR / "index.html").write_text(index_html, encoding="utf-8")
    print(f"[render] index.html ← {latest['date_iso']}")

    # Índice do arquivo
    arch_idx = render_archive_index(env, archive)
    (ARCHIVE_DIR / "index.html").write_text(arch_idx, encoding="utf-8")
    print(f"[render] archive/index.html ({len(archive)} briefs)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
