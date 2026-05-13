"""
generate_brief.py — Gera o briefing executivo diário Galapagos.

Chama a Anthropic API com a ferramenta web_search habilitada, restrita
a fontes confiáveis (Valor, InfoMoney, Bloomberg, Reuters, FT, WSJ,
BCB, B3). Salva o markdown bruto + metadados de citação em JSON
para o render.py consumir.

Roda dentro do GitHub Actions; espera ANTHROPIC_API_KEY como variável
de ambiente.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

MODEL = "claude-opus-4-7"
MAX_TOKENS = 8000
MAX_SEARCH_USES = 15

# Fontes priorizadas, em ordem de relevância para asset Brasil + UHNW
ALLOWED_DOMAINS = [
    "valor.globo.com",
    "valor.com.br",
    "infomoney.com.br",
    "bloomberg.com",
    "reuters.com",
    "ft.com",
    "wsj.com",
    "bcb.gov.br",
    "b3.com.br",
    "tesouro.gov.br",
    "economia.estadao.com.br",
    "agenciabrasil.ebc.com.br",
    "cnbc.com",
]

TZ_BR = ZoneInfo("America/Sao_Paulo")

DIAS_SEMANA_PT = {
    0: "segunda-feira",
    1: "terça-feira",
    2: "quarta-feira",
    3: "quinta-feira",
    4: "sexta-feira",
    5: "sábado",
    6: "domingo",
}

MESES_PT = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}


def format_date_pt(dt: datetime) -> str:
    return f"{DIAS_SEMANA_PT[dt.weekday()]}, {dt.day} de {MESES_PT[dt.month]} de {dt.year}"


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

def build_prompt(now_br: datetime) -> str:
    date_pt = format_date_pt(now_br)
    return f"""Você é o analista sênior responsável pela leitura matinal de mercado da Galapagos Capital, asset focada em clientes UHNW brasileiros e internacionais.

CONTEXTO
- Data: {date_pt}
- Horário atual: {now_br.strftime('%H:%M')} (Brasília)
- Audiência: equipe interna de gestão (PMs, analistas, relacionamento)
- Formato: briefing executivo de 1 página, leitura em 5 minutos
- Idioma: português brasileiro
- Tom: factual, denso, sem floreios. Estilo Valor/FT, não estilo portal.

TAREFA
Use a ferramenta web_search para apurar o que aconteceu nas últimas ~18 horas em mercados, política econômica e geopolítica que impactem alocação de capital. Faça múltiplas buscas direcionadas — não apenas uma. Cubra:

1. Fechamento e abertura dos mercados (Brasil e EUA)
2. Decisões e sinalizações de bancos centrais (BCB, Fed, BCE)
3. Política doméstica brasileira com impacto fiscal/regulatório
4. Movimentos relevantes em commodities, câmbio e juros longos
5. Eventos corporativos materiais (M&A, resultados, IPOs)

ESTRUTURA OBRIGATÓRIA (markdown puro, sem code fences, sem H1)

## Top 3 do Dia
Três bullets de uma linha cada — os movimentos mais relevantes para decisão de alocação hoje. Sem rodeios.

## Brasil
**Renda Variável** — Ibovespa fechamento prévio com pontos e variação %, principais altas e baixas, fluxo estrangeiro se disponível.
**Renda Fixa** — curva DI (vértices curtos e longos), NTN-B 2035/2045, Selic implícita.
**Câmbio** — USDBRL último, máxima/mínima do dia anterior, drivers principais.
**Macro & Política** — o que o BC, Fazenda, Congresso fizeram ou sinalizaram nas últimas 24h.

## Global
**EUA** — S&P 500, Nasdaq, Dow (% do dia), Treasury 10Y, dólar (DXY), sinais do Fed.
**Europa & Ásia** — DAX, FTSE, Nikkei, Hang Seng, CSI 300 — só o que importa.
**Commodities** — Brent, WTI, ouro, minério de ferro (Dalian/Singapura), soja.

## Agenda do Dia
Eventos econômicos com horário (BR/UTC), leilões do Tesouro, decisões esperadas, divulgações corporativas relevantes.

## O Que Monitorar
Dois ou três temas analíticos para acompanhar nas próximas 24-48h. Aqui é onde você adiciona viés interpretativo — o que pode mexer com book.

REGRAS DE ESCRITA
- Sempre cite número e fonte de forma natural. Ex: "Ibovespa fechou em 132.450 pontos (+0,8%) na véspera."
- Se um dado não estiver verificado por uma fonte confiável, escreva "dado não disponível" — NUNCA invente número.
- Sem disclaimers de fim de e-mail.
- Sem frases como "espero que isso ajude" ou "abraços".
- Sem repetir a data no corpo (ela vai no header do template).
- Bullets curtos. Parágrafos curtos. Densidade alta, palavras enxutas.

Comece direto pelo "## Top 3 do Dia". Não escreva preâmbulo."""


# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------

def call_claude(prompt: str) -> anthropic.types.Message:
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
