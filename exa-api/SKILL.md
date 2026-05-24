---
name: exa-api
description: "Reliable, distilled know-how for calling the Exa web API (search, answer, research) from any agent or skill. Use when you need to search the web via Exa, run a deep-reasoning structured-output search, get a cited answer, run an async deep-research/enrichment agent, or when another skill says to 'use the Exa skill' / 'make a deep-reasoning call' / 'verify claims with Exa'. Provides one Python entrypoint (exa.py: search | answer | research) plus reference docs for every endpoint, search type, and gotcha."
disable-model-invocation: true
---

# Exa API Toolkit

One reliable way to call Exa from any agent. The know-how (which endpoint, which
search type, which knobs) is distilled here so you don't have to rediscover it.

Everything routes through **one script**: `scripts/exa.py`, with three subcommands.

## The 3 products (pick one)

| You want… | Subcommand | Endpoint | Returns | Sync? |
|---|---|---|---|---|
| Web pages for a query (retrieval) | `search` | `POST /search` | results (URLs + text/highlights), or structured `output` if you pass a schema | sync |
| One cited answer, no config | `answer` | `POST /answer` | `answer` string/dict + citations | sync |
| Multi-step research / list-building / enrichment | `research` | `POST /agent/runs` | async run → `output.text` + structured + grounding | **async** |

**Rule of thumb:**
- Need control over *how* it searches, the prompt, or the output shape → **`search`** (use `--type deep-reasoning` + `--system-prompt-file` + `--output-schema-file`).
- Just want a quick cited answer with zero knobs → **`answer`** (you cannot steer its model or depth).
- Need a long-running agent that searches, reasons, and enriches over many steps → **`research`**.

## Quick start

```bash
SKILL_DIR=<path to this skill>          # the exa-api/ folder
python $SKILL_DIR/scripts/exa.py <search|answer|research> [flags] --pretty
```

Auth resolves automatically: **`EXA_API_KEY` env var first**, then `~/.claude.json`
(`mcpServers.exa.url` → `exaApiKey`). To use anywhere, set `EXA_API_KEY` as a
Windows **User** env var once.

> **Always pass big prompts/schemas as files** (`--system-prompt-file`,
> `--output-schema-file`), never inline — Windows has an ~8191-char command-line
> limit and mangles JSON with `?`, `&`, `=` in it.

## Search — the workhorse

```bash
# Cheap plain retrieval (keyword discovery, link gathering)
python $SKILL_DIR/scripts/exa.py search --query "tummy tuck recovery" --type auto --num-results 10

# Maxed-out deep-reasoning structured research (synthesis + grounded claims)
python $SKILL_DIR/scripts/exa.py search \
    --query "What does tummy tuck recovery look like week by week?" \
    --type deep-reasoning --num-results 20 \
    --system-prompt-file prompt.txt \
    --output-schema-file schema.json \
    --highlights --highlights-query "recovery timeline statistics" --max-characters 3000 \
    --include-domains plasticsurgery.org,fda.gov \
    --pretty --out research.json

# Many calls in parallel (rate-limited, retried) — e.g. one per article section
python $SKILL_DIR/scripts/exa.py search --batch calls.json --pretty --out research.json
```

When you pass an `--output-schema`, the structured result lands under
`structured.content`, with per-field citations under `structured.grounding`
(see `references/structured-output.md`). Without a schema, you get a `results` list.

The `--batch` file is a JSON **array** of call specs; each spec uses camelCase keys
(`query`, `type`, `numResults`, `systemPrompt`, `outputSchema`, `contents`,
`includeDomains`, `additionalQueries`, `name`). They run in parallel batches of
`rate_limit` (config, default 5) with one retry on 429/5xx/524.

**Complete coverage / nothing restricted.** Every `/search` param has a flag (see
`references/search-parameters.md`). For nested `contents` sub-fields use
`--contents-json '{...}'`; for any top-level param without a flag (or a future
one) use `--extra-json '{...}'` — it's deep-merged into the body last and wins.
Batch specs are full passthrough (the spec IS the request body + a `name`). The
`--type` flag accepts any value, so new search types work immediately.

## Answer

```bash
python $SKILL_DIR/scripts/exa.py answer --query "What is the capital of Australia?" --pretty
python $SKILL_DIR/scripts/exa.py answer --query "capital + population of Australia" \
    --output-schema-file shape.json --pretty      # typed answer
```

## Research (async agent)

```bash
python $SKILL_DIR/scripts/exa.py research --query "Compare X and Y; cite sources" --effort high --pretty
python $SKILL_DIR/scripts/exa.py research --query "..." --no-wait        # launch only, prints id
python $SKILL_DIR/scripts/exa.py research --get agent_run_abc123 --pretty  # poll an existing run
```

`--effort`: `low | medium | high | xhigh | auto`. The script handles the required
`Exa-Beta` header and polls to completion (default up to 600s).

## Reference docs (read the one you need)

| File | Read when |
|---|---|
| `references/search-types.md` | Choosing a `--type` (instant/fast/auto/neural/keyword/deep-lite/deep/deep-reasoning) — latency, cost, when to use |
| `references/search-parameters.md` | The complete param→flag map. **Proof every `/search` param is reachable** + the `--extra-json` / `--contents-json` escape hatches |
| `references/structured-output.md` | Building `systemPrompt` + `outputSchema`, Exa's schema limits, parsing `structured.content` + `grounding`. **The maxed-out deep-reasoning recipe.** |
| `references/answer.md` | Using `/answer`, its limits (no model/depth control), when NOT to use it |
| `references/research-agent.md` | The async Agent API — launch/poll/cancel, effort, enrichment, beta header |
| `references/cost-limits-gotchas.md` | Pricing tells, rate limits, Windows/encoding gotchas, error→fix table |

## Common flags (all subcommands)

`--pretty` (indent), `--raw` (Exa's unmodified response), `--out FILE` (write to
file), `--timeout SECONDS` (per request; deep-reasoning needs ≥120).

## Reproducing the blog-skill scripts

This one script is a superset of the per-purpose Exa scripts in the blog skills:

| Old script | Equivalent here |
|---|---|
| `discover-keywords.py` (`type=auto`) | `search --type auto` |
| `serp-analyst.py` (deep-reasoning + prompt + schema) | `search --type deep-reasoning --system-prompt-file --output-schema-file` |
| `verify-with-exa.py` (deep-reasoning + verdict schema) | same, with a verdict schema |
| `exa-researcher.py` (N parallel per-H2 calls) | `search --batch calls.json` |

The domain-specific prompts/schemas stay in the calling skill and are passed in as
files — this skill owns the *transport*, not the content.
