# `/agent/runs` — the async Research / Agent API

This is Exa's separate **multi-step agent** product: it searches, reads, reasons,
and (optionally) enriches over many steps, then returns a grounded result. It is
**asynchronous** and **beta-gated**.

## Call it

```bash
# Launch + poll to completion (default; up to --max-wait seconds)
python scripts/exa.py research --query "Compare X and Y; cite sources" --effort high --pretty

# Launch only, get the run id back (poll later)
python scripts/exa.py research --query "..." --no-wait

# Poll / fetch an existing run
python scripts/exa.py research --get agent_run_abc123 --pretty
```

The script sets the required `Exa-Beta` header (default token `agent-2026-05-07`,
in `config.json`) and polls every `--poll-interval` (default 5s).

## Knobs

| Flag | Values | Meaning |
|---|---|---|
| `--effort` | `low`, `medium`, `high`, `xhigh`, `auto` | reasoning/compute budget (cost ↑ with effort) |
| `--output-schema[-file]` | JSON Schema | force structured output instead of prose |
| `--no-wait` | — | launch only, return `id` + `status` |
| `--get RUN_ID` | — | poll an existing run instead of launching |
| `--max-wait` | seconds (default 600) | give up polling after this long |
| `--beta-token` | token | override the Exa-Beta header |

## Response

```json
{"id": "agent_run_...", "status": "completed",
 "output": {"text": "...", "structured": null,
            "grounding": [{"field":"text","citations":[...],"score":0.9,"confidence":"high"}]},
 "cost": {"total": 0.025, "agentCompute": 0.01, "search": 0.015, "emails": 0, "phoneNumbers": 0}}
```

The `cost` object itemizes `agentCompute` + `search` (+ `emails`/`phoneNumbers`
for enrichment runs) — unlike `/answer`, this one is transparent.

## The endpoints (raw)

| Method + path | Purpose |
|---|---|
| `POST /agent/runs` | launch a run (body: `query`, `effort`, optional `outputSchema`) |
| `GET /agent/runs/{id}` | fetch a run's status/output |
| `GET /agent/runs` | list your team's runs |
| `POST /agent/runs/{id}/cancel` | stop a run |
| `DELETE /agent/runs/{id}` | delete a stored run |
| `GET /agent/runs/{id}/events` | replay run events (streaming) |

All require the `Exa-Beta` header. The launch body uses **`query`** (not
`instructions` — that returns a 400).

## When to use

Use `research` for genuinely multi-step work: open-ended research questions,
building lists of entities, enriching records (emails/phones), follow-up reasoning
that one search call can't satisfy. For a single synthesized, grounded answer over
the SERP, `search --type deep-reasoning` is cheaper and synchronous — prefer it.
