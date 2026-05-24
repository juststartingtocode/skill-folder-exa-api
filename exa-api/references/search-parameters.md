# Complete `/search` parameter coverage

Every parameter Exa's `POST /search` accepts is reachable. Three layers guarantee
**nothing is ever restricted** vs. the API reference or playground:

1. **First-class flags** for common params (table below).
2. **`--contents-json`** — pass the entire `contents` object as raw JSON (covers
   every nested sub-field, including ones with no convenience flag).
3. **`--extra-json` / `--extra-json-file`** — arbitrary JSON deep-merged into the
   request body **last**, so it can set or override ANY top-level param, present
   or future. This is the universal escape hatch.

Batch specs are full **passthrough**: each spec in the `--batch` array IS the Exa
request body (camelCase keys) plus an optional `name`. Any key the API accepts
passes straight through.

## Top-level parameters

| Exa param | Flag | Notes |
|---|---|---|
| `query` | `--query` | required (or `--batch`) |
| `type` | `--type` | no value restriction; known: instant, fast, auto, neural, keyword, deep-lite, deep, deep-reasoning |
| `category` | `--category` | company, people, research paper, news, financial report, … |
| `numResults` | `--num-results` | 1–100 |
| `includeDomains` | `--include-domains` | comma-separated |
| `excludeDomains` | `--exclude-domains` | comma-separated |
| `includeText` | `--include-text` | phrase a result must contain |
| `excludeText` | `--exclude-text` | phrase a result must not contain |
| `startPublishedDate` | `--start-published-date` | ISO 8601 |
| `endPublishedDate` | `--end-published-date` | ISO 8601 |
| `startCrawlDate` | `--start-crawl-date` | ISO 8601 |
| `endCrawlDate` | `--end-crawl-date` | ISO 8601 |
| `moderation` | `--moderation` | flag |
| `userLocation` | `--user-location` | two-letter ISO country code |
| `compliance` | `--compliance hipaa` | **enterprise-only**; non-enterprise keys get a clean 403 |
| `systemPrompt` | `--system-prompt[-file]` | steers structured synthesis |
| `outputSchema` | `--output-schema[-file]` | structured output (see structured-output.md) |
| `additionalQueries` | `--additional-queries` | comma-separated, max 10 |
| `stream` | `--stream` | SSE; prints data chunks |
| anything else / future | `--extra-json` | universal |

## `contents` sub-fields

Convenience flags: `--text`, `--highlights`, `--highlights-query`, `--summary`,
`--summary-query`, `--max-characters`, `--livecrawl`.

For everything else under `contents` — `text.includeHtmlTags`, `text.verbosity`
(compact/standard/full), `text.includeSections`/`excludeSections`,
`summary.schema`, `extras.{links,imageLinks,richLinks,richImageLinks,codeBlocks}`,
`livecrawlTimeout`, `maxAgeHours`, `subpages`, `subpageTarget` — use
**`--contents-json`** with the full object:

```bash
python exa.py search --query "..." --type auto \
  --contents-json '{"text":{"verbosity":"compact"},"extras":{"links":10},"subpages":2}'
```

## Examples that exercise the hatch

```bash
# Override numResults via extra-json (override wins over the flag)
python exa.py search --query "..." --num-results 3 --extra-json '{"numResults":1}'

# Set a param that has no flag yet
python exa.py search --query "..." --extra-json '{"someNewExaParam":true}'

# Full contents control
python exa.py search --query "..." --contents-json '{"summary":{"schema":{...}},"extras":{"imageLinks":5}}'
```

`/answer` and `research` also accept `--extra-json` / `--extra-json-file` for the
same guarantee on their endpoints.
