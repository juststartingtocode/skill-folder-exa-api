# `/contents` — extract contents for URLs you already have

`POST /contents` crawls/extracts a list of URLs (or Exa result `ids`) and returns
their text, summary, highlights, links, etc. It's `/search` minus the discovery
step: **you supply the URLs**, Exa returns their contents. (Equivalent to the Exa
MCP `crawling_exa` tool.)

## Call it

```bash
# Plain text + summary for two URLs
python scripts/exa.py contents --urls "https://a.com/x,https://b.com/y" --text --summary

# Custom highlights + cap characters
python scripts/exa.py contents --urls "https://a.com/x" \
    --highlights --highlights-query "pricing" --max-characters 3000 --pretty

# Full control of every content field
python scripts/exa.py contents --urls "https://a.com/x" \
    --contents-json '{"summary":{"schema":{...}},"extras":{"links":10,"imageLinks":5},"subpages":2}'

# From Exa result ids (instead of raw URLs)
python scripts/exa.py contents --ids "id1,id2" --text
```

## Parameters

| Flag | Effect |
|---|---|
| `--urls` | comma-separated URLs to extract (1–100). Required (or `--ids`). |
| `--ids` | comma-separated Exa result ids (alternative to `--urls`) |
| `--text` | full page text (`--max-characters` caps it) |
| `--summary` / `--summary-query` | AI summary (optionally guided) |
| `--highlights` / `--highlights-query` | relevant snippets |
| `--max-characters` | cap text/highlight length (1–10,000) |
| `--max-age-hours` | cache freshness: `-1`..`720`; `0` = fetch fresh |
| `--subpages` | 0–100 subpages to crawl per URL |
| `--livecrawl` | **deprecated** by Exa → use `--max-age-hours` |
| `--compliance hipaa` | enterprise-only |
| `--contents-json` | full content block as raw JSON (overrides the flags) |
| `--extra-json` | any top-level param (universal escape hatch) |

The content fields are sent at the **top level** of the `/contents` body (not
nested under `contents` as they are in `/search`) — the script handles this.

## Response (normalized)

```json
{
  "numResults": 2,
  "cost": {"total": 0.002, "contents": {"text": 0.001, "summary": 0.001}},
  "statuses": [{"id": "https://a.com/x", "status": "success", "source": "crawled"}],
  "results": [{"url": "...", "title": "...", "summary": "...", "highlights": [...], "text": "..."}]
}
```

`statuses` tells you per-URL whether the content came from Exa's **cache** or a
fresh **crawl**, and whether each URL succeeded. Use `--raw` for Exa's full body.

## When to use `contents` vs `search`

- **`contents`** — you already know the URLs (from a previous search, a sitemap, a
  user-supplied list) and just need their content. Cheaper: no search step.
- **`search`** — you have a *query* and need Exa to find the URLs. `search` can also
  return contents in the same call (its `--text`/`--summary`/`--highlights` flags),
  so you rarely need a separate `contents` call right after a search.
