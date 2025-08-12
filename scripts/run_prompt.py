# scripts/run_prompt.py
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

from feedgen.feed import FeedGenerator
from openai import OpenAI
import httpx

# Configure the OpenAI client:
# - 120s per request timeout (covers connect+read)
# - max_retries=0 because we implement our own single manual retry
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    timeout=120.0,
    max_retries=0,
)

def _extract_json(text: str) -> list[dict]:
    """Best-effort JSON extractor: direct parse, then fenced code block, then first array."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*($begin:math:display$.*?$end:math:display$)\s*```", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    m = re.search(r"(\[.*\])", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    raise json.JSONDecodeError("No valid JSON array found", text, 0)

def _call_responses_with_retry(system_msg: str, user_prompt: str, retry_delay: float = 1.5):
    """Call the Responses API once; on network error, retry exactly once after a brief delay."""
    print("[openai] calling Responses API with web_search…", flush=True)
    try:
        return client.responses.create(
            model="gpt-5",
            tools=[{"type": "web_search"}],
            input=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_prompt},
            ],
        )
    except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.HTTPError) as e:
        print(f"[warn] OpenAI request failed ({type(e).__name__}: {e}); retrying once…", flush=True)
        time.sleep(retry_delay)
        # Second (and final) attempt
        return client.responses.create(
            model="gpt-5",
            tools=[{"type": "web_search"}],
            input=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_prompt},
            ],
        )

def call_llm(prompt: str) -> list[dict]:
    """
    Return a list of items: [{title, url, summary, published}]
    Uses the Responses API with built-in web_search.
    """
    system_msg = (
        "You must use web search before answering. Find 12 recent news articles "
        "(last 30 days) emphasizing: how people are using AI, especially in "
        "education, blogging, US politics, science; and NBA/MLB with slight emphasis "
        "on the New York Knicks and New York Mets. De-duplicate domains and topics. "
        "Return only JSON (no prose), as an array of objects with exactly these keys: "
        'title, url, summary, published. Use canonical article URLs. '
        'Use ISO 8601 UTC "YYYY-MM-DDTHH:MM:SSZ" for published.'
    )

    try:
        resp = _call_responses_with_retry(system_msg, prompt)
    except httpx.HTTPError as e:
        print(f"[error] OpenAI request failed after retry: {type(e).__name__}: {e}", flush=True)
        sys.exit(1)

    try:
        print(f"[openai] response_id={resp.id} model={resp.model} usage={resp.usage}", flush=True)
    except Exception:
        pass

    text = resp.output_text or ""
    if not text.strip():
        print("[error] Empty response from model.", flush=True)
        sys.exit(1)

    try:
        items = _extract_json(text)
    except json.JSONDecodeError:
        print("[error] Model did not return valid JSON. Raw output follows:", flush=True)
        print(text)
        sys.exit(1)

    if not isinstance(items, list):
        print("[error] Model did not return a JSON array.", flush=True)
        sys.exit(1)

    # Minimal schema checks
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            print(f"[error] Item {i} is not an object.", flush=True)
            sys.exit(1)
        for k in ("title", "url", "summary", "published"):
            if k not in it:
                print(f"[error] Item {i} missing key: {k}", flush=True)
                sys.exit(1)

    return items

def make_rss(items: list[dict], outfile: Path):
    fg = FeedGenerator()
    fg.load_extension('podcast')  # harmless/no-op if unused
    fg.title('Late News (AI practical uses)')
    # TODO: replace with your real site + feed URLs when publishing
    fg.link(href='https://example.com/', rel='alternate')
    fg.link(href='https://example.com/feed.xml', rel='self')
    fg.description('Auto-generated feed of practical AI stories.')
    fg.language('en')
    fg.lastBuildDate(datetime.now(timezone.utc))

    for it in items:
        fe = fg.add_entry()
        fe.title(it.get("title", "(untitled)"))
        if it.get("url"):
            fe.link(href=it["url"])
        fe.description(it.get("summary", ""))
        if it.get("published"):
            fe.pubDate(it["published"])

    outfile.parent.mkdir(parents=True, exist_ok=True)
    fg.rss_file(str(outfile), pretty=True)
    print(f"[rss] wrote {outfile} with {len(items)} items", flush=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt-file", required=True, help="Path to the prompt text/markdown file")
    ap.add_argument("--out", required=True, help="Output RSS path, e.g., public/feed.xml")
    args = ap.parse_args()

    prompt_path = Path(args.prompt_file)
    if not prompt_path.is_file():
        print(f"[error] Prompt file not found: {prompt_path}", flush=True)
        sys.exit(1)

    prompt = prompt_path.read_text(encoding="utf-8")
    items = call_llm(prompt)
    make_rss(items, Path(args.out))

if __name__ == "__main__":
    main()
