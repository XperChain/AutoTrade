import streamlit as st
from pymongo import MongoClient
import pandas as pd
from datetime import datetime
import numpy as np
import altair as alt
import hashlib

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()
# -----------------------------
# 1. MongoDB 연결
# -----------------------------

def get_mongo_db():
    MONGO_URL = st.secrets["mongodb"]["uri"]    
    client = MongoClient(MONGO_URL)
    return client["blockchain_db"]

db = get_mongo_db()
users_col = db["users"]
setting_col = db["setting"]
transactions_col = db["transactions"]

# -----------------------------
# 2. 로그인 UI (사이드바)
# -----------------------------
st.sidebar.title("🔐 로그인")
username_input = st.sidebar.text_input("사용자명")
password_input = st.sidebar.text_input("비밀번호", type="password")

# -----------------------------
# 3. MongoDB에서 로그인 확인
# -----------------------------
def authenticate_user(username, password):
    user = users_col.find_one({"username": username})        
    if user:        
        return user.get("password_hash") == hash_password(password)
    else:
        return False

is_authenticated = authenticate_user(username_input, password_input)

# -----------------------------
# 4. 자동매수 상태 표시/설정
# -----------------------------
st.sidebar.markdown("### ⚙️ 자동 매수 상태")

current_setting = setting_col.find_one()
current_status = current_setting.get("status", "off") if current_setting else "off"

if is_authenticated:
    st.sidebar.success(f"✅ {username_input}님 환영합니다!")

    status_radio = st.sidebar.radio(
        "자동 매수 기능",
        options=["ON", "OFF"],
        index=0 if current_status == "on" else 1
    )
    
    new_status = "on" if status_radio == "ON" else "off"
    if new_status != current_status:
        setting_col.update_one({}, {"$set": {"status": new_status}}, upsert=True)
        st.sidebar.success(f"자동 매수 상태가 '{status_radio}'로 변경되었습니다.")
else:
    st.sidebar.radio(
        "자동 매수 기능",
        options=["ON", "OFF"],
        index=0 if current_status == "on" else 1,
        disabled=True
    )
    if password_input:
        st.sidebar.error("❌ 로그인 실패")

# -----------------------------
# 5. 거래 정보 출력
# -----------------------------
st.title("📊 자동 매매 트레이딩 대시보드")

data = list(transactions_col.find())
if not data:
    st.warning("❗ 거래 데이터가 없습니다.")
else:
    df = pd.DataFrame(data)
    df["datetime"] = pd.to_datetime(df.get("datetime", datetime.now()), errors="coerce")
    df = df.dropna(subset=["datetime"])
    df = df.sort_values("datetime", ascending=False)

    df["profit_krw"] = df["sale_value"] - df["buy_value"] - df["fee"]

    avg_profit_ratio = df["profit_ratio"].mean()
    total_profit_krw = df["profit_krw"].sum()
    success_count = (df["profit_krw"] > 0).sum()
    fail_count = (df["profit_krw"] <= 0).sum()

    col1, col2, col3 = st.columns(3)
    col1.markdown(
        f"<h5>📈 평균 수익률<br><span style='color:{'blue' if avg_profit_ratio >= 0 else 'red'}'>{avg_profit_ratio*100:.2f}%</span></h5>",
        unsafe_allow_html=True
    )
    col2.markdown(
        f"<h5>💰 총 수익 금액<br><span style='color:{'blue' if total_profit_krw >= 0 else 'red'}'>{total_profit_krw:,.0f} 원</span></h5>",
        unsafe_allow_html=True
    )
    col3.markdown(f"<h5>✅ 성공/실패<br>{success_count} / {fail_count}</h5>", unsafe_allow_html=True)

    # 그래프
    st.subheader("📉 일별 수익률 및 누적 수익률")
    df["date"] = df["datetime"].dt.date
    daily_summary = df.groupby("date")["profit_ratio"].mean().reset_index()
    daily_summary["cumulative_profit"] = daily_summary["profit_ratio"].cumsum()

    chart = alt.Chart(daily_summary).transform_fold(
        ["profit_ratio", "cumulative_profit"],
        as_=["Metric", "Value"]
    ).mark_line(point=True).encode(
        x='date:T', y='Value:Q', color='Metric:N'
    ).properties(width=700, height=400)

    st.altair_chart(chart, use_container_width=True)

    # 테이블
    if is_authenticated:
        st.subheader("🧾 거래 상세 정보")
        st.dataframe(
            df[["datetime", "title", "ticker", "buy_value", "sale_value", "fee", "profit_ratio", "profit_krw"]],
            use_container_width=True
        )
