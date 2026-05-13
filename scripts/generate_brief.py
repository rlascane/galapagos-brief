"""
generate_brief.py - Gera o briefing executivo diario Galapagos.
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
MAX_TOKENS = 8000
MAX_SEARCH_USES = 15

TZ_BR = ZoneInfo("America/Sao_Paulo")

DIAS_SEMANA_PT = {
    0: "segunda-feira",
    1: "terca-feira",
    2: "quarta-feira",
    3: "quinta-feira",
    4: "sexta-feira",
    5: "sabado",
    6: "domingo",
}

MESES_PT = {
    1: "janeiro", 2: "fevereiro", 3: "marco", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}


def format_date_pt(dt):
    return f"{DIAS_SEMANA_PT[dt.weekday()]}, {dt.day} de {MESES_PT[dt.month]} de {dt.year}"


def build_prompt(now_br):
    date_pt = format_date_pt(now_br)
    return f"""Voce e o analista senior responsavel pela leitura matinal de mercado da Galapagos Capital, asset focada em clientes UHNW brasileiros e internacionais.

CONTEXTO
- Data: {date_pt}
- Horario atual: {now_br.strftime('%H:%M')} (Brasilia)
- Audiencia: equipe interna de gestao (PMs, analistas, relacionamento)
- Formato: briefing executivo de 1 pagina, leitura em 5 minutos
- Idioma: portugues brasileiro
- Tom: factual, denso, sem floreios. Estilo Valor/FT, nao estilo portal.

TAREFA
Use a ferramenta web_search para apurar o que aconteceu nas ultimas ~18 horas em mercados, politica economica e geopolitica que impactem alocacao de capital. Faca multiplas buscas direcionadas. Cubra:

1. Fechamento e abertura dos mercados (Brasil e EUA)
2. Decisoes e sinalizacoes de bancos centrais (BCB, Fed, BCE)
3. Politica domestica brasileira com impacto fiscal/regulatorio
4. Movimentos relevantes em commodities, cambio e juros longos
5. Eventos corporativos materiais (M&A, resultados, IPOs)

Priorize fontes como Valor Economico, InfoMoney, Bloomberg, Reuters, Financial Times, WSJ, BCB, B3.

ESTRUTURA OBRIGATORIA (markdown puro, sem code fences, sem H1)

## Top 3 do Dia
Tres bullets de uma linha cada - os movimentos mais relevantes para decisao de alocacao hoje. Sem rodeios.

## Brasil
**Renda Variavel** - Ibovespa fechamento previo com pontos e variacao %, principais altas e baixas, fluxo estrangeiro se disponivel.
**Renda Fixa** - curva DI (vertices curtos e longos), NTN-B 2035/2045, Selic implicita.
**Cambio** - USDBRL ultimo, maxima/minima do dia anterior, drivers principais.
**Macro & Politica** - o que o BC, Fazenda, Congresso fizeram ou sinalizaram nas ultimas 24h.

## Global
**EUA** - S&P 500, Nasdaq, Dow (% do dia), Treasury 10Y, dolar (DXY), sinais do Fed.
**Europa & Asia** - DAX, FTSE, Nikkei, Hang Seng, CSI 300 - so o que importa.
**Commodities** - Brent, WTI, ouro, minerio de ferro (Dalian/Singapura), soja.

## Agenda do Dia
Eventos economicos com horario (BR/UTC), leiloes do Tesouro, decisoes esperadas, divulgacoes corporativas relevantes.

## O Que Monitorar
Dois ou tres temas analiticos para acompanhar nas proximas 24-48h. Aqui e onde voce adiciona vies interpretativo - o que pode mexer com book.

REGRAS DE ESCRITA
- Sempre cite numero e fonte de forma natural. Ex: "Ibovespa fechou em 132.450 pontos (+0,8%) na vespera."
- Se um dado nao estiver verificado por uma fonte confiavel, escreva "dado nao disponivel" - NUNCA invente numero.
- Sem disclaimers de fim de e-mail.
- Sem frases como "espero que isso ajude" ou "abracos".
- Sem repetir a data no corpo (ela vai no header do template).
- Bullets curtos. Paragrafos curtos. Densidade alta, palavras enxutas.

Comece direto pelo "## Top 3 do Dia". Nao escreva preambulo."""


def call_claude(prompt):
    client = anthropic.Anthropic()
    return client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        tools=[
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": MAX_SEARCH_USES,
            }
        ],
        messages=[{"role": "user", "content": prompt}],
    )


def extract_brief(response):
    text_parts = []
    citations = []
    seen_urls = set()

    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
            block_citations = getattr(block, "citations", None) or []
            for cit in block_citations:
                cit_dict = cit if isinstance(cit, dict) else cit.model_dump()
                url = cit_dict.get("url")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    citations.append({
                        "url": url,
                        "title": cit_dict.get("title", url),
                        "cited_text": cit_dict.get("cited_text", ""),
                    })

    return "".join(text_parts).strip(), citations


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERRO: ANTHROPIC_API_KEY nao definido.", file=sys.stderr)
        return 1

    now_br = datetime.now(TZ_BR)
    prompt = build_prompt(now_br)

    print(f"[generate_brief] Chamando {MODEL} em {now_br.isoformat()}...")
    response = call_claude(prompt)

    body, citations = extract_brief(response)
    if not body:
        print("ERRO: resposta sem conteudo de texto.", file=sys.stderr)
        return 2

    usage = response.usage
    print(
        f"[generate_brief] tokens: input={usage.input_tokens} "
        f"output={usage.output_tokens} | citacoes: {len(citations)}"
    )

    out_dir = Path(__file__).resolve().parent.parent / "build"
    out_dir.mkdir(exist_ok=True)

    date_iso = now_br.strftime("%Y-%m-%d")
    payload = {
        "date_iso": date_iso,
        "date_pt": format_date_pt(now_br),
        "generated_at_br": now_br.isoformat(),
        "model": MODEL,
        "body_md": body,
        "citations": citations,
        "usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
        },
    }

    out_file = out_dir / f"{date_iso}.json"
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"[generate_brief] salvo em {out_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
