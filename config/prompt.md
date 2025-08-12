Search the public web for recent news articles from the last 30 days.  
Focus on stories that show how people are using AI, with emphasis on:
- Education
- Blogging and content creation
- US politics
- Science news
- NBA and MLB, with a slight emphasis on the New York Knicks and New York Mets

Instructions:
1. Use web search to find the 20 most relevant, high-quality stories from authoritative sources (major news outlets, government, universities, reputable industry publications).  
2. Remove duplicate topics and avoid more than one story from the same source domain unless highly distinct.  
3. Prefer the most recent version of an article if multiple outlets cover the same story.  
4. Return only JSON in this exact format (no other text):
[
  {
    "title": "...",
    "url": "https://canonical-article-url.com",
    "summary": "One or two factual sentences summarizing the story.",
    "published": "YYYY-MM-DDTHH:MM:SSZ"
  }
]
5. Dates must be the original article's publication date in UTC ISO 8601 (Z) format.  
6. No example.com or placeholders — all URLs must be real, working links to the source content.
