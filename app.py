import json
import os
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from tools.meal_planner import generate_plan, replace_meal

st.set_page_config(page_title="週間夕飯プランナー", page_icon="🍳", layout="wide")

DATA_FILE = "meal_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── サイドバー ──────────────────────────────────────────────────
with st.sidebar:
    st.header("設定")
    st.info("苦手な食材：柑橘系・グリーンピース・激辛系", icon="🚫")
    generate_btn = st.button("🔄 今週のレシピを生成する", use_container_width=True, type="primary")

    if load_data() is not None:
        st.divider()
        st.success("生成済み", icon="✅")
        st.caption("気に入らない日は各レシピの「差し替え」ボタンを押してください")

# ── 生成処理 ───────────────────────────────────────────────────
if generate_btn:
    with st.spinner("AIが5日分のレシピを考えています...（30秒ほどかかります）"):
        try:
            data = generate_plan()
            save_data(data)
            st.rerun()
        except Exception as e:
            st.error(f"生成に失敗しました: {e}")

# ── 未生成時のガイド ───────────────────────────────────────────
data = load_data()
if data is None:
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 使い方")
        st.markdown("""
1. 左のサイドバーの **「今週のレシピを生成する」** を押す
2. AIが月〜金の夕飯を5日分考えます
3. **レシピ** を確認して、気に入らない日は差し替え
4. **買い物リスト** をコピーして週1回の買い物へ
        """)
    st.stop()

# ── 結果表示 ───────────────────────────────────────────────────
meals = data.get("meals", [])
shopping = data.get("shopping_list", [])

tab1, tab2, tab3 = st.tabs(["📅 今週のレシピ", "📊 栄養バランス", "🛒 買い物リスト"])

# ── タブ1: レシピカード ─────────────────────────────────────────
with tab1:
    cols = st.columns(5)
    for i, meal in enumerate(meals):
        with cols[i]:
            tool_icon = "🍳" if meal.get("tool") == "フライパン" else "🥘"
            st.markdown(f"### {meal['day']}")
            st.markdown(f"**{meal['name']}**")
            st.caption(f"{tool_icon} {meal.get('tool', '')} ｜ ⏱ {meal.get('time', '?')}分")

            n = meal.get("nutrition", {})
            st.metric("カロリー(2人分)", f"{n.get('calories', '?')} kcal")

            with st.expander("🥦 材料"):
                for ing in meal.get("ingredients", []):
                    st.write(f"• {ing['name']}　{ing['amount']}")

            with st.expander("📝 作り方"):
                for j, step in enumerate(meal.get("steps", []), 1):
                    st.write(f"{j}. {step}")

            if st.button("🔄 差し替え", key=f"replace_{i}", use_container_width=True):
                with st.spinner(f"{meal['day']}を差し替え中..."):
                    try:
                        new_meal, new_shopping = replace_meal(meal["day"], meals)
                        data["meals"][i] = new_meal
                        data["shopping_list"] = new_shopping
                        save_data(data)
                        st.rerun()
                    except Exception as e:
                        st.error(f"差し替えに失敗しました: {e}")

# ── タブ2: 栄養グラフ ───────────────────────────────────────────
with tab2:
    if not meals:
        st.warning("レシピを生成してください")
    else:
        days       = [m["day"]                          for m in meals]
        calories   = [m["nutrition"].get("calories", 0)   for m in meals]
        protein    = [m["nutrition"].get("protein", 0)    for m in meals]
        carbs      = [m["nutrition"].get("carbs", 0)      for m in meals]
        fat        = [m["nutrition"].get("fat", 0)        for m in meals]
        vegetables = [m["nutrition"].get("vegetables", 0) for m in meals]

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("1日あたりのカロリー（2人分）")
            fig_cal = px.bar(
                x=days, y=calories,
                color=calories,
                color_continuous_scale="oranges",
                labels={"x": "曜日", "y": "kcal", "color": "kcal"}
            )
            fig_cal.add_hline(
                y=1400, line_dash="dot", line_color="red",
                annotation_text="目安 700kcal×2人"
            )
            fig_cal.update_layout(coloraxis_showscale=False)
            st.plotly_chart(fig_cal, use_container_width=True)

        with col2:
            st.subheader("週平均のPFCバランス（カロリー換算）")
            avg_p = sum(protein) / len(protein)
            avg_c = sum(carbs)   / len(carbs)
            avg_f = sum(fat)     / len(fat)
            fig_pfc = px.pie(
                values=[avg_p * 4, avg_c * 4, avg_f * 9],
                names=["タンパク質", "炭水化物", "脂質"],
                color_discrete_sequence=["#FF6B6B", "#4ECDC4", "#FFE66D"],
                hole=0.4
            )
            fig_pfc.update_traces(textinfo="percent+label")
            st.plotly_chart(fig_pfc, use_container_width=True)

        st.subheader("日別 栄養素（g）")
        fig_stack = go.Figure(data=[
            go.Bar(name="タンパク質", x=days, y=protein,   marker_color="#FF6B6B"),
            go.Bar(name="炭水化物",   x=days, y=carbs,     marker_color="#4ECDC4"),
            go.Bar(name="脂質",       x=days, y=fat,       marker_color="#FFE66D"),
        ])
        fig_stack.update_layout(barmode="group", yaxis_title="g", legend_title="栄養素")
        st.plotly_chart(fig_stack, use_container_width=True)

        st.subheader("日別 野菜摂取量（g）")
        fig_veg = px.bar(
            x=days, y=vegetables,
            color=vegetables,
            color_continuous_scale="greens",
            labels={"x": "曜日", "y": "g", "color": "g"}
        )
        fig_veg.add_hline(
            y=350, line_dash="dot", line_color="green",
            annotation_text="1日の目標 350g"
        )
        fig_veg.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig_veg, use_container_width=True)

# ── タブ3: 買い物リスト ─────────────────────────────────────────
with tab3:
    st.subheader("今週の買い物リスト")
    st.caption("チェックボックスで購入済みを管理できます（チェック状態は端末ごとに独立しています）")

    list_text = "【今週の買い物リスト】\n"
    shop_cols = st.columns(2)

    for ci, category in enumerate(shopping):
        with shop_cols[ci % 2]:
            st.markdown(f"**{category['category']}**")
            for j, item in enumerate(category.get("items", [])):
                st.checkbox(f"{item['name']}　{item['amount']}", key=f"check_{ci}_{j}")
            st.write("")
        list_text += f"\n■ {category['category']}\n"
        for item in category.get("items", []):
            list_text += f"  □ {item['name']}　{item['amount']}\n"

    st.divider()
    st.text_area("コピー用テキスト", value=list_text, height=250)
