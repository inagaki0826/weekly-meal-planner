import json
import re
from tools.gemini_client import generate

DEFAULT_DISLIKED = "柑橘系, グリーンピース, 激辛系"

def _parse(raw: str) -> dict:
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            return json.loads(m.group())
        raise ValueError("JSONの解析に失敗しました")

def generate_plan(disliked: str = DEFAULT_DISLIKED) -> dict:
    dislike_line = f"- 使用禁止の食材：{disliked}" if disliked.strip() else ""
    prompt = f"""
栄養士として共働き夫婦2人分の平日5日間（月〜金）の夕飯レシピを考えてください。

【条件】
- 2人前
- フライパン1つまたは鍋1つだけで作れる（洗い物を最小限に）
- 調理時間30分以内
- 健康的でたんぱく質・野菜・炭水化物のバランスが良い
- 5日間すべて異なる料理
{dislike_line}

以下のJSON形式で出力してください：
{{
  "meals": [
    {{
      "day": "月曜日",
      "name": "料理名",
      "tool": "フライパン",
      "time": 20,
      "ingredients": [
        {{"name": "鶏むね肉", "amount": "300g"}}
      ],
      "steps": ["手順1", "手順2", "手順3"],
      "nutrition": {{
        "calories": 450,
        "protein": 35,
        "carbs": 40,
        "fat": 12,
        "vegetables": 200
      }}
    }}
  ],
  "shopping_list": [
    {{
      "category": "肉・魚",
      "items": [
        {{"name": "鶏むね肉", "amount": "300g"}}
      ]
    }}
  ]
}}

nutritionはすべて2人分の合計値で整数。shopping_listは5日分をまとめて重複食材を合算。
カテゴリ例：肉・魚、野菜、きのこ・海藻、豆腐・卵・乳製品、調味料・乾物
"""
    raw = generate(prompt, json_mode=True)
    return _parse(raw)


def replace_meal(day: str, current_meals: list, disliked: str = DEFAULT_DISLIKED) -> tuple:
    used_names = "、".join([m["name"] for m in current_meals if m["day"] != day])
    dislike_line = f"- 使用禁止の食材：{disliked}" if disliked.strip() else ""

    prompt = f"""
{day}の夕飯レシピを1つ考えてください（2人前）。

【条件】
- フライパン1つまたは鍋1つだけ
- 30分以内
- 健康的でバランスが良い
- 今週すでに使っているこれらの料理とは別のもの：{used_names}
{dislike_line}

以下のJSON形式のみで出力：
{{
  "day": "{day}",
  "name": "料理名",
  "tool": "フライパン",
  "time": 20,
  "ingredients": [{{"name": "食材名", "amount": "量"}}],
  "steps": ["手順1", "手順2"],
  "nutrition": {{
    "calories": 450,
    "protein": 35,
    "carbs": 40,
    "fat": 12,
    "vegetables": 200
  }}
}}
"""
    raw = generate(prompt, json_mode=True)
    new_meal = _parse(raw)
    updated_meals = [new_meal if m["day"] == day else m for m in current_meals]
    new_shopping = _rebuild_shopping(updated_meals, disliked)
    return new_meal, new_shopping


def _rebuild_shopping(meals: list, disliked: str = DEFAULT_DISLIKED) -> list:
    meal_text = "\n".join([
        f"{m['day']}「{m['name']}」\n" + "\n".join([f"  - {i['name']} {i['amount']}" for i in m["ingredients"]])
        for m in meals
    ])
    prompt = f"""
以下の5日分の夕飯の食材から、1週間分の買い物リストを作ってください。
同じ食材は合算し、カテゴリ別にまとめてください。

{meal_text}

JSON形式のみで出力：
{{
  "shopping_list": [
    {{
      "category": "カテゴリ名",
      "items": [{{"name": "食材名", "amount": "合計量"}}]
    }}
  ]
}}

カテゴリ例：肉・魚、野菜、きのこ・海藻、豆腐・卵・乳製品、調味料・乾物
"""
    raw = generate(prompt, json_mode=True)
    data = _parse(raw)
    return data.get("shopping_list", [])
