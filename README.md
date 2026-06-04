# Exa API Skill — a reliable wrapper for the Exa web search & research API

> An installable AI-agent **skill** (and standalone Python CLI) that wraps the
> [Exa](https://exa.ai) API — **search, contents, answer, research, and agent** —
> behind one dependable entrypoint, so you stop rediscovering which endpoint, which
> search type, and which gotcha you needed.

[![Install with npx skills](https://img.shields.io/badge/install-npx%20skills-black)](https://skills.sh)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Status](https://img.shields.io/badge/status-stable-brightgreen)

**Keywords:** Exa API · Exa AI · web search API · AI agent skill · Claude Code skill ·
LLM retrieval · RAG · deep research agent · structured output · neural search ·
Python Exa wrapper · `/search` `/contents` `/answer` `/research/v1` `/agent` endpoints.

---

## Why this exists

The Exa API is powerful but has a real learning curve: several products
(`/search`, `/contents`, `/answer`, the `/research/v1` Research API, and the beta
`/agent/runs`), a ladder of search types (`auto`, `fast`, `deep`,
`deep-reasoning`…), structured-output schemas with undocumented limits, two
different async research surfaces (one of which needs a beta header), plus
Windows/encoding pitfalls that silently mangle JSON payloads. Most people burn
hours rediscovering all of this — and the endpoints keep moving.

This skill distills that hard-won know-how into **one script + focused reference
docs**, so any agent (or you, from the terminal) can call Exa correctly the first
time. It owns the **transport** — auth, retry, rate-limiting, payload building,
response parsing — and leaves the domain content (your prompts and schemas) to you.

## What you get

- **One entrypoint, five modes** — `search`, `contents`, `answer`, `research`,
  `agent` in a single `exa.py`. No SDK to learn.
- **Full `/search` coverage** — every Exa search parameter has a flag, plus
  `--extra-json` / `--contents-json` escape hatches for anything new.
- **Standalone contents extraction** — crawl/extract text, summaries, highlights,
  and links for URLs you already have, via `/contents`.
- **Deep-reasoning structured output** — pass a `systemPrompt` + `outputSchema`
  (as files) and get synthesized, grounded, per-field-cited JSON.
- **Parallel batch search** — run many queries at once, rate-limited and retried.
- **Exa Research API** — launch, poll, and collect `/research/v1` runs with a chosen
  model tier; plus the beta Agent API for enrichment/list-building.
- **Safe auth** — your API key is read at runtime from an env var or your local
  config. It is never hardcoded, logged, or committed.
- **Reference docs for every knob** — search types, parameters, contents, structured
  output, answer, research/agent, and a cost/limits/gotchas cheat sheet.

| Mode | Subcommand | Exa endpoint | Returns |
|---|---|---|---|
| Web pages for a query (retrieval), optionally structured | `search` | `POST /search` | results list, or structured `output` if you pass a schema |
| Extract contents for URLs you already have | `contents` | `POST /contents` | text/summary/highlights/links per URL + statuses |
| One cited answer, zero config | `answer` | `POST /answer` | answer string/dict + citations |
| Async agentic research from instructions | `research` | `POST /research/v1` | run → `output.parsed`/`content` + citations |
| Multi-step enrichment / list-building (beta) | `agent` | `POST /agent/runs` | async run → text + structured + grounding |

## Install (as an agent skill)

This is an [agent skill](https://skills.sh) — install it globally for all your
agents (Claude Code CLI, Claude Desktop, Cursor, Codex, and 50+ others) with
[`npx skills`](https://skills.sh):

```bash
npx skills add juststartingtocode/skill-folder-exa-api -g --all
```

Your agent then invokes it on demand via the skill's `SKILL.md`.

## Use (standalone, from the terminal)

The wrapper is just Python + the standard library — clone and run it directly:

```bash
git clone https://github.com/juststartingtocode/skill-folder-exa-api.git
export EXA_API_KEY=your-exa-api-key            # get one at https://exa.ai

# Cheap plain retrieval
python skill-folder-exa-api/exa-api/scripts/exa.py \
    search --query "tummy tuck recovery" --type auto --num-results 10 --pretty

# Extract contents for URLs you already have
python .../exa.py contents --urls "https://a.com/x,https://b.com/y" --text --summary --pretty

# A quick cited answer
python .../exa.py answer --query "What is the capital of Australia?" --pretty

# Deep-reasoning structured research (prompt + schema passed as files)
python .../exa.py search --query "..." --type deep-reasoning \
    --system-prompt-file prompt.txt --output-schema-file schema.json --pretty

# Async Research API (instructions + model tier)
python .../exa.py research --instructions "Compare X and Y; cite sources" --model exa-research --pretty

# Beta Agent API (enrichment / list-building)
python .../exa.py agent --query "Find 10 Miami clinics with emails" --effort high --pretty
```

**Auth** resolves automatically: the `EXA_API_KEY` environment variable first, then
`~/.claude.json` (`mcpServers.exa.url` → `exaApiKey`). Set `EXA_API_KEY` once as a
user environment variable to use it anywhere. Get a key at
[exa.ai](https://exa.ai).

> **Tip:** always pass large prompts/schemas as files (`--system-prompt-file`,
> `--output-schema-file`) rather than inline — Windows command lines have an
> ~8191-char limit and mangle JSON containing `?`, `&`, `=`.

## Documentation

The full decision guide and quick-start live in [`exa-api/SKILL.md`](exa-api/SKILL.md).
On-demand reference docs in [`exa-api/references/`](exa-api/references/):

| Doc | Read when |
|---|---|
| `search-types.md` | Choosing a `--type` — latency, cost, when to use each |
| `search-parameters.md` | The complete param→flag map + the `--extra-json` escape hatch |
| `contents.md` | The `/contents` endpoint — fields, statuses, when vs `search` |
| `structured-output.md` | Building `systemPrompt` + `outputSchema`; the maxed deep-reasoning recipe |
| `answer.md` | Using `/answer` and its limits |
| `research-agent.md` | `research` (`/research/v1`) vs `agent` (`/agent/runs` beta) — models, effort, enrichment |
| `cost-limits-gotchas.md` | Pricing tells, rate limits, Windows/encoding gotchas, error→fix table |

## Layout

```
exa-api/                 # the installable skill (this is what npx detects)
  SKILL.md               # orchestrator: which subcommand, how to run, doc index
  config.json            # base URL, beta token, research model, rate limit, timeout, default type
  scripts/exa.py         # the single entrypoint: search | contents | answer | research | agent
  references/            # the know-how docs the agent reads on demand
```

## Security

Your Exa API key is **never** stored in this repository. It is resolved at runtime
from the `EXA_API_KEY` environment variable or your local `~/.claude.json`, and is
only ever sent as the `x-api-key` header to `api.exa.ai`. Nothing in this repo logs
or persists it.

## License

MIT — see [LICENSE](LICENSE).
