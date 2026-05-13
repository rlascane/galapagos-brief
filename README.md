# Briefing Matinal · Galapagos Capital

Geração e publicação automatizadas de uma leitura executiva diária de mercado, alimentada pela Anthropic API com `web_search` em fontes selecionadas (Valor, InfoMoney, Bloomberg, Reuters, FT, WSJ, BCB, B3) e publicada estaticamente via GitHub Pages.

```
[ Cron 07:00 BRT, seg-sex ]
        │
        ▼
[ GitHub Actions runner ]
        │
        ├── scripts/generate_brief.py   (Claude Opus 4.7 + web_search)
        ├── scripts/render.py           (markdown → HTML editorial)
        │
        ▼
[ commit em docs/ → GitHub Pages → URL pública ]
```

---

## Setup (15 min)

### 1. Subir o repositório

```bash
git init
git add .
git commit -m "init: briefing galapagos"
gh repo create galapagos-brief --private --source=. --push
```

Use `--public` se quiser o site acessível sem login (recomendado se for distribuir para clientes). Use `--private` se for só uso interno — o site ainda fica público pelo Pages, mas o código fonte fica fechado.

### 2. Cadastrar a chave da Anthropic

No GitHub, vá em **Settings → Secrets and variables → Actions → New repository secret**:

| Nome                | Valor                                                   |
|---------------------|---------------------------------------------------------|
| `ANTHROPIC_API_KEY` | sua chave da [console.anthropic.com](https://console.anthropic.com/) |

A chave precisa estar em uma organização/workspace com **web search habilitado** (Settings → Privacy → Web Search, na console). Sem isso a tool retorna erro.

### 3. Ligar o GitHub Pages

**Settings → Pages**:

- **Source**: `Deploy from a branch`
- **Branch**: `main` · pasta `/docs`
- Save.

Após o primeiro commit em `docs/`, o site fica disponível em:

```
https://<seu-usuario>.github.io/galapagos-brief/
```

### 4. Primeira execução manual

**Actions → Daily Briefing → Run workflow**.

Tempo médio: 60-90 segundos. Acompanhe pelo log. Após sucesso, o commit `briefing: edição YYYY-MM-DD` aparece no histórico e o Pages publica em ~1 minuto.

A partir daí, o cron toma conta: roda automático seg-sex às 07:00 BRT (10:00 UTC).

---

## Teste local (opcional)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export ANTHROPIC_API_KEY=sk-ant-...

python scripts/generate_brief.py   # gera build/YYYY-MM-DD.json
python scripts/render.py           # popula docs/

# pré-visualizar
python -m http.server -d docs 8000
# abrir http://localhost:8000
```

---

## Customizações comuns

| O que mudar                    | Onde                                                                 |
|--------------------------------|----------------------------------------------------------------------|
| Horário do cron                | `.github/workflows/daily-brief.yml` → linha `cron`                   |
| Fontes (allow list)            | `scripts/generate_brief.py` → `ALLOWED_DOMAINS`                      |
| Estrutura/tom do briefing      | `scripts/generate_brief.py` → `build_prompt()`                       |
| Visual (paleta, fontes)        | `scripts/templates/style.css` → bloco `:root`                        |
| Modelo                         | `scripts/generate_brief.py` → `MODEL`                                |
| Quantas buscas o agente faz    | `scripts/generate_brief.py` → `MAX_SEARCH_USES`                      |

### Adicionar fim de semana (resumo semanal)

No cron, troque `1-5` por `*` e adicione condicional no prompt. Ou crie um segundo workflow para sábado às 09:00 BRT com prompt diferente ("resumo da semana", não "briefing diário").

### Idioma bilíngue PT/EN para clientes internacionais

Duplicar o prompt em inglês, gerar dois JSONs (um por idioma), renderizar duas páginas (`/en/`, `/pt/`). Mudança de ~30 minutos.

### Tirar do ar (pausar agendamento)

`.github/workflows/daily-brief.yml` → comentar o bloco `schedule:`. O workflow continua disponível para `workflow_dispatch` manual.

---

## Notas operacionais

**Atraso do cron.** O agendador do GitHub Actions não é exato — em horário de pico (00:00 UTC, 12:00 UTC) atrasos de 5-15 minutos são comuns. Para o slot das 10:00 UTC isso costuma ser <5min, mas não há SLA.

**Falhas silenciosas.** Se o workflow falhar, o último briefing válido continua no ar. Configure notificação em Settings → Notifications → Actions para receber email em falhas.

**Custos aproximados.** Cada briefing consome o equivalente a uma chamada Opus 4.7 com ~10-15 buscas web. Confira preços atuais em [docs.claude.com/en/docs/about-claude/pricing](https://docs.claude.com/en/docs/about-claude/pricing). Para orçar com precisão antes de ligar o cron, rode 3-5 vezes manual e olhe os tokens reportados no log.

**Privacidade dos clientes.** Nada de PII (nomes, posições, alocações) entra no prompt. O briefing é puramente macro/mercado — nenhuma exposição.

**Histórico.** Tanto o JSON cru (`build/`) quanto o HTML renderizado (`docs/archive/`) ficam versionados no git. Histórico completo, auditável, indexado pelo Pages.

---

## Estrutura de arquivos

```
galapagos-brief/
├── .github/workflows/
│   └── daily-brief.yml          # cron + pipeline
├── scripts/
│   ├── generate_brief.py        # API call
│   ├── render.py                # JSON → HTML
│   └── templates/
│       ├── brief.html.j2        # template página individual
│       ├── archive.html.j2      # template arquivo
│       └── style.css            # design system
├── build/                       # JSONs gerados (versionado)
├── docs/                        # GitHub Pages root
│   ├── index.html               # último briefing
│   ├── archive/
│   │   └── YYYY-MM-DD.html      # snapshot
│   └── assets/style.css
├── requirements.txt
└── README.md
```

---

**Manutenção:** prompt e fontes em `scripts/generate_brief.py`. Visual em `scripts/templates/style.css`. Resto está estável.
