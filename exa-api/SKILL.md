---
name: exa-api
description: "Reliable, distilled know-how for calling the Exa web API from any agent or skill. Use when you need to search the web via Exa, extract page contents for known URLs, get a cited answer, run a deep-reasoning structured-output search, launch Exa's async Research API, or run an enrichment/agent workflow — or when another skill says to 'use the Exa skill' / 'make a deep-reasoning call' / 'verify claims with Exa'. One Python entrypoint (exa.py: search | contents | answer | research | agent) plus reference docs for every endpoint, search type, and gotcha."
disable-model-invocation: true
---

# Exa API Toolkit

One reliable way to call Exa from any agent. The know-how (which endpoint, which
search type, which knob) is distilled here so you don't rediscover it. Everything
routes through **one script**: `scripts/exa.py`, with five subcommands.

## Pick the endpoint (decision table)

| Your intent | Subcommand | Endpoint | Sync? |
|---|---|---|---|
| Find web pages for a **query** (retrieval / link-gathering / SERP) | `search` | `POST /search` | sync |
| Extract text/summary/links for **URLs you already have** (crawl/scrape) | `contents` | `POST /contents` | sync |
| One cited **answer** to a question, zero config | `answer` | `POST /answer` | sync |
| Synthesized, **grounded structured output** over the SERP | `search --type deep-reasoning` + schema | `POST /search` | sync |
| Open-ended **async research** from instructions (Exa's Research API) | `research` | `POST /research/v1` | **async** |
| Multi-step **enrichment / list-building** (emails, follow-ups) | `agent` | `POST /agent/runs` (beta) | **async** |

**Rule of thumb:**
- Have a query, want links → **`search`** (cheapest type that works).
- Already have URLs, want their content → **`contents`**.
- Want a synthesized grounded object now → **`search --type deep-reasoning`** + `--output-schema-file`.
- Want a quick cited answer, no knobs → **`answer`**.
- Want Exa to research a topic over many steps → **`research`** (forward path) or **`agent`** (beta, for enrichment).

## Quick start

```bash
SKILL_DIR=<path to this skill>          # the exa-api/ folder
python $SKILL_DIR/scripts/exa.py <search|contents|answer|research|agent> [flags] --pretty
```

Auth resolves automatically: **`EXA_API_KEY` env var first**, then `~/.claude.json`
(`mcpServers.exa.url` → `exaApiKey`). Set `EXA_API_KEY` as a Windows **User** env
var once to use anywhere.

> **Always pass big prompts/schemas as files** (`--system-prompt-file`,
> `--output-schema-file`), never inline — Windows caps the command line at ~8191
> chars and mangles JSON containing `?`, `&`, `=`.

## search — the workhorse (`POST /search`)

```bash
# Cheap plain retrieval (keyword discovery, link gathering)
python $SKILL_DIR/scripts/exa.py search --query "tummy tuck recovery" --type auto --num-results 10

# Maxed-out deep-reasoning structured research (synthesis + grounded claims)
python $SKILL_DIR/scripts/exa.py search \
    --query "What does tummy tuck recovery look like week by week?" \
    --type deep-reasoning --num-results 20 \
    --system-prompt-file prompt.txt --output-schema-file schema.json \
    --highlights --highlights-query "recovery timeline statistics" --max-characters 3000 \
    --include-domains plasticsurgery.org,fda.gov --pretty --out research.json

# Many calls in parallel (rate-limited, retried) — e.g. one per article section
python $SKILL_DIR/scripts/exa.py search --batch calls.json --pretty --out research.json
```

With an `--output-schema`, the structured result lands under `structured.content`
with per-field citations under `structured.grounding`. Without a schema you get a
`results` list. Types: `auto` (default), `fast`, `instant`, `deep-lite`, `deep`,
`deep-reasoning` (legacy `neural`/`keyword` still work). See `references/search-types.md`.

**Complete coverage / nothing restricted.** Every `/search` param has a flag (see
`references/search-parameters.md`). For nested content sub-fields use
`--contents-json '{...}'`; for any top-level param without a flag (or a future one)
use `--extra-json '{...}'` — deep-merged into the body last, wins. Batch specs are
full passthrough (the spec IS the request body + a `name`). `--type` accepts any value.

## contents — extract from known URLs (`POST /contents`)

```bash
python $SKILL_DIR/scripts/exa.py contents --urls "https://a.com/x,https://b.com/y" \
    --text --summary --highlights --max-characters 3000 --pretty
python $SKILL_DIR/scripts/exa.py contents --urls "https://a.com/x" \
    --contents-json '{"summary":{"schema":{...}},"extras":{"links":10}}' --pretty
```

No query — you pass `--urls` (1–100) or `--ids` from a prior search. Same content
flags as `search`. Returns text/summary/highlights per URL + per-URL `statuses`
(cached vs crawled). See `references/contents.md`.

## answer — quick cited answer (`POST /answer`)

```bash
python $SKILL_DIR/scripts/exa.py answer --query "What is the capital of Australia?" --pretty
python $SKILL_DIR/scripts/exa.py answer --query "capital + population of Australia" \
    --output-schema-file shape.json --pretty      # typed answer
```

No model/depth/systemPrompt knobs by design. See `references/answer.md`.

## research — async Research API (`POST /research/v1`)

Exa's current, forward research product. Natural-language `instructions` + a `model`.

```bash
python $SKILL_DIR/scripts/exa.py research \
    --instructions "Compare X and Y for safety; cite sources" \
    --model exa-research --pretty
python $SKILL_DIR/scripts/exa.py research --instructions "..." \
    --output-schema-file schema.json --pretty       # -> output.parsed
python $SKILL_DIR/scripts/exa.py research --instructions "..." --no-wait   # launch only
python $SKILL_DIR/scripts/exa.py research --get r_abc123 --pretty          # poll a run
```

Models: `exa-research-fast` (cheap/quick) · `exa-research` (default) ·
`exa-research-pro` (deepest). `--query` is an alias for `--instructions`. Polls to
completion. See `references/research-agent.md`.

## agent — beta Agent API (`POST /agent/runs`)

For multi-step enrichment / list-building the Research API can't do (row
enrichment via `input.data`, follow-ups via `previousRunId`, events). Beta —
requires the `Exa-Beta` header (handled for you).

```bash
python $SKILL_DIR/scripts/exa.py agent --query "Find 10 Miami plastic surgeons + emails" --effort high --pretty
python $SKILL_DIR/scripts/exa.py agent --get agent_run_abc123 --pretty
python $SKILL_DIR/scripts/exa.py agent --list      # your team's runs
python $SKILL_DIR/scripts/exa.py agent --cancel agent_run_abc123
```

`--effort`: `low | medium | high | xhigh | auto`. See `references/research-agent.md`.

## Reference docs (read the one you need)

| File | Read when |
|---|---|
| `references/search-types.md` | Choosing a `--type` — latency, cost, when to use |
| `references/search-parameters.md` | Complete `/search` param→flag map + `--extra-json`/`--contents-json` escape hatches |
| `references/contents.md` | The `/contents` endpoint — fields, statuses, when vs `search` |
| `references/structured-output.md` | The maxed-out deep-reasoning recipe; schema limits; parsing `structured.content` + grounding |
| `references/answer.md` | Using `/answer`, its limits, when NOT to use it |
| `references/research-agent.md` | `research` (/research/v1) vs `agent` (/agent/runs beta) — models, effort, enrichment |
| `references/cost-limits-gotchas.md` | Pricing tells, rate limits, Windows/encoding gotchas, error→fix table |

## Common flags (all subcommands)

`--pretty` (indent), `--raw` (Exa's unmodified response), `--out FILE`,
`--timeout SECONDS` (deep-reasoning needs ≥120), `--extra-json[-file]` (override any body param).

## Design boundary

This skill owns the **transport** (auth, retry, rate-limit, payload, parse). It does
NOT own domain content — calling skills pass their `systemPrompt` / `outputSchema`
as **files**. The one script is a superset of the per-purpose Exa scripts in the
blog skills (`discover-keywords` → `search --type auto`; `serp-analyst` /
`verify-with-exa` → `search --type deep-reasoning` + prompt/schema; `exa-researcher`
→ `search --batch`).
