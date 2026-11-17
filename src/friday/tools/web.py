from src.friday.tools.shared import ToolResponse
from src import config

WEB_SEARCH_PROVIDER = config.get("misc", "web_search_provider").lower()

if WEB_SEARCH_PROVIDER == "none":
    __all__ = []
else:
    __all__ = ["web_search", "web_fetch"]

if WEB_SEARCH_PROVIDER == "ollama":
    import ollama

    if not os.getenv("OLLAMA_API_KEY"):
        raise AssertionError("OLLAMA_API_KEY should be set in order to use ollama web search")

    def web_search(query: str, max_results: int = 2):
        return ToolResponse(ollama.web_search(query, max_results))

    def web_fetch(url: str):
        """
        Args:
            url: url of the web page
        """
        return ToolResponse(ollama.web_fetch(url))

elif WEB_SEARCH_PROVIDER == "searxng":
    import requests, trafilatura

    def web_search(query: str, max_results: int = 2) -> dict:
        max_results = max(1, min(max_results, 8))

        response = requests.get(
            config.get("misc", "searxng_url"),
            params={"q": query, "format": "json"},
            timeout=15,
        )

        response.raise_for_status()

        results = response.json().get("results", [])[:max_results]
        found = [
            {
                "title": item.get("title", ""),
                "body": item.get("content", "")[:700],
                "url": item.get("url", ""),
            }
            for item in results
        ]

        return ToolResponse(found)

    def web_fetch(url: str):
        """
        Args:
            url: url of the web page
        """

        response = requests.get(url, timeout=15)
        response.raise_for_status()

        text = trafilatura.extract(
            response.text,
            url=url,
            include_comments=False,
            include_tables=True,
        )

        return ToolResponse(text or "")

else:
    from ddgs import DDGS

    def web_search(query: str, max_results: int = 10):
        try: 
            return ToolResponse(DDGS().text(query, max_results=max_results))
        except Exception as e:
            return str(e)

    def web_fetch(url: str):
        """
        Args:
            url: url of the web page
        """
        return ToolResponse(DDGS().extract(url, fmt="text_rich"))
