"""
render.py -- Renderiza todos os JSONs do dia em HTML estatico.

Le:
  build/YYYY-MM-DD.json        -> briefing
  build/market_YYYY-MM-DD.json -> dados de mercado (graficos)
  build/article_YYYY-MM-DD.json-> artigo analitico

Gera:
  docs/index.html
  docs/archive/YYYY-MM-DD.html
  docs/archive/index.html
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT         = Path(__file__).resolve().parent.parent
BUILD_DIR    = ROOT / "build"
DOCS_DIR     = ROOT / "docs"
ARCHIVE_DIR  = DOCS_DIR / "archive"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def render_markdown(md_text: str) -> str:
    return markdown.markdown(
        md_text,
        extensions=["extra", "smarty", "sane_lists"],
        output_format="html5",
    )


def load_json(path: Path) -> dict | None:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def get_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def list_archive_entries() -> list[dict]:
    entries = []
    for p in sorted(BUILD_DIR.glob("[0-9]*.json"), reverse=True):
        data = load_json(p)
        if not data:
            continue
        entries.append({
            "date_iso": data["date_iso"],
            "date_pt":  data["date_pt"],
            "filename": f"{data['date_iso']}.html",
            "teaser":   extract_first_top3(data.get("body_md", "")),
        })
    return entries


def extract_first_top3(md: str) -> str:
    match = re.search(r"##\s*Top 3 do Dia\s*\n+([-*]\s*.+)", md)
    if not match:
        return ""
    return re.sub(r"^[-*]\s*", "", match.group(1).strip())


def render_brief_page(
    env: Environment,
    data: dict,
    market: dict | None,
    article: dict | None,
    is_latest: bool,
    archive: list[dict],
) -> str:
    body_html    = render_markdown(data["body_md"])
    article_html = render_markdown(article["article_md"]) if article and article.get("article_md") else None

    template = env.get_template("brief.html.j2")
    return template.render(
        date_iso        = data["date_iso"],
        date_pt         = data["date_pt"],
        generated_at_br = data["generated_at_br"],
        body_html       = body_html,
        citations       = data.get("citations", []),
        market_assets   = (market or {}).get("assets", []),
        article_html    = article_html,
        is_latest       = is_latest,
        archive         = archive,
        model           = data.get("model", ""),
    )


def render_archive_index(env: Environment, archive: list[dict]) -> str:
    template = env.get_template("archive.html.j2")
    return template.render(archive=archive)


def main() -> int:
    if not BUILD_DIR.exists():
        print(f"ERRO: {BUILD_DIR} nao existe.", file=sys.stderr)
        return 1

    brief_files = sorted(BUILD_DIR.glob("[0-9]*.json"), reverse=True)
    if not brief_files:
        print("ERRO: nenhum briefing em build/.", file=sys.stderr)
        return 2

    DOCS_DIR.mkdir(exist_ok=True)
    ARCHIVE_DIR.mkdir(exist_ok=True)

    src_css = TEMPLATES_DIR / "style.css"
    if src_css.exists():
        (DOCS_DIR / "assets").mkdir(exist_ok=True)
        shutil.copy(src_css, DOCS_DIR / "assets" / "style.css")

    env     = get_env()
    archive = list_archive_entries()

    for bf in brief_files:
        data    = load_json(bf)
        date_iso = data["date_iso"]
        market  = load_json(BUILD_DIR / f"market_{date_iso}.json")
        article = load_json(BUILD_DIR / f"article_{date_iso}.json")
        is_latest = (bf == brief_files[0])

        html = render_brief_page(env, data, market, article, is_latest, archive)
        out  = ARCHIVE_DIR / f"{date_iso}.html"
        out.write_text(html, encoding="utf-8")
        print(f"[render] {out.relative_to(ROOT)}")

    # Index = mais recente
    latest   = load_json(brief_files[0])
    date_iso = latest["date_iso"]
    market   = load_json(BUILD_DIR / f"market_{date_iso}.json")
    article  = load_json(BUILD_DIR / f"article_{date_iso}.json")
    index_html = render_brief_page(env, latest, market, article, True, archive)
    (DOCS_DIR / "index.html").write_text(index_html, encoding="utf-8")
    print(f"[render] index.html <- {date_iso}")

    arch_idx = render_archive_index(env, archive)
    (ARCHIVE_DIR / "index.html").write_text(arch_idx, encoding="utf-8")
    print(f"[render] archive/index.html ({len(archive)} edicoes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
