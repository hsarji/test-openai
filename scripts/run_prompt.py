# scripts/run_prompt.py
import argparse
import json
import os
from pathlib import Path
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
from openai import OpenAI


client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


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
        "Return only JSON, no prose. Use canonical article URLs. "
        'Each item must be: {"title","url","summary","published"} with '
        'published as ISO 8601 UTC "YYYY-MM-DDTHH:MM:SSZ".'
    )

    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["title", "url", "summary", "published"],
            "properties": {
                "title": {"type": "string"},
                "url": {"type": "string", "format": "uri"},
                "summary": {"type": "string"},
                "published": {
                    "type": "string",
                    "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
                }
            },
            "additionalProperties": False
        },
        "minItems": 5,
        "maxItems": 25
    }

    # Visible log lines in GitHub Actions
    print("[openai] calling Responses API with web_search…")
    resp = client.responses.create(
        model="gpt-5",                      # model that supports web_search
        tools=[{"type": "web_search"}],     # <-- browsing enabled
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "NewsItems", "schema": schema, "strict": True}
        },
        input=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt}
        ],
        # NOTE: do not pass temperature if the model doesn't support it
    )

    # Helpful confirmation in CI logs
    try:
        print(f"[openai] response_id={resp.id} model={resp.model} usage={resp.usage}")
    except Exception:
        pass

    # If you want to see full tool traces in CI, uncomment this:
    # print(resp.model_dump_json(indent=2))

    text = resp.output_text  # concatenates all text outputs from the run
    try:
        items = json.loads(text)
    except json.JSONDecodeError as e:
        print("[error] Model did not return valid JSON. Raw output follows:")
        print(text)
        raise

    if not isinstance(items, list):
        raise ValueError("Model did not return a JSON array.")
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
