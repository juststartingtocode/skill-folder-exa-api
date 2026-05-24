# Structured output (the maxed-out deep-reasoning recipe)

This is the highest-value Exa pattern: a `deep-reasoning` search with a
`systemPrompt` and an `outputSchema`. Exa searches, reasons over the results,
and returns your exact JSON shape **plus per-field citations and confidence**.

## How to call it

```bash
python scripts/exa.py search \
    --query "What does tummy tuck recovery look like week by week?" \
    --type deep-reasoning --num-results 20 \
    --system-prompt-file prompt.txt \
    --output-schema-file schema.json \
    --highlights --highlights-query "recovery timeline statistics" --max-characters 3000 \
    --include-domains plasticsurgery.org,fda.gov \
    --pretty --out research.json
```

- `--system-prompt-file` — your instructions to Exa's synthesis model (role,
  what to extract, source priorities). Pass as a file, not inline.
- `--output-schema-file` — a JSON Schema describing the object you want back.
- `--highlights` + `--highlights-query` — improves Exa's internal analysis by
  pulling the most relevant ~3000 chars from each result. Recommended for
  deep-reasoning; you usually don't need `--text`.

## What you get back

The normalized response (default, non-`--raw`):

```json
{
  "resolvedSearchType": "",
  "cost": {"total": 0.017},
  "numResults": 20,
  "structured": {
    "content": { ...your schema... },
    "grounding": [
      {"field": "claims[0].claim",
       "citations": [{"url": "...", "title": "..."}],
       "confidence": "high"}
    ]
  },
  "results": [ ...the underlying pages... ],
  "elapsed_seconds": 17.2
}
```

- `structured.content` = your schema, filled in. **This is the payload.**
- `structured.grounding` = citations + confidence keyed by **field path**
  (`claims[0].claim`, `claims[0].source`, `stats[2].stat`, ...). Use it to attach
  source URLs to each claim for linking/verification.

In `--raw` mode this lives at `output.content` / `output.grounding` in Exa's
response.

## Exa's schema limits (important)

- **Max ~10 properties total across all nesting levels.** Count top-level +
  nested. A 2-top-level + 4-nested schema = 6 (fine). Exceeding this fails or
  truncates.
- **Max depth ~2.** Don't nest objects more than two levels deep.
- Keep `description` fields specific — they steer extraction quality more than
  the systemPrompt for individual fields.

## Schema patterns that work

**Synthesis + claims** (research a section):
```json
{"type":"object","properties":{
  "synthesis":{"type":"string","description":"200-300 word answer with numbers and sources inline"},
  "claims":{"type":"array","items":{"type":"object","properties":{
    "claim":{"type":"string"},"source":{"type":"string"},"confidence":{"type":"string"}}}}},
 "required":["synthesis","claims"]}
```

**Verdict** (verify claims):
```json
{"type":"object","properties":{
  "verifications":{"type":"array","items":{"type":"object","properties":{
    "original_claim":{"type":"string"},
    "verdict":{"type":"string","description":"supported, contradicted, or insufficient_evidence"},
    "evidence":{"type":"string"},"source":{"type":"string"}}}}}}
```

## Grounding leakage gotcha

`deep-reasoning` sometimes leaks grounding metadata (`"citations [1,2,3]"`,
`"confidence high"`) into string-array fields like an FAQ list. If your schema has
arrays of plain strings, filter entries that don't look like real content (e.g.
questions must end with `?` and not start with `citations`/`confidence`).

## Cost / time (measured)

A single `deep-reasoning` + schema call over 12–20 results: **~$0.017, ~17 s**.
Two in parallel via `--batch`: **~$0.034 total, ~10 s wall** (true concurrency).
Rate limit is ~5 deep-reasoning calls/sec — the `--batch` runner respects it.
