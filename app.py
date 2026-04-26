import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="2026 終極監控系統", layout="wide")

# --- 抓股票名稱 ---
def get_stock_name(code):
    symbol = code.split('.')[0]
    url = f"https://tw.stock.yahoo.com/quote/{symbol}"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.find('title').get_text()
        name = title.split('(')[0].strip()
        return name if name else symbol
    except:
        return symbol

# --- 安全轉 float ---
def safe_float(text):
    try:
        return float(text.replace('%', '').replace(',', '').strip())
    except:
        return None

# --- 抓佩程資料 ---
def get_peicheng_index_data(symbol_short):
    url = f"http://www.peicheng.com.tw/asp/stockquery/{symbol_short}.htm"
    try:
        res = requests.get(url, timeout=10)
        res.encoding = 'big5'
        soup = BeautifulSoup(res.text, 'html.parser')

        eps = None
        yoy_list = []

        # 抓EPS
        for td in soup.find_all('td'):
            if "機構估稅後EPS" in td.get_text():
                val = td.find_next_sibling('td')
                if val:
                    eps = safe_float(val.get_text())
                break

        # 抓YoY
        rows = soup.find_all('tr')
        found = False
        yoy_col_idx = -1

        for row in rows:
            cells = row.find_all('td')
            texts = [c.get_text(strip=True) for c in cells]

            if not found and any("YoY" in t for t in texts):
                for i, t in enumerate(texts):
                    if "單月YoY" in t:
                        yoy_col_idx = i
                        found = True
                continue

            if found and len(texts) > yoy_col_idx and texts[0].isdigit():
                val = safe_float(texts[yoy_col_idx])
                if val is not None:
                    yoy_list.append(val)

            if len(yoy_list) >= 6:
                break

        # 👉 修正：只取最新3筆
        yoy_list = yoy_list[:3]

        avg_3m_yoy = sum(yoy_list) / len(yoy_list) if yoy_list else 0

        # 👉 修正：累計用平均（不要用單月）
        rev_yoy = avg_3m_yoy

        return {
            "eps": eps,
            "rev_yoy": round(rev_yoy, 2),
            "avg_3m_yoy": round(avg_3m_yoy, 2)
        }

    except:
        return None

# --- Forward PE ---
def get_forward_pe(ticker):
    try:
        info = ticker.info
        pe = info.get("forwardPE")
        return pe if pe and pe > 0 else None
    except:
        return None


# --- UI ---
st.title("🚀 2026 終極監控系統")
st.markdown("### 【動態位階校準】x【智慧趨勢監控】")

default_stocks = "2330.TW, 8299.TWO, 2337.TW, 6147.TWO, 2401.TW, 8039.TW, 2485.TW, 2474.TW, 3217.TWO, 2476.TW"
user_input = st.text_input("請輸入股票代號", default_stocks)

if st.button("啟動全自動趨勢診斷"):

    stock_list = [s.strip().upper() for s in user_input.split(",")]
    results = []

    with st.spinner('分析中...'):

        for code in stock_list:
            symbol_short = code.split('.')[0]
            ticker = yf.Ticker(code)

            stock_name = get_stock_name(code)
            hist = ticker.history(period="150d")

            if hist.empty:
                continue

            curr_price = round(hist['Close'].iloc[-1], 2)
            period_high = round(hist['High'].max(), 2)
            drop_from_high = round(((curr_price - period_high) / period_high) * 100, 2)

            ma5 = hist['Close'].rolling(5).mean().iloc[-1]
            ma10 = hist['Close'].rolling(10).mean().iloc[-1]
            ma20 = hist['Close'].rolling(20).mean().iloc[-1]
            ma60 = hist['Close'].rolling(60).mean().iloc[-1]

            is_all_up = curr_price > ma5 > ma10 > ma20 > ma60
            bias_5 = round(((curr_price - ma5) / ma5) * 100, 2)

            data = get_peicheng_index_data(symbol_short)
            if not data or data['eps'] is None:
                continue

            # ===== 目標價（修正版）=====
            forward_pe = get_forward_pe(ticker)

            dynamic_pe = curr_price / data['eps'] if data['eps'] > 0 else 10
            base_pe = forward_pe if forward_pe else dynamic_pe

            # 動能調整
            if data['avg_3m_yoy'] > 50:
                factor = 1.3
            elif data['avg_3m_yoy'] > 30:
                factor = 1.2
            elif data['avg_3m_yoy'] > 10:
                factor = 1.1
            elif data['avg_3m_yoy'] < 0:
                factor = 0.8
            else:
                factor = 1.0

            pred_pe = min(max(base_pe * factor, 8), 40)
            calc_target = data['eps'] * pred_pe

            # 趨勢校準
            if is_all_up:
                target_price = round(calc_target, 2)
            elif calc_target > curr_price * 1.5:
                target_price = round(curr_price * 1.3, 2)
            else:
                target_price = round(calc_target, 2)

            # ===== 成功率（評分制）=====
            score = 0

            if data['rev_yoy'] > 30:
                score += 30
            elif data['rev_yoy'] > 10:
                score += 20

            if is_all_up:
                score += 30

            if bias_5 < 5:
                score += 20

            if drop_from_high < -10:
                score += 20

            success_rate = min(score, 95)

            # ===== 位階 =====
            if drop_from_high < -20 and curr_price < ma20 * 1.05:
                level = "🆘超跌"
            elif is_all_up:
                level = "🔥強勢"
            elif curr_price > ma60:
                level = "高檔整理"
            else:
                level = "弱勢"

            results.append({
                "名稱": f"{stock_name}({symbol_short})",
                "最新價": curr_price,
                "高點回檔": f"{drop_from_high}%",
                "累計YoY": f"{data['rev_yoy']}%",
                "3月平均": f"{data['avg_3m_yoy']}%",
                "預估PE": round(pred_pe, 2),
                "推算目標": target_price,
                "5日乖離": f"{bias_5}%",
                "站上線": "是" if is_all_up else "否",
                "成功率": f"{success_rate}%",
                "位階": level
            })

    if results:
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)
