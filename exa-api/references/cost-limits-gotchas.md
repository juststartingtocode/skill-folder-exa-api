# Cost, limits, and gotchas

## Cost ladder (measured, same simple query)

| Call | Cost | Notes |
|---|---|---|
| `answer` | ~$0.005 | flat; no itemized search line |
| `search` auto/neural/fast | ~$0.007 | `cost.search.neural` |
| `search deep-reasoning` + schema | ~$0.017 | 12–20 results, ~17s |
| `research` (low effort) | ~$0.025 | `agentCompute` + `search` itemized |

Billing is computed from Exa's server-side usage counters, not the `cost` object
in the response — treat `cost` as an estimate.

## Rate limits

- `deep-reasoning` ≈ **5 calls/second**. The `--batch` runner processes specs in
  chunks of `rate_limit` (config, default 5) with a ~1.2s gap and retries 429.
- On 429/500/502/503/504/**524**, `exa.py` retries up to 2× with backoff. **524**
  is an Exa upstream timeout (not auth) — usually succeeds on retry.

## Windows / encoding gotchas

- **Pass big prompts/schemas as files**, not inline. The Windows command line caps
  at ~8191 chars and `cmd.exe` mangles `?`, `&`, `=` inside JSON args. `exa.py`
  reads `--system-prompt-file` / `--output-schema-file` to sidestep this.
- `exa.py` forces UTF-8 stdout/stderr so Exa's smart quotes and direction marks
  (e.g. `‎` in some Wikipedia URLs) don't crash Windows' cp1252 console.
- Calling from Python? Invoke `python exa.py ...` directly. Don't shell out through
  the `gws`-style `.cmd` wrappers; those are a different tool's problem.

## Auth

- Resolution order: **`EXA_API_KEY` env var**, then `~/.claude.json`
  (`mcpServers.exa.url` → `?exaApiKey=`).
- To use the skill from any agent/session, set a Windows **User** env var once:
  `[Environment]::SetEnvironmentVariable('EXA_API_KEY','<key>','User')`.
- This skill calls the **REST API directly** — it does NOT depend on the Exa MCP
  server (whose config has drifted to deprecated tools). That's intentional and
  more reliable.

## Error → fix

| Symptom | Cause | Fix |
|---|---|---|
| `MISSING_BETA_HEADER` on `research` | no `Exa-Beta` header | handled by script; if overriding, pass a valid `--beta-token` |
| 400 "Unrecognized key 'instructions'" | wrong field on agent launch | use `query`, not `instructions` (script does this) |
| HTTP 524 | Exa upstream timeout | retry (script auto-retries) |
| empty `resolvedSearchType` | Exa often omits it | read engine from `cost.search.*` instead |
| structured arrays contain `"citations [1,2]"` | grounding leakage | filter non-content entries (see structured-output.md) |
| `UnicodeEncodeError` cp1252 | Windows console | script forces UTF-8; if you copied the code, keep the `reconfigure` block |
| `No Exa API key` | env + config both empty | set `EXA_API_KEY` |
| 403 `FEATURE_DISABLED` HIPAA | `--compliance hipaa` on a non-enterprise key | enterprise-only feature; not a script bug — the param was sent correctly |
| a param "does nothing" | no first-class flag for it | use `--extra-json '{...}'` (top-level) or `--contents-json` (inside contents) |
