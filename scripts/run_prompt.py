# scripts/run_prompt.py
import argparse, os, time, json
from pathlib import Path
from feedgen.feed import FeedGenerator
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def call_llm(prompt: str) -> list[dict]:
    """
    Return a list of items: [{title, url, summary, published}]
    We switch to the Responses API and enable the built-in web search tool.
    """
    resp = client.responses.create(
        model="gpt-5",  # model that supports tools in Responses API
        tools=[{"type": "web_search"}],   # <-- this enables web browsing
        temperature=0.2,
        input=[
            {
                "role": "system",
                "content": (
                    'You must use web search to find recent, real articles before answering. '
                    'Return JSON only in this exact array shape: '
                    '[{"title":"...","url":"...","summary":"...","published":"YYYY-MM-DDTHH:MM:SSZ"}]. '
                    'No placeholders or example.com. Use canonical article URLs.'
                )
            },
            {"role": "user", "content": prompt}
        ],
        # Optional: require valid JSON (object is recommended, but arrays work in practice)
        # response_format={"type": "json_object"}
    )

    # output_text concatenates all text segments from the model/tool run
    text = resp.output_text
    return json.loads(text)

def make_rss(items: list[dict], outfile: Path):
    fg = FeedGenerator()
    fg.load_extension('podcast')
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
