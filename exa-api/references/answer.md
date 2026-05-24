# `/answer` — quick cited answer (and when NOT to use it)

`POST /answer` runs a search internally, then an LLM writes a synthesized answer
with citations. It is a **no-knobs convenience appliance**.

## Call it

```bash
python scripts/exa.py answer --query "What is the capital of Australia?" --pretty
python scripts/exa.py answer --query "..." --text                 # include full citation text
python scripts/exa.py answer --query "..." --output-schema-file s.json   # typed answer
python scripts/exa.py answer --query "..." --stream                # SSE chunks to stdout
```

## Parameters (that's all there is)

| Flag | Effect |
|---|---|
| `--query` | the question (required) |
| `--text` | include full page text of citations (default off) |
| `--output-schema[-file]` | return `answer` as a typed object instead of prose |
| `--stream` | stream the answer as server-sent events |

## Response

```json
{"answer": "The capital of Australia is Canberra ([Wikipedia](...), ...).",
 "citations": [{"url": "...", "title": "...", "publishedDate": "..."}],
 "cost": {"total": 0.005}}
```

With `--output-schema`, `answer` is a dict, e.g. `{"city":"Canberra","population":523285}`.

## The limits (why it's a black box)

- **No `model` parameter.** Exa picks the LLM and does not document which.
- **No `systemPrompt`.** You cannot steer tone, depth, or extraction.
- **No `type`/depth control.** You cannot make the underlying search deeper.
- Cost is a flat **~$0.005** with **no itemized search line** — cheaper than a
  standalone neural search ($0.007), which tells you it uses a lighter internal
  retrieval, not full neural search at list price.

## When to use vs not

**Use `/answer`** for: quick factual lookups, chatbot/voice answers, anything
where "good enough, cited, zero config, ~2s" is the bar.

**Do NOT use `/answer`** when you need: control over reasoning depth, a custom
research prompt, domain-restricted sources, or a strict multi-field output shape.
For those, use **`search --type deep-reasoning`** with `systemPrompt` +
`outputSchema` (see `structured-output.md`), or **`research`** (the async agent)
for multi-step work. The blog skills deliberately use `search`, never `/answer`,
for exactly this reason.
