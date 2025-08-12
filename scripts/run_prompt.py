# scripts/run_prompt.py
import argparse, os, time
from pathlib import Path
from feedgen.feed import FeedGenerator

# OpenAI SDK v1.x
from openai import OpenAI
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def call_llm(prompt: str) -> list[dict]:
    """
    Return a list of items: [{title, url, summary, published}]
    Your prompt should ask for JSON. We use JSON mode to be strict.
    """
    resp = client.chat.completions.create(
        model="gpt-4o-mini",  # or your preferred model
        messages=[
            {"role": "system", "content": "Return JSON only: [{\"title\":\"...\",\"url\":\"...\",\"summary\":\"...\",\"published\":\"YYYY-MM-DDTHH:MM:SSZ\"}]"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    import json
    text = resp.choices[0].message.content
    return json.loads(text)

def make_rss(items: list[dict], outfile: Path):
    fg = FeedGenerator()
    fg.load_extension('podcast')  # harmless/no-op if unused
    fg.title('Late News (AI practical uses)')
    fg.link(href='https://example.com/', rel='alternate')
    fg.link(href='https://example.com/feed.xml', rel='self')
    fg.description('Auto-generated feed of practical AI stories.')
    fg.language('en')

    for it in items:
        fe = fg.add_entry()
        fe.title(it.get("title","(untitled)"))
        if it.get("url"): fe.link(href=it["url"])
        fe.description(it.get("summary",""))
        if it.get("published"): fe.pubDate(it["published"])

    outfile.parent.mkdir(parents=True, exist_ok=True)
    fg.rss_file(str(outfile), pretty=True)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    items = call_llm(prompt)
    make_rss(items, Path(args.out))
    print(f"Wrote {args.out}")
