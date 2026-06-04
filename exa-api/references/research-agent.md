# Async research: `research` (/research/v1) vs `agent` (/agent/runs)

Exa has **two** async products for multi-step work. They're different — pick by intent.

| | `research` | `agent` |
|---|---|---|
| Endpoint | `POST /research/v1` | `POST /agent/runs` |
| Status | **current / forward** (GA-style) | **beta** (`Exa-Beta` header) |
| Input field | `instructions` | `query` |
| Depth knob | `model` (3 tiers) | `effort` (5 tiers) |
| Strength | open-ended research → report or structured JSON | enrichment, list-building, row processing, follow-ups |
| Use for | "research topic X and give me a grounded answer/object" | "find N entities + emails", multi-step workflows |

**Default to `research`** — it's Exa's forward path. Reach for `agent` only when you
need its enrichment/workflow features (`input.data` rows, `previousRunId` follow-ups,
events) that the Research API doesn't offer.

---

## `research` — `POST /research/v1`

```bash
# Launch + poll to completion (default; up to --max-wait seconds)
python scripts/exa.py research --instructions "Compare X and Y for safety; cite sources" \
    --model exa-research --pretty

# Structured output -> output.parsed
python scripts/exa.py research --instructions "..." --output-schema-file schema.json --pretty

# Launch only / poll an existing run
python scripts/exa.py research --instructions "..." --no-wait        # returns researchId
python scripts/exa.py research --get r_01k... --pretty
```

| Flag | Values | Meaning |
|---|---|---|
| `--instructions` | string | what to research (required). `--query` is an alias. |
| `--model` | `exa-research-fast`, `exa-research` (default), `exa-research-pro` | cost/depth tier |
| `--output-schema[-file]` | JSON Schema | structured output → `output.parsed` |
| `--no-wait` | — | launch only, return `researchId` + `status` |
| `--get RESEARCH_ID` | — | poll/fetch an existing run |
| `--max-wait` | seconds (default 600) | give up polling after this long |

**No beta header required.** Response (normalized):

```json
{"researchId": "r_01k...", "status": "completed", "model": "exa-research-fast",
 "output": {"parsed": { ...your schema... }, "content": "...markdown report if no schema..."},
 "citations": [{"id": "...", "url": "...", "title": "..."}],
 "cost": {"total": 0.006, "numPages": 0.277, "numSearches": 1, "reasoningTokens": 172}}
```

- With a schema → read `output.parsed` (validated object). Without → `output.content`
  is a markdown report. `citations` lists sources.
- Endpoints: `POST /research/v1` (create), `GET /research/v1/{id}` (poll),
  `GET /research/v1` (list).

---

## `agent` — `POST /agent/runs` (beta)

Multi-step agent: searches, reads, reasons, and (optionally) **enriches** rows over
many steps. Asynchronous and **beta-gated** (`Exa-Beta` header, handled for you).

```bash
python scripts/exa.py agent --query "Find 10 Miami plastic surgeons with emails" --effort high --pretty
python scripts/exa.py agent --query "..." --no-wait        # launch only
python scripts/exa.py agent --get agent_run_abc123 --pretty
python scripts/exa.py agent --list                          # your team's runs
python scripts/exa.py agent --cancel agent_run_abc123
```

| Flag | Values | Meaning |
|---|---|---|
| `--query` | string | the task (required to launch) |
| `--effort` | `low`, `medium`, `high`, `xhigh`, `auto` | reasoning/compute budget |
| `--output-schema[-file]` | JSON Schema | force structured output |
| `--no-wait` / `--get` / `--cancel` / `--list` | — | launch-only / poll / cancel / list |
| `--beta-token` | token | override the `Exa-Beta` header (default in config.json) |

Response itemizes `cost` (`agentCompute` + `search` + `emails`/`phoneNumbers` for
enrichment). The launch body uses **`query`** (not `instructions`).

Raw endpoints: `POST /agent/runs`, `GET /agent/runs/{id}`, `GET /agent/runs`,
`POST /agent/runs/{id}/cancel`, `DELETE /agent/runs/{id}`, `GET /agent/runs/{id}/events`.
All require the `Exa-Beta` header.

---

## When NOT to use either

For a single synthesized, grounded answer over the SERP, **`search --type
deep-reasoning`** with `systemPrompt` + `outputSchema` is cheaper and synchronous —
prefer it (see `structured-output.md`). Use `research`/`agent` only for genuinely
multi-step, open-ended, or enrichment work.
