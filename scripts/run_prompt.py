def call_llm(prompt: str) -> list[dict]:
    """
    Return a list of items: [{title, url, summary, published}]
    Uses the Responses API with the built-in web_search tool.
    """
    from openai import OpenAI
    import json, datetime

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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
        # NOTE: no temperature parameter here
    )

    text = resp.output_text  # concatenates all text outputs
    items = json.loads(text)

    # Light sanity check so your RSS step doesn’t blow up later
    if not isinstance(items, list):
        raise ValueError("Model did not return a JSON array.")
    return items
