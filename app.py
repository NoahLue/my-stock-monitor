import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="2026 終極監控系統", layout="wide")

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
    except: return symbol

def safe_float(text):
    try: return float(text.replace('%', '').replace(',', '').strip())
    except: return None

def get_peicheng_index_data(symbol_short):
    url = f"http://www.peicheng.com.tw/asp/stockquery/{symbol_short}.htm"
    try:
        res = requests.get(url, timeout=10)
        res.encoding = 'big5'
        soup = BeautifulSoup(res.text, 'html.parser')
        eps = None
        yoy_list = []
        for td in soup.find_all('td'):
            if "機構估稅後EPS" in td.get_text():
                val = td.find_next_sibling('td')
                if val: eps = safe_float(val.get_text())
                break
        rows = soup.find_all('tr')
        found = False
        yoy_col_idx = -1
        for row in rows:
            cells = row.find_all('td')
            texts = [c.get_text(strip=True) for c in cells]
            if not found and any("YoY" in t for t in texts):
                for i, t in enumerate(texts):
                    if "單月YoY" in t:
                        yoy_col_idx = i; found = True
                continue
            if found and len(texts) > yoy_col_idx and texts[0].isdigit():
                val = safe_float(texts[yoy_col_idx])
                if val is not None: yoy_list.append(val)
            if len(yoy_list) >= 3: break
        avg_3m_yoy = sum(yoy_list) / len(yoy_list) if yoy_list else 0
        return {"eps": eps, "rev_yoy": round(yoy_list[0] if yoy_list else 0, 2), "avg_3m_yoy": round(avg_3m_yoy, 2)}
    except: return None

st.title("🚀 2026 終極監控系統（精準校準版）")
default_stocks = "2330.TW, 8046.TW, 8299.TWO, 2337.TW"
user_input = st.text_input("請輸入股票代號", default_stocks)

if st.button("啟動全自動趨勢診斷"):
    stock_list = [s.strip().upper() for s in user_input.split(",")]
    results = []
    for code in stock_list:
        symbol_short = code.split('.')[0]
        ticker = yf.Ticker(code)
        stock_name = get_stock_name(code)
        hist = ticker.history(period="150d")
        if hist.empty: continue
        curr_price = round(hist['Close'].iloc[-1], 2)
        period_high = round(hist['High'].max(), 2)
        drop_from_high = round(((curr_price - period_high) / period_high) * 100, 2)

        ma5, ma20, ma60 = [hist['Close'].rolling(w).mean().iloc[-1] for w in [5, 20, 60]]
        is_all_up = curr_price > ma5 > ma20 > ma60
        bias_5 = round(((curr_price - ma5) / ma5) * 100, 2)

        data = get_peicheng_index_data(symbol_short)
        if not data: continue

        # === 核心估值邏輯修正 ===
        book_value = ticker.info.get('bookValue', 0)
        
        if data['eps'] and data['eps'] > (curr_price / 100): # EPS 必須合理，不能太小
            # 獲利股：動能 PE 模型
            f_pe = ticker.info.get("forwardPE", 15)
            factor = 1.2 if data['avg_3m_yoy'] > 30 else 1.0
            pred_pe = min(max(f_pe * factor, 12), 35)
            target_price = round(data['eps'] * pred_pe, 2)
            pe_display = round(pred_pe, 1)
        elif book_value > 0:
            # 轉機/虧損股：PB 模型
            pb_ratio = 1.8 if data['avg_3m_yoy'] > 20 else 1.4
            target_price = round(book_value * pb_ratio, 2)
            pe_display = f"PB:{pb_ratio}"
        else:
            target_price = round(curr_price * 1.1, 2)
            pe_display = "N/A"

        # 位階判定
        if drop_from_high < -20: level = "🆘超跌"
        elif is_all_up: level = "🔥強勢"
        else: level = "整理"

        results.append({
            "名稱": f"{stock_name}({symbol_short})",
            "最新價": curr_price,
            "高點回檔": f"{drop_from_high}%",
            "累計YoY": f"{data['rev_yoy']}%",
            "3月平均": f"{data['avg_3m_yoy']}%",
            "預估PE/PB": pe_display,
            "推算目標": target_price,
            "站上線": "是" if is_all_up else "否",
            "成功率": f"{(85 if data['avg_3m_yoy']>20 else 60) + (10 if is_all_up else 0)}%",
            "位階": level
        })

    if results:
        st.dataframe(pd.DataFrame(results), use_container_width=True)
