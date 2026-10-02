
from src.workflows.news_pipeline import ingest, preprocess, run_news_pipeline

ARTICLE = {
    "title": "Company announces new product line",
    "publisher": "Example News",
    "date": "2026-09-20T12:00:00Z",
    "url": "https://example.com/article-1",
    "text": "<p>The company unveiled  a new product today.</p>",
}


def test_ingest_caps_article_count():
    articles = [{"title": f"Article {i}"} for i in range(20)]
    assert len(ingest(articles, max_articles=5)) == 5


def test_preprocess_cleans_html_and_whitespace():
    cleaned = preprocess([ARTICLE])
    assert "<p>" not in cleaned[0]["text"]
    assert "  " not in cleaned[0]["text"]


def test_preprocess_drops_duplicate_titles():
    duplicate = {**ARTICLE, "url": "https://example.com/article-2"}
    cleaned = preprocess([ARTICLE, duplicate])
    assert len(cleaned) == 1


def test_preprocess_drops_articles_with_empty_text():
    empty = {**ARTICLE, "text": "", "title": "Untitled"}
    cleaned = preprocess([empty])
    assert cleaned == []


def test_run_news_pipeline_falls_back_gracefully_without_llm(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = run_news_pipeline("AAPL", [ARTICLE])

    assert result["classified"][0]["category"] == "OTHER"
    assert result["extracted"][0]["sentiment"] == "neutral"
    assert isinstance(result["summary"], str)


def test_run_news_pipeline_handles_no_articles():
    result = run_news_pipeline("AAPL", [])
    assert result["summary"] == "No recent news articles were available for AAPL."
