import os

import requests
import yfinance as yf

NYT_API_KEY = os.getenv("NYT_API_KEY")

# ── Tool 1: NYT news ──────────────────────────────────────────


def nyt_search(ticker: str, company_name: str) -> dict:
    """Find recent articles about a company"""
    url = "https://api.nytimes.com/svc/search/v2/articlesearch.json"
    params = {
        "q": company_name,
        "api-key": NYT_API_KEY,
        "sort": "newest",
        "fq": 'section_name:("Business" "Technology" "DealBook")',
        "fl": "headline,snippet,pub_date,web_url",
        "page": 0,
    }
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()

    docs = response.json()["response"]["docs"][:5]
    articles = [
        {
            "headline": d["headline"]["main"],
            "snippet": d["snippet"],
            "date": d["pub_date"][:10],
            "url": d["web_url"],
        }
        for d in docs
    ]
    return {"ticker": ticker, "articles": articles, "count": len(articles)}


# ── Tool 2: Yahoo Finance ─────────────────────────────────────


def get_stock_data(ticker: str) -> dict:
    """Retrieves price, metrics and recent tendency of a stock."""
    stock = yf.Ticker(ticker)
    info = stock.info

    # History of past 30 days
    hist = stock.history(period="1mo")
    price_start = float(hist["Close"].iloc[0])
    price_now = float(hist["Close"].iloc[-1])
    change_1mo = round((price_now - price_start) / price_start * 100, 2)

    return {
        "ticker": ticker,
        "price": round(price_now, 2),
        "change_1mo_pct": change_1mo,
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "analyst_target": info.get("targetMeanPrice"),
        "recommendation": info.get("recommendationKey"),  # buy/hold/sell
        "sector": info.get("sector"),
        "summary": info.get("longBusinessSummary", "")[:300],
    }


# ── Tool 3: Sentiment scorer ──────────────────────────────────


def analyze_sentiment(articles: list[dict]) -> dict:
    """Puntúa el sentimiento de una lista de titulares (sin LLM)."""
    POSITIVE = [
        "surge",
        "beat",
        "record",
        "growth",
        "profit",
        "strong",
        "rally",
        "gain",
        "upgrade",
        "bullish",
        "expands",
        "wins",
    ]
    NEGATIVE = [
        "fall",
        "miss",
        "loss",
        "cut",
        "decline",
        "warning",
        "lawsuit",
        "layoff",
        "bearish",
        "crash",
        "fraud",
        "risk",
    ]

    scores = []
    for a in articles:
        text = (a["headline"] + " " + a.get("snippet", "")).lower()
        pos = sum(1 for w in POSITIVE if w in text)
        neg = sum(1 for w in NEGATIVE if w in text)
        scores.append(pos - neg)

    total = sum(scores)
    label = "positive" if total > 1 else "negative" if total < -1 else "neutral"

    return {
        "sentiment": label,
        "score": total,
        "article_scores": scores,
    }
