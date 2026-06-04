# Search types (`--type`)

`POST /search` exposes a ladder of search engines via `type`. They trade latency
and cost for reasoning depth. Pick the cheapest one that answers your need.

| `--type` | Latency | What it is | Use when |
|---|---|---|---|
| `instant` | ~250 ms | fastest index lookup | real-time chat/voice autocomplete |
| `fast` | ~450 ms | speed with minimal quality loss | high-volume, latency-sensitive |
| `auto` | ~1 s | **default**; picks neural vs keyword per query | general retrieval, keyword discovery |
| `deep-lite` | ~4 s | lightweight multi-step retrieval | light synthesis, cheaper than deep |
| `deep` | 4–15 s | multi-step reasoning retrieval | complex queries needing several hops |
| `deep-reasoning` | 12–40 s | heaviest synthesized reasoning | hard research; structured grounded output |

The six above are the **currently documented** types. `auto` is the default and
internally chooses neural (semantic) vs keyword (literal) per query — so you rarely
need to ask for those directly.

**Legacy (undocumented but still functional):** `neural` (embeddings/semantic,
"find pages *like* this") and `keyword` (literal term matching). Exa dropped them
from the docs and folded them into `auto`, but `POST /search` **still accepts both**
(verified live — they return `cost.search.neural` / `cost.search.keyword`). The
`--type` flag has no value restriction, so they keep working; prefer `auto` for new
code and only force `neural`/`keyword` when you specifically need that engine.

## Which billing path did I get?

`resolvedSearchType` is often returned empty. Read the engine off the **cost
breakdown** instead:
- `cost.search.neural` → a neural search ran.
- `cost.search.keyword` → a keyword search ran.
- For `deep*` types with structured output, cost is reported as a flat
  `cost.total` (the synthesis LLM is bundled in).

Measured examples (same query):
- `auto`/`neural`/`fast`: `cost.total = 0.007`, `{"search": {"neural": 0.007}}`
- `keyword`: `{"search": {"keyword": 0.007}}`
- `deep-reasoning` + schema, 12–20 results: `cost.total ≈ 0.017`, ~17 s

## Plain vs structured

- **Plain** (no `--output-schema`): you get a `results` list (URLs, titles,
  optional `text`/`highlights`/`summary`). The agent reads/synthesizes itself.
- **Structured** (`--output-schema` + usually `--system-prompt`): Exa runs an
  LLM over the results and returns `structured.content` (your schema) +
  `structured.grounding` (per-field citations + confidence). Only worth it on
  `deep`/`deep-reasoning`. See `structured-output.md`.

## Cost discipline

`deep-reasoning` is the most expensive sync type and the blog skills fire 6+ in
parallel per article. Use `auto` for cheap link/keyword gathering; reserve
`deep-reasoning` for calls that genuinely need synthesized, grounded claims.
`deep` or `deep-lite` are reasonable middle tiers for lighter research (e.g. FAQ
answers) if you want to cut cost/latency.
