"""
generate_article.py -- Gera artigo analitico diario via Claude.

Le o briefing do dia (ja gerado por generate_brief.py) como contexto,
e pede ao Claude que escolha o tema mais relevante do dia para escrever
um artigo de 500-600 palavras para investidores UHNW brasileiros.

Nao faz buscas adicionais -- usa o contexto do briefing.
Salva em build/article_YYYY-MM-DD.json.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic

MODEL = "claude-opus-4-7"
MAX_TOKENS = 4000
TZ_BR = ZoneInfo("America/Sao_Paulo")

BUILD_DIR = Path(__file__).resolve().parent.parent / "build"


def build_article_prompt(brief_body: str, date_pt: str) -> str:
    return f"""Voce e o estrategista-chefe da Galapagos Capital, asset brasileira focada em clientes UHNW.

CONTEXTO DO DIA ({date_pt})
A seguir esta o briefing de mercado ja apurado pela equipe de research:

---
{brief_body}
---

TAREFA
Com base nesse contexto, escolha o tema mais relevante e analiticamente rico do dia para escrever um artigo de 500 a 600 palavras.

Temas possiveis (mas nao limitados a):
- Alocacao de portfolio dado o cenario macro atual
- Momento politico-fiscal brasileiro e implicacoes para renda fixa/renda variavel
- Trajetoria de juros globais e impacto em emergentes
- Ciclo de commodities e posicionamento setorial
- Comparativo de classes de ativos no contexto atual

Escolha o tema que voce, como estrategista, consideraria mais urgente e util para um gestor de patrimonio tomar decisoes esta semana.

ESTRUTURA DO OUTPUT (markdown puro, sem code fences)

## [Titulo do artigo -- especifico e preciso, nao generico]

*[Subtitulo de uma linha resumindo o argumento central]*

[Corpo do artigo -- 500 a 600 palavras, estruturado em 3 a 4 paragrafos]

**[Nome do tema/secao em negrito no inicio de cada paragrafo se ajudar a estrutura]**

[Paragrafo de fechamento com implicacao pratica para alocacao]

REGRAS
- Tom: analitico, direto, sem hedges excessivos. Voce tem uma visao e defende ela.
- Use os dados do briefing para embasar os argumentos. Cite numeros especificos.
- Nao escreva "Com base no briefing..." -- integre naturalmente.
- Sem disclaimer de investimento no final.
- Portugues brasileiro, vocabulario tecnico mas acessivel.
- Nao repita o titulo do artigo como H1 -- comece direto pelo subtitulo em italico."""


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERRO: ANTHROPIC_API_KEY nao definido.", file=sys.stderr)
        return 1

    now_br = datetime.now(TZ_BR)
    date_iso = now_br.strftime("%Y-%m-%d")

    # Le o briefing do dia
    brief_file = BUILD_DIR / f"{date_iso}.json"
    if not brief_file.exists():
        print(f"ERRO: briefing {brief_file} nao encontrado. Rode generate_brief.py primeiro.", file=sys.stderr)
        return 2

    brief_data = json.loads(brief_file.read_text())
    brief_body = brief_data.get("body_md", "")

    if not brief_body:
        print("ERRO: briefing vazio.", file=sys.stderr)
        return 3

    prompt = build_article_prompt(brief_body, brief_data.get("date_pt", date_iso))

    client = anthropic.Anthropic()
    print(f"[generate_article] Gerando artigo analitico ({MODEL})...")

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )

    article_md = ""
    for block in response.content:
        if block.type == "text":
            article_md += block.text

    article_md = article_md.strip()
    if not article_md:
        print("AVISO: resposta vazia do modelo.", file=sys.stderr)
        return 0  # nao falha o workflow

    usage = response.usage
    print(
        f"[generate_article] tokens: input={usage.input_tokens} "
        f"output={usage.output_tokens}"
    )

    out_file = BUILD_DIR / f"article_{date_iso}.json"
    out_file.write_text(
        json.dumps({
            "date_iso": date_iso,
            "article_md": article_md,
            "model": MODEL,
            "usage": {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
            },
        }, ensure_ascii=False, indent=2)
    )
    print(f"[generate_article] salvo em {out_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
