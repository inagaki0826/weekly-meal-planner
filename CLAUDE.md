# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## セットアップ・起動

```bash
pip install -r requirements.txt
cp .env.example .env   # GEMINI_API_KEY を設定
streamlit run app.py
```

## アーキテクチャ

週間夕飯プランナーアプリ。Streamlit + Gemini APIで構築。

```
app.py                  ← UI全体（タブ切り替え）
tools/
  gemini_client.py      ← Gemini API の窓口（JSONモード対応）
  meal_planner.py       ← レシピ生成・買い物リスト生成ロジック
```

## 主な機能

- 平日5日分の夕飯レシピ生成（2人前・フライパンまたは鍋1つ・30分以内）
- 苦手な食材は固定：柑橘系・グリーンピース・激辛系
- 栄養バランスグラフ（カロリー・PFCバランス・栄養素内訳・野菜量）
- 1週間分の買い物リスト（カテゴリ別・合算済み・チェックボックス付き）
- 個別レシピの差し替え機能（差し替え時に買い物リストも自動更新）

## モデル・API

- モデル: `gemini-2.0-flash`
- JSONモード使用（`response_mime_type: "application/json"`）
- APIキーは `.env` の `GEMINI_API_KEY`
