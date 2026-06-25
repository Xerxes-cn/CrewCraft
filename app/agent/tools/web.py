"""Web 工具：搜索和抓取。"""

import json
import re

from .registry import register


@register(
    "web_search",
    "Search the web. Returns titles, snippets, and URLs for the given query.",
    {
        "query": {"type": "string", "description": "Search query"},
        "max_results": {"type": "integer", "description": "Maximum number of results (default 5)"},
    },
    permission="read",
)
async def web_search(query: str, max_results: int = 5):
    """使用 DuckDuckGo HTML 搜索网页（无需 API 密钥）。"""
    import httpx
    from html import unescape

    url = "https://html.duckduckgo.com/html/"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, data={"q": query})
        resp.raise_for_status()

    results = []
    blocks = re.findall(
        r'<a rel="nofollow" class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        resp.text,
    )
    snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', resp.text)

    for i, (href, title) in enumerate(blocks[:max_results]):
        title_clean = unescape(re.sub(r"<[^>]+>", "", title)).strip()
        snip = snippets[i] if i < len(snippets) else ""
        snippet_clean = unescape(re.sub(r"<[^>]+>", "", snip)).strip()
        results.append({
            "title": title_clean,
            "url": unescape(href),
            "snippet": snippet_clean,
        })

    if not results:
        return f"No results found for '{query}'."

    return json.dumps(results, indent=2, ensure_ascii=False)


@register(
    "web_fetch",
    "Fetch content from a URL and return the text. Use for reading web pages, APIs, or any HTTP resource.",
    {
        "url": {"type": "string", "description": "The URL to fetch"},
        "method": {"type": "string", "description": "HTTP method: GET or POST"},
        "body": {"type": "string", "description": "Request body (for POST, JSON string)"},
    },
    permission="read",
)
async def web_fetch(url: str, method: str = "GET", body: str = ""):
    """抓取 URL 并返回其文本内容。"""
    import httpx

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        if method.upper() == "POST":
            kwargs = {"content": body} if body else {}
            resp = await client.post(url, **kwargs)
        else:
            resp = await client.get(url)
        resp.raise_for_status()
        text = resp.text[:10000]
        if len(resp.text) > 10000:
            text += f"\n... [truncated, {len(resp.text)} total chars]"
        return text
