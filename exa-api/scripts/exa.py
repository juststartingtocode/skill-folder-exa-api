#!/usr/bin/env python3
"""exa.py — One entrypoint for every Exa API call an agent needs.

Five subcommands, all sharing one auth/retry/parse core. Pick by intent:

  search    POST /search          Discover web pages for a QUERY. Every search
                                  type (instant, fast, auto, deep-lite, deep,
                                  deep-reasoning; legacy neural/keyword still
                                  work). Plain results OR synthesized structured
                                  output (systemPrompt + outputSchema). Single
                                  call (flags) OR --batch (parallel, rate-limited).

  contents  POST /contents        Extract text/highlights/summary/links for URLs
                                  you ALREADY have (crawl/scrape known pages). No
                                  query — you pass --urls (or --ids from a search).

  answer    POST /answer          One cited ANSWER to a question (sync RAG). No
                                  model/depth knobs. Optional outputSchema, stream.

  research  POST /research/v1      Exa's Research API — async agentic research from
                                  natural-language INSTRUCTIONS. Models:
                                  exa-research-fast | exa-research | exa-research-pro.
                                  Optional outputSchema -> output.parsed. This is
                                  Exa's current/forward research product. Launch +
                                  poll, or --no-wait, or --get <researchId>.

  agent     POST /agent/runs       Exa Agent API (BETA, Exa-Beta header) — multi-step
                                  agentic workflows with row enrichment (input.data),
                                  follow-ups (previousRunId), events. Use for
                                  list-building / enrichment the Research API can't do.
                                  Launch + poll, --no-wait, --get, --cancel, --list.

Auth: EXA_API_KEY env var first, then ~/.claude.json mcpServers.exa.url
(?exaApiKey=...). Set EXA_API_KEY as a Windows User env var to use anywhere.

Big prompts / schemas: pass via --system-prompt-file / --output-schema-file to
avoid the Windows ~8191-char command-line limit and URL-mangling of JSON args.

Examples
--------
  # Cheap keyword discovery (plain results)
  python exa.py search --query "tummy tuck recovery" --type auto --num-results 10

  # Maxed-out deep-reasoning structured research (the heavy sync path)
  python exa.py search --query "tummy tuck recovery timeline" \
      --type deep-reasoning --num-results 20 \
      --system-prompt-file prompt.txt --output-schema-file schema.json \
      --highlights --highlights-query "recovery timeline statistics" \
      --include-domains plasticsurgery.org,fda.gov --pretty

  # Parallel multi-call (reproduces the per-H2 researcher pattern)
  python exa.py search --batch calls.json --pretty --out research.json

  # Extract contents for URLs you already have
  python exa.py contents --urls "https://a.com/x,https://b.com/y" --text --summary

  # Quick cited answer
  python exa.py answer --query "What is the capital of Australia?" --pretty

  # Async deep research (new Research API)
  python exa.py research --instructions "Compare X vs Y, cite sources" --model exa-research --pretty

  # Beta Agent API (enrichment / multi-step workflows)
  python exa.py agent --query "Find 10 plastic surgeons in Miami with emails" --effort high --pretty
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
except ImportError:
    print(json.dumps({"error": True, "message": "pip install requests"}), file=sys.stderr)
    sys.exit(1)

# --------------------------------------------------------------------------- #
# Defaults (overridable via config.json next to this script, or via flags)
# --------------------------------------------------------------------------- #
BASE_URL = "https://api.exa.ai"
# Documented /search types (auto picks neural vs keyword for you). The legacy
# "neural" and "keyword" are no longer in Exa's docs but STILL work on /search,
# so we never restrict --type — pass any value, current/legacy/future.
SEARCH_TYPES = ["instant", "fast", "auto", "deep-lite", "deep", "deep-reasoning",
                "neural", "keyword"]
RESEARCH_MODELS = ["exa-research-fast", "exa-research", "exa-research-pro"]
EFFORT_LEVELS = ["low", "medium", "high", "xhigh", "auto"]   # agent API
DEFAULT_BETA_TOKEN = "agent-2026-05-07"   # Exa-Beta header for the Agent API
DEFAULT_RESEARCH_MODEL = "exa-research"   # balanced default for /research/v1
DEFAULT_RATE_LIMIT = 5                     # deep-reasoning is ~5 calls/sec
DEFAULT_TIMEOUT = 180                      # deep-reasoning can take 12-40s+
RETRY_STATUS = {429, 500, 502, 503, 504, 524}  # 524 = Exa upstream timeout
MAX_RETRIES = 2
TERMINAL = {"completed", "complete", "failed", "error", "canceled", "cancelled"}


def load_config():
    """Merge config.json (sibling of scripts/) over the built-in defaults."""
    cfg = {
        "base_url": BASE_URL,
        "beta_token": DEFAULT_BETA_TOKEN,
        "research_model": DEFAULT_RESEARCH_MODEL,
        "rate_limit": DEFAULT_RATE_LIMIT,
        "timeout": DEFAULT_TIMEOUT,
        "default_search_type": "auto",
    }
    here = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(os.path.dirname(here), "config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                user_cfg = json.load(f)
            cfg.update({k: v for k, v in user_cfg.items() if v is not None})
        except (json.JSONDecodeError, OSError):
            pass
    return cfg


def get_api_key():
    """Resolve the Exa API key: EXA_API_KEY env, then ~/.claude.json."""
    key = os.environ.get("EXA_API_KEY")
    if key:
        return key
    claude_config = os.path.expanduser("~/.claude.json")
    if os.path.exists(claude_config):
        try:
            with open(claude_config, encoding="utf-8") as f:
                config = json.load(f)
            url = config.get("mcpServers", {}).get("exa", {}).get("url", "")
            params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            keys = params.get("exaApiKey", [])
            if keys:
                return keys[0]
        except (json.JSONDecodeError, OSError):
            pass
    return None


def post(cfg, api_key, path, payload, extra_headers=None, timeout=None):
    """POST with retry on transient failures. Returns (ok, data_or_error, elapsed)."""
    url = cfg["base_url"].rstrip("/") + path
    headers = {"Content-Type": "application/json", "x-api-key": api_key}
    if extra_headers:
        headers.update(extra_headers)
    timeout = timeout or cfg["timeout"]

    last_err = None
    start = time.time()
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        except requests.exceptions.Timeout:
            last_err = {"error": True, "message": f"Request timed out after {timeout}s"}
        except requests.exceptions.RequestException as e:
            last_err = {"error": True, "message": f"Request failed: {e}"}
        else:
            if resp.status_code in (200, 201):
                return True, resp.json(), round(time.time() - start, 2)
            last_err = {
                "error": True,
                "status_code": resp.status_code,
                "message": resp.text[:500],
            }
            if resp.status_code not in RETRY_STATUS:
                break
        if attempt < MAX_RETRIES:
            time.sleep(2 + 2 * attempt)  # 2s, 4s backoff
    last_err["elapsed_seconds"] = round(time.time() - start, 2)
    return False, last_err, last_err["elapsed_seconds"]


def get(cfg, api_key, path, extra_headers=None, timeout=None):
    url = cfg["base_url"].rstrip("/") + path
    headers = {"x-api-key": api_key}
    if extra_headers:
        headers.update(extra_headers)
    try:
        resp = requests.get(url, headers=headers, timeout=timeout or cfg["timeout"])
    except requests.exceptions.RequestException as e:
        return False, {"error": True, "message": str(e)}
    if resp.status_code == 200:
        return True, resp.json()
    return False, {"error": True, "status_code": resp.status_code, "message": resp.text[:500]}


# --------------------------------------------------------------------------- #
# Shared helpers for building payloads
# --------------------------------------------------------------------------- #
def read_text_arg(inline, file_path):
    """Return inline value, else file contents, else None."""
    if inline:
        return inline
    if file_path:
        with open(file_path, encoding="utf-8") as f:
            return f.read()
    return None


def read_json_arg(inline, file_path):
    raw = read_text_arg(inline, file_path)
    if raw is None:
        return None
    return json.loads(raw)


def split_csv(val):
    if not val:
        return None
    return [v.strip() for v in val.split(",") if v.strip()]


def build_contents(args):
    """Assemble the content-extraction block (text/highlights/summary/extras/...).

    Used by BOTH search (nested under `contents`) and the contents command
    (spread at top level). `--contents-json` overrides everything.
    """
    if getattr(args, "contents_json", None):
        return json.loads(args.contents_json)
    contents = {}
    if getattr(args, "highlights", False):
        hl = {}
        if args.highlights_query:
            hl["query"] = args.highlights_query
        if args.max_characters:
            hl["maxCharacters"] = args.max_characters
        contents["highlights"] = hl or True
    if getattr(args, "summary", False):
        contents["summary"] = ({"query": args.summary_query} if args.summary_query else True)
    if getattr(args, "text", False):
        contents["text"] = ({"maxCharacters": args.max_characters}
                            if args.max_characters else True)
    if getattr(args, "livecrawl", None):
        contents["livecrawl"] = args.livecrawl          # deprecated; prefer maxAgeHours
    if getattr(args, "max_age_hours", None) is not None:
        contents["maxAgeHours"] = args.max_age_hours    # replaces livecrawl
    if getattr(args, "subpages", None) is not None:
        contents["subpages"] = args.subpages
    return contents or None


def deep_merge(base, override):
    """Recursively merge override into base (override wins). Returns base."""
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def build_search_payload(spec, cfg):
    """Passthrough: a spec IS the Exa /search body (camelCase keys) plus an
    optional `name` (stripped). Any key the API accepts — current or future —
    passes straight through, so nothing is ever restricted. `type`/`numResults`
    are defaulted only if absent. None/empty values are dropped.
    """
    payload = {k: v for k, v in spec.items()
               if k != "name" and v is not None and v != [] and v != {}}
    payload.setdefault("type", cfg["default_search_type"])
    payload.setdefault("numResults", 10)
    return payload


def normalize_search(data, raw=False):
    """Turn a raw /search response into a clean shape.

    - If structured output was requested, surface output.content + grounding.
    - Otherwise surface the results list.
    """
    if raw:
        return data
    out = {
        "cost": data.get("costDollars", {}),
        "numResults": len(data.get("results", [])),
    }
    structured = data.get("output")
    if structured:
        out["structured"] = {
            "content": structured.get("content"),
            "grounding": structured.get("grounding", []),
        }
    out["results"] = [
        {
            "url": r.get("url", ""),
            "title": r.get("title", ""),
            "publishedDate": r.get("publishedDate"),
            "highlights": r.get("highlights"),
            "summary": r.get("summary"),
            "text": (r.get("text")[:1000] if r.get("text") else None),
        }
        for r in data.get("results", [])
    ]
    return out


# --------------------------------------------------------------------------- #
# Subcommand: search
# --------------------------------------------------------------------------- #
def cmd_search(args, cfg, api_key):
    if args.batch:
        return run_batch(args, cfg, api_key)

    if not args.query:
        return {"error": True, "message": "--query is required (or use --batch)"}

    spec = {
        "query": args.query,
        "type": args.type,
        "numResults": args.num_results,
        "category": args.category,
        "systemPrompt": read_text_arg(args.system_prompt, args.system_prompt_file),
        "outputSchema": read_json_arg(args.output_schema, args.output_schema_file),
        "contents": build_contents(args),
        "includeDomains": split_csv(args.include_domains),
        "excludeDomains": split_csv(args.exclude_domains),
        "includeText": [args.include_text] if args.include_text else None,
        "excludeText": [args.exclude_text] if args.exclude_text else None,
        "startPublishedDate": args.start_published_date,
        "endPublishedDate": args.end_published_date,
        "startCrawlDate": args.start_crawl_date,
        "endCrawlDate": args.end_crawl_date,
        "additionalQueries": (split_csv(args.additional_queries) or [])[:10],
        "moderation": True if args.moderation else None,
        "userLocation": args.user_location,
        "compliance": args.compliance,
        "stream": True if args.stream else None,
    }
    payload = build_search_payload(spec, cfg)
    # Escape hatch: deep-merge arbitrary JSON last so ANY param (present or
    # future) can be set or overridden — guarantees full API parity.
    extra = read_json_arg(args.extra_json, args.extra_json_file)
    if extra:
        deep_merge(payload, extra)
    if args.stream:
        return stream_post(cfg, api_key, "/search", payload, args.timeout)
    ok, data, elapsed = post(cfg, api_key, "/search", payload, timeout=args.timeout)
    if not ok:
        data["elapsed_seconds"] = elapsed
        return data
    result = normalize_search(data, raw=args.raw)
    if not args.raw:
        result["elapsed_seconds"] = elapsed
    return result


def run_batch(args, cfg, api_key):
    """Run N search specs in parallel, rate-limited and retried."""
    with open(args.batch, encoding="utf-8") as f:
        specs = json.load(f)
    if not isinstance(specs, list):
        return {"error": True, "message": "--batch file must be a JSON array of call specs"}

    rate = args.rate_limit or cfg["rate_limit"]
    results = {}
    total_start = time.time()

    def do_one(idx, spec):
        name = spec.get("name", f"call_{idx}")
        payload = build_search_payload(spec, cfg)
        ok, data, elapsed = post(cfg, api_key, "/search", payload, timeout=args.timeout)
        if not ok:
            return name, {"error": True, **data}
        norm = normalize_search(data, raw=args.raw)
        if not args.raw:
            norm["elapsed_seconds"] = elapsed
        return name, norm

    # Process in rate-sized batches with a 1s gap between batches.
    for start_i in range(0, len(specs), rate):
        chunk = list(enumerate(specs))[start_i:start_i + rate]
        if start_i > 0:
            time.sleep(1.2)
        with ThreadPoolExecutor(max_workers=rate) as ex:
            futures = {ex.submit(do_one, i, s): i for i, s in chunk}
            for fut in as_completed(futures):
                name, res = fut.result()
                results[name] = res
                tag = "ERROR " + str(res.get("message", ""))[:60] if res.get("error") else \
                    f"{res.get('numResults', 0)} results, {res.get('elapsed_seconds', '?')}s"
                print(f"  {name}: {tag}", file=sys.stderr)

    return {
        "batch": True,
        "num_calls": len(specs),
        "num_errors": sum(1 for r in results.values() if r.get("error")),
        "total_elapsed_seconds": round(time.time() - total_start, 1),
        "total_cost": round(sum(
            (r.get("cost", {}) or {}).get("total", 0)
            for r in results.values() if not r.get("error")
        ), 4),
        "results": results,
    }


# --------------------------------------------------------------------------- #
# Subcommand: contents  (POST /contents)
# --------------------------------------------------------------------------- #
def cmd_contents(args, cfg, api_key):
    urls = split_csv(args.urls)
    ids = split_csv(args.ids)
    if not urls and not ids:
        return {"error": True, "message": "--urls (or --ids) is required"}

    payload = {}
    if urls:
        payload["urls"] = urls
    if ids:
        payload["ids"] = ids
    if args.compliance:
        payload["compliance"] = args.compliance
    # Content-extraction fields go at the TOP level on /contents (not nested).
    fields = build_contents(args)
    if fields:
        payload.update(fields)
    extra = read_json_arg(args.extra_json, args.extra_json_file)
    if extra:
        deep_merge(payload, extra)

    ok, data, elapsed = post(cfg, api_key, "/contents", payload, timeout=args.timeout)
    if not ok:
        data["elapsed_seconds"] = elapsed
        return data
    if args.raw:
        return data
    return {
        "numResults": len(data.get("results", [])),
        "cost": data.get("costDollars", {}),
        "statuses": data.get("statuses", []),
        "results": [
            {
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "publishedDate": r.get("publishedDate"),
                "summary": r.get("summary"),
                "highlights": r.get("highlights"),
                "text": (r.get("text")[:1000] if r.get("text") else None),
            }
            for r in data.get("results", [])
        ],
        "elapsed_seconds": elapsed,
    }


# --------------------------------------------------------------------------- #
# Subcommand: answer  (POST /answer)
# --------------------------------------------------------------------------- #
def cmd_answer(args, cfg, api_key):
    if not args.query:
        return {"error": True, "message": "--query is required"}
    payload = {"query": args.query}
    if args.text:
        payload["text"] = True
    schema = read_json_arg(args.output_schema, args.output_schema_file)
    if schema:
        payload["outputSchema"] = schema
    extra = read_json_arg(args.extra_json, args.extra_json_file)
    if extra:
        deep_merge(payload, extra)

    if args.stream:
        payload["stream"] = True
        return stream_post(cfg, api_key, "/answer", payload, args.timeout)

    ok, data, elapsed = post(cfg, api_key, "/answer", payload, timeout=args.timeout)
    if not ok:
        data["elapsed_seconds"] = elapsed
        return data
    if args.raw:
        return data
    return {
        "answer": data.get("answer"),
        "citations": [
            {"url": c.get("url"), "title": c.get("title"),
             "publishedDate": c.get("publishedDate")}
            for c in data.get("citations", [])
        ],
        "cost": data.get("costDollars", {}),
        "elapsed_seconds": elapsed,
    }


def stream_post(cfg, api_key, path, payload, timeout, extra_headers=None):
    """Minimal SSE consumer — prints data chunks to stdout as they arrive.
    Works for any streaming endpoint (/answer, /search with stream=true)."""
    url = cfg["base_url"].rstrip("/") + path
    headers = {"Content-Type": "application/json", "x-api-key": api_key}
    if extra_headers:
        headers.update(extra_headers)
    try:
        with requests.post(url, json=payload, headers=headers,
                           timeout=timeout or cfg["timeout"], stream=True) as resp:
            if resp.status_code not in (200, 201):
                return {"error": True, "status_code": resp.status_code,
                        "message": resp.text[:500]}
            for line in resp.iter_lines(decode_unicode=True):
                if line and line.startswith("data:"):
                    print(line[5:].strip())
    except requests.exceptions.RequestException as e:
        return {"error": True, "message": str(e)}
    return {"streamed": True}


# --------------------------------------------------------------------------- #
# Subcommand: research  (POST /research/v1 — Exa's current Research API)
# --------------------------------------------------------------------------- #
def normalize_research(data, raw=False):
    if raw:
        return data
    output = data.get("output") or {}
    return {
        "researchId": data.get("researchId"),
        "status": data.get("status"),
        "model": data.get("model"),
        "output": {
            # parsed = structured object when an outputSchema was given;
            # content = the raw string / markdown report otherwise.
            "parsed": output.get("parsed"),
            "content": output.get("content"),
        },
        "citations": data.get("citations", []),
        "cost": data.get("costDollars", {}),
    }


def cmd_research(args, cfg, api_key):
    # Poll / fetch an existing run.
    if args.get:
        ok, data = get(cfg, api_key, f"/research/v1/{args.get}")
        return data if not ok else normalize_research(data, raw=args.raw)

    instructions = args.instructions or args.query
    if not instructions:
        return {"error": True,
                "message": "--instructions (or --query) is required (or --get <researchId>)"}

    payload = {"instructions": instructions, "model": args.model or cfg["research_model"]}
    schema = read_json_arg(args.output_schema, args.output_schema_file)
    if schema:
        payload["outputSchema"] = schema
    extra = read_json_arg(args.extra_json, args.extra_json_file)
    if extra:
        deep_merge(payload, extra)

    ok, data, elapsed = post(cfg, api_key, "/research/v1", payload, timeout=args.timeout)
    if not ok:
        data["elapsed_seconds"] = elapsed
        return data

    rid = data.get("researchId")
    if args.no_wait:
        return {"researchId": rid, "status": data.get("status"),
                "note": "launched; poll with --get <researchId>"}

    # Poll to completion.
    deadline = time.time() + args.max_wait
    status = data.get("status")
    while status not in TERMINAL and time.time() < deadline:
        time.sleep(args.poll_interval)
        ok, data = get(cfg, api_key, f"/research/v1/{rid}")
        if not ok:
            return data
        status = data.get("status")
        print(f"  {rid}: {status}", file=sys.stderr)
    return normalize_research(data, raw=args.raw)


# --------------------------------------------------------------------------- #
# Subcommand: agent  (POST /agent/runs — BETA Agent API)
# --------------------------------------------------------------------------- #
def cmd_agent(args, cfg, api_key):
    beta = {"Exa-Beta": args.beta_token or cfg["beta_token"]}

    if args.list:
        ok, data = get(cfg, api_key, "/agent/runs", extra_headers=beta)
        return data
    if args.cancel:
        ok, data, _ = post(cfg, api_key, f"/agent/runs/{args.cancel}/cancel", {},
                           extra_headers=beta, timeout=args.timeout)
        return data
    if args.get:
        ok, data = get(cfg, api_key, f"/agent/runs/{args.get}", extra_headers=beta)
        return data

    if not args.query:
        return {"error": True,
                "message": "--query is required (or --get/--cancel <run_id>, or --list)"}

    payload = {"query": args.query, "effort": args.effort}
    schema = read_json_arg(args.output_schema, args.output_schema_file)
    if schema:
        payload["outputSchema"] = schema
    extra = read_json_arg(args.extra_json, args.extra_json_file)
    if extra:
        deep_merge(payload, extra)

    ok, data, elapsed = post(cfg, api_key, "/agent/runs", payload,
                             extra_headers=beta, timeout=args.timeout)
    if not ok:
        data["elapsed_seconds"] = elapsed
        return data

    run_id = data.get("id")
    if args.no_wait:
        return {"id": run_id, "status": data.get("status"), "note": "launched; poll with --get"}

    deadline = time.time() + args.max_wait
    status = data.get("status")
    while status not in TERMINAL and time.time() < deadline:
        time.sleep(args.poll_interval)
        ok, data = get(cfg, api_key, f"/agent/runs/{run_id}", extra_headers=beta)
        if not ok:
            return data
        status = data.get("status")
        print(f"  {run_id}: {status}", file=sys.stderr)

    if args.raw:
        return data
    return {
        "id": run_id,
        "status": status,
        "output": data.get("output"),
        "cost": data.get("costDollars", {}),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def common_parent():
    """Flags shared by every subcommand (work after the subcommand name)."""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--out", help="write JSON output to this file instead of stdout")
    p.add_argument("--pretty", action="store_true", help="pretty-print JSON")
    p.add_argument("--raw", action="store_true", help="return Exa's raw response unmodified")
    p.add_argument("--timeout", type=int, help="per-request timeout seconds")
    # Escape hatch: arbitrary JSON deep-merged into the request body LAST. Sets or
    # overrides ANY parameter (present or future) — guarantees full API parity.
    p.add_argument("--extra-json", help="raw JSON merged into the request body (overrides)")
    p.add_argument("--extra-json-file", help="file with JSON merged into the request body")
    return p


def add_content_flags(p):
    """Content-extraction flags shared by `search` (nested) and `contents` (top-level)."""
    p.add_argument("--contents-json",
                   help="raw content block as JSON (overrides the content flags below)")
    p.add_argument("--text", action="store_true")
    p.add_argument("--highlights", action="store_true")
    p.add_argument("--highlights-query")
    p.add_argument("--summary", action="store_true")
    p.add_argument("--summary-query")
    p.add_argument("--max-characters", type=int)
    p.add_argument("--max-age-hours", type=int,
                   help="cache freshness: -1..720; 0 = fetch fresh (replaces --livecrawl)")
    p.add_argument("--livecrawl", choices=["never", "fallback", "always", "preferred"],
                   help="DEPRECATED by Exa — prefer --max-age-hours")
    p.add_argument("--subpages", type=int, help="0-100 subpages to crawl per result")


def add_search_parser(sub, common):
    p = sub.add_parser("search", parents=[common],
                       help="POST /search — discover pages for a query (single or batch)")
    p.add_argument("--query")
    # No `choices` on purpose — any current/legacy/future type works. Default from config.
    p.add_argument("--type", default=None,
                   help="search type; documented: " + ", ".join(SEARCH_TYPES[:6])
                        + " (legacy neural/keyword still work)")
    p.add_argument("--num-results", type=int, default=10)
    p.add_argument("--category",
                   help="company, people, research paper, news, financial report, personal site")
    # Agentic / structured output
    p.add_argument("--system-prompt")
    p.add_argument("--system-prompt-file")
    p.add_argument("--output-schema", help="inline JSON schema string")
    p.add_argument("--output-schema-file")
    p.add_argument("--additional-queries", help="comma-separated, max 10 (deep* types only)")
    # Content extraction (per result). Full control via --contents-json.
    add_content_flags(p)
    # Filters
    p.add_argument("--include-domains")
    p.add_argument("--exclude-domains")
    p.add_argument("--include-text", help="phrase a result MUST contain")
    p.add_argument("--exclude-text", help="phrase a result must NOT contain")
    p.add_argument("--start-published-date")
    p.add_argument("--end-published-date")
    p.add_argument("--start-crawl-date")
    p.add_argument("--end-crawl-date")
    p.add_argument("--user-location", help="two-letter ISO country code")
    p.add_argument("--compliance", choices=["hipaa"], help="compliance mode (enterprise-only)")
    p.add_argument("--moderation", action="store_true")
    p.add_argument("--stream", action="store_true", help="stream results as SSE")
    # Batch (parallel multi-call)
    p.add_argument("--batch", help="JSON file: array of call specs (parallel, rate-limited)")
    p.add_argument("--rate-limit", type=int, help="max parallel calls per batch (default 5)")


def add_contents_parser(sub, common):
    p = sub.add_parser("contents", parents=[common],
                       help="POST /contents — extract contents for URLs you already have")
    p.add_argument("--urls", help="comma-separated URLs to crawl/extract (1-100)")
    p.add_argument("--ids", help="comma-separated Exa result ids (alternative to --urls)")
    p.add_argument("--compliance", choices=["hipaa"], help="compliance mode (enterprise-only)")
    add_content_flags(p)


def add_answer_parser(sub, common):
    p = sub.add_parser("answer", parents=[common],
                       help="POST /answer — one cited answer (sync RAG, no knobs)")
    p.add_argument("--query")
    p.add_argument("--text", action="store_true", help="include full page text of citations")
    p.add_argument("--output-schema")
    p.add_argument("--output-schema-file")
    p.add_argument("--stream", action="store_true")


def add_research_parser(sub, common):
    p = sub.add_parser("research", parents=[common],
                       help="POST /research/v1 — async Research API (instructions + model)")
    p.add_argument("--instructions", help="natural-language research instructions")
    p.add_argument("--query", help="alias for --instructions")
    p.add_argument("--model", default=None, choices=RESEARCH_MODELS,
                   help="exa-research-fast | exa-research (default) | exa-research-pro")
    p.add_argument("--output-schema", help="JSON schema -> output.parsed")
    p.add_argument("--output-schema-file")
    p.add_argument("--no-wait", action="store_true", help="launch only; do not poll")
    p.add_argument("--get", metavar="RESEARCH_ID", help="poll/fetch an existing research run")
    p.add_argument("--poll-interval", type=int, default=5)
    p.add_argument("--max-wait", type=int, default=600, help="seconds to poll before giving up")


def add_agent_parser(sub, common):
    p = sub.add_parser("agent", parents=[common],
                       help="POST /agent/runs — BETA Agent API (enrichment, multi-step)")
    p.add_argument("--query")
    p.add_argument("--effort", default="medium", choices=EFFORT_LEVELS)
    p.add_argument("--output-schema")
    p.add_argument("--output-schema-file")
    p.add_argument("--no-wait", action="store_true", help="launch only; do not poll")
    p.add_argument("--get", metavar="RUN_ID", help="poll an existing run")
    p.add_argument("--cancel", metavar="RUN_ID", help="cancel a queued/running run")
    p.add_argument("--list", action="store_true", help="list your team's runs")
    p.add_argument("--poll-interval", type=int, default=5)
    p.add_argument("--max-wait", type=int, default=600, help="seconds to poll before giving up")
    p.add_argument("--beta-token", help="Exa-Beta header token (default from config)")


def main():
    parser = argparse.ArgumentParser(
        prog="exa.py",
        description="One entrypoint for Exa: search | contents | answer | research | agent")
    sub = parser.add_subparsers(dest="command", required=True)
    common = common_parent()
    add_search_parser(sub, common)
    add_contents_parser(sub, common)
    add_answer_parser(sub, common)
    add_research_parser(sub, common)
    add_agent_parser(sub, common)
    args = parser.parse_args()

    # Windows consoles default to cp1252; Exa returns UTF-8 (smart quotes, marks).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    cfg = load_config()
    api_key = get_api_key()
    if not api_key:
        print(json.dumps({"error": True, "message":
              "No Exa API key. Set EXA_API_KEY env var or configure mcpServers.exa in ~/.claude.json"}),
              file=sys.stderr)
        sys.exit(1)

    dispatch = {"search": cmd_search, "contents": cmd_contents, "answer": cmd_answer,
                "research": cmd_research, "agent": cmd_agent}
    result = dispatch[args.command](args, cfg, api_key)

    output_str = json.dumps(result, indent=2 if args.pretty else None, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output_str)
        print(f"Output written to {args.out}", file=sys.stderr)
    else:
        print(output_str)

    sys.exit(1 if (isinstance(result, dict) and result.get("error")) else 0)


if __name__ == "__main__":
    main()
