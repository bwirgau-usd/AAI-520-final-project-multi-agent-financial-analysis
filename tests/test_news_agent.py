from unittest.mock import patch

from src.agents.news_agent import run_news_agent

ARTICLE = {
    "title": "Company beats earnings expectations",
    "publisher": "Example News",
    "date": "2026-09-20T12:00:00Z",
    "url": "https://example.com/article-1",
    "text": "Full article text here.",
}


def test_run_news_agent_preserves_sources():
    with patch("src.agents.news_agent.get_company_news", return_value=[ARTICLE]):
        result = run_news_agent("AAPL")

    assert result["symbol"] == "AAPL"
    assert result["article_count"] == 1
    assert result["sources"][0]["url"] == ARTICLE["url"]
    assert "summary" in result


def test_run_news_agent_handles_no_articles():
    with patch("src.agents.news_agent.get_company_news", return_value=[]):
        result = run_news_agent("AAPL")

    assert result["article_count"] == 0
    assert result["sources"] == []
