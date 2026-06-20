import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import feedparser

from tools.gemini_client import generate

SOURCES = {
    "厚労省": "https://www.mhlw.go.jp/rss/iryou.rdf",
    "中医協": "https://www.mhlw.go.jp/rss/chuo.rdf",
}

PRIORITY_KEYWORDS = [
    "診療報酬", "DPC", "医療法", "地域医療構想",
    "介護報酬", "医師働き方", "医療DX", "病床機能", "施設基準",
]

IMPACT_ORDER = {"高": 0, "中": 1, "低": 2}

_FALLBACK_SUMMARY = {
    "impact_level": "低",
    "impact_reason": "自動分析に失敗しました。",
    "summary": "要約を取得できませんでした。",
    "client_point": "詳細はURLを確認してください。",
}


def load_seen_urls(path: str = "data/seen_urls.json") -> set:
    p = Path(path)
    if p.exists():
        return set(json.loads(p.read_text(encoding="utf-8")))
    return set()


def save_seen_urls(urls: set, path: str = "data/seen_urls.json") -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sorted(urls), ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_rss(url: str, source_label: str) -> list:
    try:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            print(f"[{source_label}] RSSフィード取得失敗: {url}")
            return []
        results = []
        for entry in feed.entries:
            link = entry.get("link") or entry.get("id", "")
            title = entry.get("title", "").strip()
            if not link or not title:
                continue
            pub_date = getattr(entry, "published", None) or getattr(entry, "updated", "")
            results.append({
                "url": link,
                "title": title,
                "pub_date": pub_date,
                "source": source_label,
            })
        return results
    except Exception as e:
        print(f"[{source_label}] 取得エラー: {e}")
        return []


def check_keywords(title: str) -> tuple:
    matched = [kw for kw in PRIORITY_KEYWORDS if kw in title]
    return bool(matched), matched


def _build_summarize_prompt(title: str, url: str, source: str, is_priority: bool) -> str:
    priority_hint = "※このトピックは病院経営に直結するキーワードを含んでいます。\n" if is_priority else ""
    return f"""あなたは日本の医療政策・病院経営の専門コンサルタントです。
以下の厚生労働省・中医協の行政情報を病院経営者向けに分析してください。
{priority_hint}
【情報源】{source}
【タイトル】{title}
【URL】{url}

以下のJSON形式のみで回答してください：
{{
  "impact_level": "高|中|低のいずれか",
  "impact_reason": "病院経営への影響理由を1文で（日本語）",
  "summary": "内容の要約を2〜3文で（日本語）",
  "client_point": "非専門家の病院管理者向けに1行で伝えるポイント（日本語）"
}}

判断基準：
- 高：診療報酬・施設基準・医療法改正など収益・運営に直接影響するもの
- 中：通知・指導・研究会報告など近い将来に影響する可能性があるもの
- 低：統計・調査・その他参考情報"""


def summarize_article(title: str, url: str, source: str, is_priority: bool) -> dict:
    prompt = _build_summarize_prompt(title, url, source, is_priority)
    try:
        raw = generate(prompt, json_mode=True)
        result = json.loads(raw)
        for k in ("impact_level", "impact_reason", "summary", "client_point"):
            if k not in result:
                raise ValueError(f"missing key: {k}")
        if result["impact_level"] not in ("高", "中", "低"):
            result["impact_level"] = "低"
        return result
    except Exception as e:
        print(f"Gemini要約失敗 ({title[:30]}): {e}")
        return _FALLBACK_SUMMARY.copy()


def process_new_articles(seen: set) -> tuple:
    all_fetched = []
    for source_label, url in SOURCES.items():
        entries = fetch_rss(url, source_label)
        all_fetched.extend(entries)
        print(f"[{source_label}] {len(entries)}件取得")

    new_articles = [a for a in all_fetched if a["url"] not in seen]
    print(f"新着: {len(new_articles)}件 / 取得: {len(all_fetched)}件")

    enriched = []
    for article in new_articles:
        is_priority, matched_kws = check_keywords(article["title"])
        summary = summarize_article(article["title"], article["url"], article["source"], is_priority)
        enriched.append({
            **article,
            "priority": is_priority,
            "matched_keywords": matched_kws,
            **summary,
        })

    enriched.sort(
        key=lambda a: (
            IMPACT_ORDER.get(a.get("impact_level", "低"), 2),
            not a.get("priority", False),
        )
    )

    updated_seen = seen | {a["url"] for a in all_fetched}
    return enriched, updated_seen


def append_to_history(articles: list, run_date: str, path: str = "data/alerts_history.json") -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    history = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []

    JST = timezone(timedelta(hours=9))
    by_source: dict = {}
    by_impact: dict = {}
    for a in articles:
        by_source[a["source"]] = by_source.get(a["source"], 0) + 1
        by_impact[a["impact_level"]] = by_impact.get(a["impact_level"], 0) + 1

    history.append({
        "run_date": run_date,
        "run_ts": datetime.now(JST).isoformat(),
        "articles": articles,
        "summary_stats": {
            "total": len(articles),
            "priority_count": sum(1 for a in articles if a.get("priority")),
            "by_source": by_source,
            "by_impact": by_impact,
        },
    })
    p.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_subject(articles: list, run_date: str) -> str:
    priority_count = sum(1 for a in articles if a.get("priority"))
    normal_count = len(articles) - priority_count
    date_str = run_date.replace("-", "/")
    if priority_count > 0:
        return f"【厚労省/中医協】⚠️重要{priority_count}件 + 通常{normal_count}件 ({date_str})"
    return f"【厚労省/中医協】新着{len(articles)}件 ({date_str})"


_IMPACT_COLORS = {
    "高": ("#D32F2F", "white"),
    "中": ("#F57C00", "white"),
    "低": ("#757575", "white"),
}


def _article_card_html(a: dict) -> str:
    impact = a.get("impact_level", "低")
    bg, fg = _IMPACT_COLORS.get(impact, ("#757575", "white"))
    badge = (
        f'<span style="background:{bg};color:{fg};padding:2px 8px;'
        f'border-radius:4px;font-size:12px;font-weight:bold;">{impact}</span>'
    )
    priority_marker = " ⚠️" if a.get("priority") else ""
    keyword_tags = "".join(
        f'<span style="background:#E3F2FD;color:#1565C0;padding:1px 6px;'
        f'border-radius:3px;font-size:11px;margin-right:4px;">{kw}</span>'
        for kw in a.get("matched_keywords", [])
    )
    title_escaped = a["title"].replace("<", "&lt;").replace(">", "&gt;")
    return f"""
<div style="border:1px solid #e0e0e0;border-radius:8px;padding:16px;
            margin-bottom:16px;border-left:4px solid {bg};">
  <div style="margin-bottom:8px;">
    {badge}
    <span style="font-size:11px;color:#666;margin-left:8px;">{a.get("source","")}</span>
    {priority_marker}
  </div>
  <h3 style="margin:4px 0;font-size:15px;">
    <a href="{a["url"]}" style="color:#1a237e;text-decoration:none;">{title_escaped}</a>
  </h3>
  <div style="margin:4px 0;">{keyword_tags}</div>
  <p style="margin:8px 0 4px;color:#555;font-size:13px;line-height:1.6;">{a.get("summary","")}</p>
  <p style="margin:4px 0;background:#FFF8E1;padding:8px 10px;
            border-radius:4px;font-size:13px;color:#333;">
    <strong>経営者へのポイント：</strong>{a.get("client_point","")}
  </p>
  <p style="margin:6px 0 0;font-size:12px;color:#777;">{a.get("impact_reason","")}</p>
</div>
"""


def build_email_html(articles: list, run_date: str) -> tuple:
    priority_section = [a for a in articles if a.get("priority")]
    normal_section = [a for a in articles if not a.get("priority")]

    cards_html = ""
    if priority_section:
        cards_html += (
            '<h2 style="color:#D32F2F;border-bottom:2px solid #D32F2F;'
            'padding-bottom:6px;margin-top:8px;">⚠️ 優先確認事項</h2>'
        )
        cards_html += "".join(_article_card_html(a) for a in priority_section)
    if normal_section:
        header_margin = "margin-top:24px;" if priority_section else "margin-top:8px;"
        cards_html += (
            f'<h2 style="color:#333;border-bottom:1px solid #ccc;'
            f'padding-bottom:6px;{header_margin}">通常通知</h2>'
        )
        cards_html += "".join(_article_card_html(a) for a in normal_section)

    total = len(articles)
    priority_count = len(priority_section)
    priority_badge = f"　⚠️重要{priority_count}件" if priority_count else ""

    html_body = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="font-family:'Helvetica Neue',Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;">
  <div style="max-width:680px;margin:0 auto;background:#fff;border-radius:8px;
              overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
    <div style="background:#1a237e;color:white;padding:20px 24px;">
      <h1 style="margin:0;font-size:20px;">🏥 厚労省・中医協 医療アラート</h1>
      <p style="margin:6px 0 0;font-size:13px;opacity:.85;">
        {run_date} 配信　|　計{total}件{priority_badge}
      </p>
    </div>
    <div style="padding:16px 24px 24px;">
      {cards_html}
    </div>
    <div style="background:#f0f0f0;padding:12px 24px;font-size:11px;color:#999;text-align:center;">
      本メールは自動生成されています。情報の正確性は各URLからご確認ください。
    </div>
  </div>
</body>
</html>"""

    subject = _build_subject(articles, run_date)
    return subject, html_body
