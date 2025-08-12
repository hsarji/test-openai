# scripts/run_prompt.py
import argparse
import json
import os
import re
from pathlib import Path
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def _extract_json(text: str) -> list[dict]:
    """Best-effort JSON extractor: try direct parse, then fenced code blocks."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try to find a fenced JSON/code block
    m = re.search(r"```(?:json)?\s*($begin:math:display$.*?$end:math:display$)\s*```", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    # Try to find first [ ... ] block
    m = re.search(r"(\[.*\])", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    raise json.JSONDecodeError("No valid JSON array found", text, 0)

def call_llm(prompt: str) -> list[dict]:
    """
    Return a list of items: [{title, url, summary, published}]
    Uses the Responses API with the built-in web_search tool.
    """
    system_msg = (
        "You must use web search before answering. Find 20 recent news articles "
        "(last 30 days) emphasizing: how people are using AI, especially in "
        "education, blogging, US politics, science; and NBA/MLB with slight emphasis "
        "on the New York Knicks and New York Mets. De-duplicate domains and topics. "
        "Return only JSON (no prose), as an array of objects with exactly these keys: "
        'title, url, summary, published. Use canonical article URLs. '
        'Use ISO 8601 UTC "YYYY-MM-DDTHH:MM:SSZ" for published.'
    )

    print("[openai] calling Responses API with web_search…")
    resp = client.responses.create(
        model="gpt-5",                      # model that supports web_search
        tools=[{"type": "web_search"}],     # browsing enabled
        input=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt}
        ],
        # NOTE: no response_format and no temperature to maximize compatibility
    )

    # Helpful confirmation in CI logs
    try:
        print(f"[openai] response_id={resp.id} model={resp.model} usage={resp.usage}")
    except Exception:
        pass

    text = resp.output_text
    try:
        items = _extract_json(text)
    except json.JSONDecodeError:
        print("[error] Model did not return valid JSON. Raw output follows:")
        print(text)
        raise

    if not isinstance(items, list):
        raise ValueError("Model did not return a JSON array.")
    # Minimal field check
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            raise ValueError(f"Item {i} is not an object.")
        for k in ("title", "url", "summary", "published"):
            if k not in it:
                raise ValueError(f"Item {i} missing key: {k}")
    return items

def make_rss(items: list[dict], outfile: Path):
    fg = FeedGenerator()
    fg.load_extension('podcast')  # harmless/no-op if unused
    fg.title('Late News (AI practical uses)')
    # Replace these with your real site + feed URLs when publishing:
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
    print(f"[rss] wrote {outfile} with {len(items)} items")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt-file", required=True, help="Path to the prompt text/markdown file")
    ap.add_argument("--out", required=True, help="Output RSS path, e.g., public/feed.xml")
    args = ap.parse_args()

    prompt_path = Path(args.prompt_file)
    if not prompt_path.is_file():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    prompt = prompt_path.read_text(encoding="utf-8")
    items = call_llm(prompt)
    make_rss(items, Path(args.out))

if __name__ == "__main__":
    main()
