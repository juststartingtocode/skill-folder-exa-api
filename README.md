# exa-api

A reusable AI-agent **skill** that wraps the [Exa](https://exa.ai) web API behind one
reliable Python entrypoint. The hard-won know-how — which endpoint to hit, which
search type to pick, which knobs matter, and every Windows/encoding gotcha — is
distilled into the skill so any agent can call Exa correctly without rediscovering it.

This skill owns the **transport** (auth, retry, rate-limiting, payload building,
response parsing). It does **not** own domain content: callers pass their own
`systemPrompt` and `outputSchema` as files.

## What it does

Everything routes through one script, `exa-api/scripts/exa.py`, with three subcommands:

| You want… | Subcommand | Exa endpoint | Returns |
|---|---|---|---|
| Web pages for a query (retrieval), optionally structured | `search` | `POST /search` | results list, or structured `output` if you pass a schema |
| One cited answer, zero config | `answer` | `POST /answer` | answer string/dict + citations |
| A long-running agent that searches, reasons, and enriches | `research` | `POST /agent/runs` | async run → text + structured + grounding |

It supports the full `/search` surface (every parameter has a flag, plus
`--extra-json` / `--contents-json` escape hatches), parallel rate-limited batch
calls, deep-reasoning structured output, and the async Research Agent API.

## Install

This is an [agent skill](https://skills.sh). Install it globally for all your agents
(Claude Code CLI, Desktop, and others) with [`npx skills`](https://skills.sh):

```bash
npx skills add juststartingtocode/skill-folder-exa-api -g --all
```

## Use

Once installed, an agent invokes it via the skill's `SKILL.md`. To run the script
directly:

```bash
SKILL_DIR=<path to the installed exa-api/ folder>
python $SKILL_DIR/scripts/exa.py search --query "tummy tuck recovery" --type auto --num-results 10
```

Auth resolves automatically: the `EXA_API_KEY` environment variable first, then
`~/.claude.json` (`mcpServers.exa.url` → `exaApiKey`). Set `EXA_API_KEY` once as a
user environment variable to use it anywhere.

See `exa-api/SKILL.md` for the full decision guide, quick-start examples, and the
reference-doc index (`exa-api/references/`).

## Layout

```
exa-api/                 # the installable skill (this is what npx detects)
  SKILL.md               # orchestrator: which subcommand, how to run, doc index
  config.json            # base URL, beta token, rate limit, timeout, default type
  scripts/exa.py         # the single entrypoint: search | answer | research
  references/            # the know-how docs the agent reads on demand
```

## License

Private. © juststartingtocode.
