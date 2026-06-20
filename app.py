from datetime import datetime
import json
import os
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from tools.meal_planner import generate_plan, replace_meal

st.set_page_config(page_title="週間夕飯プランナー", page_icon="🍳", layout="centered")

DATA_FILE = "meal_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── データ読み込み（苦手食材の初期値に使用）
data = load_data()
saved_disliked = (data or {}).get("disliked", "柑橘系, グリーンピース, 激辛系")

# ── サイドバー
with st.sidebar:
    st.header("設定")
    disliked_input = st.text_input(
        "🚫 苦手な食材（カンマ区切り）",
        value=saved_disliked,
        placeholder="例: 柑橘系, えび, 辛いもの"
    )
    sidebar_gen_btn = st.button("🔄 今週のレシピを生成する", use_container_width=True, type="primary")
    if data is not None:
        st.divider()
        st.success("生成済み", icon="✅")
        if data.get("generated_at"):
            st.caption(f"生成日: {data['generated_at']}")
        st.caption("気に入らない日は各レシピの「差し替え」を押してください")

# ── タイトル
st.markdown("""
<style>
.app-title {
    font-size: 2.5rem;
    font-weight: 700;
    line-height: 1.2;
    margin-bottom: 0.25rem;
}
@media (max-width: 480px) {
    .app-title { font-size: 1.6rem; }
}
</style>
<p class="app-title">🍳 週間夕飯プランナー</p>
""", unsafe_allow_html=True)
st.caption("月〜金の夕飯をAIが自動プランニング。週1回の買い物で全部作れます。")

# ── ウェルカム画面（未生成時のみ）
main_gen_btn = False
if data is None:
    st.info("👈 スマホの方は左上の ≡ をタップ、またはこちらのボタンから生成できます", icon="📱")
    main_gen_btn = st.button("▶ まずはレシピを生成する", type="primary", use_container_width=True)

# ── 生成処理
should_generate = sidebar_gen_btn or main_gen_btn
if should_generate:
    _gen_error = None
    with st.spinner("AIが5日分のレシピを考えています...（30秒ほどかかります）"):
        try:
            new_data = generate_plan(disliked_input)
            new_data["disliked"] = disliked_input
            new_data["generated_at"] = datetime.now().strftime("%Y/%m/%d")
            save_data(new_data)
        except Exception as e:
            _gen_error = e
    if _gen_error:
        st.error(f"生成に失敗しました: {_gen_error}")
    else:
        st.rerun()

if data is None:
    st.stop()

# ── 結果表示
meals = data.get("meals", [])
shopping = data.get("shopping_list", [])

tab1, tab2, tab3 = st.tabs(["📅 レシピ", "📊 栄養", "🛒 買い物"])

# ── タブ1: レシピカード（縦並び・モバイル対応）
with tab1:
    if data.get("generated_at"):
        st.caption(f"生成日: {data['generated_at']}")

    for i, meal in enumerate(meals):
        n = meal.get("nutrition", {})
        tool_icon = "🍳" if meal.get("tool") == "フライパン" else "🥘"

        with st.container(border=True):
            st.markdown(f"**{meal['day']}　{meal['name']}**")
            st.caption(
                f"{tool_icon} {meal.get('tool', '')} ｜ "
                f"⏱ {meal.get('time', '?')}分 ｜ "
                f"🔥 {n.get('calories', '?')} kcal（2人分）"
            )

            exp1, exp2 = st.columns(2)
            with exp1:
                with st.expander("🥦 材料"):
                    for ing in meal.get("ingredients", []):
                        st.write(f"• {ing['name']}　{ing['amount']}")
            with exp2:
                with st.expander("📝 作り方"):
                    for j, step in enumerate(meal.get("steps", []), 1):
                        st.write(f"{j}. {step}")

            replace_clicked = st.button("🔄 差し替え", key=f"replace_{i}", type="secondary")

        if replace_clicked:
            _rep_error = None
            current_disliked = data.get("disliked", saved_disliked)
            with st.spinner(f"{meal['day']}を差し替え中..."):
                try:
                    new_meal, new_shopping = replace_meal(meal["day"], meals, current_disliked)
                    data["meals"][i] = new_meal
                    data["shopping_list"] = new_shopping
                    save_data(data)
                except Exception as e:
                    _rep_error = e
            if _rep_error:
                st.error(f"差し替えに失敗しました: {_rep_error}")
            else:
                st.rerun()

# ── タブ2: 栄養グラフ
with tab2:
    if not meals:
        st.warning("レシピを生成してください")
    else:
        days       = [m["day"]                            for m in meals]
        calories   = [m["nutrition"].get("calories", 0)   for m in meals]
        protein    = [m["nutrition"].get("protein", 0)    for m in meals]
        carbs      = [m["nutrition"].get("carbs", 0)      for m in meals]
        fat        = [m["nutrition"].get("fat", 0)        for m in meals]
        vegetables = [m["nutrition"].get("vegetables", 0) for m in meals]

        # 週平均サマリー
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("平均カロリー(2人分)", f"{int(sum(calories)/len(calories))} kcal")
        c2.metric("平均タンパク質",     f"{int(sum(protein)/len(protein))} g")
        c3.metric("平均炭水化物",       f"{int(sum(carbs)/len(carbs))} g")
        c4.metric("平均野菜摂取",       f"{int(sum(vegetables)/len(vegetables))} g")

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("日別カロリー（2人分）")
            fig_cal = px.bar(
                x=days, y=calories, color=calories,
                color_continuous_scale="oranges",
                labels={"x": "曜日", "y": "kcal", "color": "kcal"}
            )
            fig_cal.add_hline(y=1400, line_dash="dot", line_color="red",
                              annotation_text="目安 700kcal×2人")
            fig_cal.update_layout(coloraxis_showscale=False)
            st.plotly_chart(fig_cal, use_container_width=True)

        with col2:
            st.subheader("週平均PFCバランス")
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

        st.subheader("日別 栄養素内訳（g）")
        fig_stack = go.Figure(data=[
            go.Bar(name="タンパク質", x=days, y=protein, marker_color="#FF6B6B"),
            go.Bar(name="炭水化物",   x=days, y=carbs,   marker_color="#4ECDC4"),
            go.Bar(name="脂質",       x=days, y=fat,     marker_color="#FFE66D"),
        ])
        fig_stack.update_layout(barmode="group", yaxis_title="g", legend_title="栄養素")
        st.plotly_chart(fig_stack, use_container_width=True)

# ── タブ3: 買い物リスト
with tab3:
    st.subheader("今週の買い物リスト")
    st.caption("⚠️ チェック状態はブラウザを閉じると消えます。共有にはコピー用テキストをご利用ください。")

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
    st.subheader("📋 コピー用テキスト")
    st.code(list_text, language=None)
