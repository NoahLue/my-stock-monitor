import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup

# 設定網頁標題與寬版顯示
st.set_page_config(page_title="2026 終極監控系統", layout="wide")

# --- 保留所有原始函數，完全不刪減 ---
def safe_float(text):
    try:
        return float(text.replace('%', '').replace(',', '').strip())
    except:
        return None

def get_forward_pe(ticker):
    try:
        info = ticker.info
        pe = info.get("forwardPE")
        if pe and pe > 0:
            return pe
    except:
        pass
    return None

def get_peicheng_index_data(symbol_short):
    url = f"http://www.peicheng.com.tw/asp/stockquery/{symbol_short}.htm"
    try:
        res = requests.get(url, timeout=10)
        res.encoding = 'big5'
        soup = BeautifulSoup(res.text, 'html.parser')
        eps, monthly_yoy, rev_yoy = None, None, None
        rows = soup.find_all('tr')
        header_map, found_header = {}, False
        for row in rows:
            cells = row.find_all('td')
            texts = [c.get_text(strip=True) for c in cells]
            if not found_header and any("YoY" in t for t in texts):
                for i, t in enumerate(texts):
                    if "單月YoY" in t: header_map["monthly"] = i
                    if "累計YoY" in t: header_map["acc"] = i
                found_header = True
                continue
            if found_header and len(texts) > 0:
                if texts[0].isdigit():
                    if "monthly" in header_map: monthly_yoy = safe_float(texts[header_map["monthly"]])
                    if "acc" in header_map: rev_yoy = safe_float(texts[header_map["acc"]])
                    break
        for td in soup.find_all('td'):
            if "機構估稅後EPS" in td.get_text():
                val = td.find_next_sibling('td')
                if val: eps = safe_float(val.get_text())
                break
        return {"eps": eps, "monthly_yoy": monthly_yoy or 0, "rev_yoy": rev_yoy or 0}
    except:
        return None

# --- Streamlit 介面佈置 ---
st.title("🚀 2026 終極監控系統")
st.markdown("### 【回檔深度】與【波段防護】偵測儀表板")

# 1. 標的設定 (改為網頁輸入，預設填入你原本的清單)
default_stocks = "2330.TW, 8299.TWO, 2337.TW, 6147.TWO, 2401.TW, 8039.TW, 2485.TW, 2474.TW, 3217.TWO, 2476.TW"
user_input = st.text_input("請輸入股票代號 (用英文逗號隔開)", default_stocks)

if st.button("開始全自動診斷"):
    # 將輸入轉為串列
    stock_list = [s.strip().upper() for s in user_input.split(",")]
    results = []
    
    with st.spinner('偵測中...'):
        for code in stock_list:
            symbol_short = code.split('.')[0]
            ticker = yf.Ticker(code)
            
            # 抓取較長天數確保 MA60 與 波段高點準確 (保留 120d)
            hist = ticker.history(period="120d")
            if hist.empty:
                continue

            curr_price = round(hist['Close'].iloc[-1], 2)
            
            # === 高點回檔 Debug (完全保留) ===
            period_high = round(hist['High'].max(), 2)
            drop_from_high = round(((curr_price - period_high) / period_high) * 100, 2)
            
            # === 技術指標 Debug (完全保留) ===
            ma5 = round(hist['Close'].rolling(5).mean().iloc[-1], 2)
            ma10 = round(hist['Close'].rolling(10).mean().iloc[-1], 2)
            ma20 = round(hist['Close'].rolling(20).mean().iloc[-1], 2)
            ma60 = round(hist['Close'].rolling(60).mean().iloc[-1], 2)
            
            # 站上所有線
            is_all_up = curr_price > ma5 > ma10 > ma20 > ma60
            # 5日乖離率
            bias_5 = round(((curr_price - ma5) / ma5) * 100, 2)
            
            data = get_peicheng_index_data(symbol_short)
            if not data or data['eps'] is None:
                continue

            # === 計算 PE 與 目標價 (完全保留原始邏輯) ===
            forward_pe = get_forward_pe(ticker)
            if data['eps'] > 0:
                p_pe = forward_pe if forward_pe else curr_price / data['eps']
                if p_pe > 80: p_pe = 40
                elif p_pe < 5: p_pe = 10
                target_price = round(data['eps'] * p_pe, 2)
                dynamic_pe = round(curr_price / data['eps'], 2)
                pred_pe = round(p_pe, 2)
            else:
                pred_pe = round(forward_pe, 2) if forward_pe else 0
                target_price = "待轉盈"
                dynamic_pe = "負數"

            # === 抓鬼診斷 4.0 (完整保留整合邏輯) ===
            if drop_from_high < -20 and data['rev_yoy'] > 50:
                ghost_check = "⚠️重鬼(利多崩跌)"
            elif bias_5 > 10:
                ghost_check = "🧨超速(乖離過大)" 
            elif drop_from_high > -5 and is_all_up:
                ghost_check = "✅強勢(大戶鎖籌)"
            elif data['rev_yoy'] < 10 and curr_price > ma20 and (isinstance(pred_pe, (int, float)) and pred_pe > 30):
                ghost_check = "⚠️虛火(沒賺亂漲)"
            elif is_all_up and data['rev_yoy'] > 20:
                ghost_check = "✅沒鬼(多頭發動)"
            else:
                ghost_check = "正常"

            # 進化診斷 (完全保留原始邏輯)
            if is_all_up and data['rev_yoy'] > 30:
                diagnosis = "🔥全線啟動"
            elif data['eps'] <= 0 and data['rev_yoy'] > 10:
                diagnosis = "🚀轉機啟動"
            elif curr_price < ma60 and data['rev_yoy'] > 100:
                diagnosis = "💎明珠蒙塵"
            else:
                diagnosis = "觀察等待"

            results.append({
                "名稱": code,
                "最新價": curr_price,
                "波段高點": period_high,
                "高點回檔": f"{drop_from_high}%",
                "累計年增": f"{data['rev_yoy']}%",
                "動態PE": dynamic_pe,
                "預估PE": pred_pe,
                "推算目標": target_price,
                "5日乖離": f"{bias_5}%",
                "站上所有線": "🌕是" if is_all_up else "🌑否",
                "成功率": f"{(80 if data['rev_yoy']>30 else 50) + (20 if is_all_up else 0)}%",
                "位階": "偏強" if curr_price > ma20 else "超跌" if drop_from_high < -20 else "整理",
                "進化診斷": diagnosis,
                "有沒有鬼": ghost_check
            })

    if results:
        # 轉換為 DataFrame 並以網頁表格呈現
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("請輸入代號並點擊按鈕開始分析。")
