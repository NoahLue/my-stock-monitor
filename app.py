import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup

# 設定網頁標題與寬版顯示
st.set_page_config(page_title="2026 終極監控系統", layout="wide")

# --- 1. 自動抓取台股中文名稱 ---
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

# --- 2. 核心邏輯函數 ---
def safe_float(text):
    try:
        return float(text.replace('%', '').replace(',', '').strip())
    except:
        return None

def get_peicheng_index_data(symbol_short):
    url = f"http://www.peicheng.com.tw/asp/stockquery/{symbol_short}.htm"
    try:
        res = requests.get(url, timeout=10)
        res.encoding = 'big5'
        soup = BeautifulSoup(res.text, 'html.parser')
        eps, rev_yoy = None, 0
        rows = soup.find_all('tr')
        header_map, found_header = {}, False
        for row in rows:
            cells = row.find_all('td')
            texts = [c.get_text(strip=True) for c in cells]
            if not found_header and any("YoY" in t for t in texts):
                for i, t in enumerate(texts):
                    if "累計YoY" in t: header_map["acc"] = i
                found_header = True
                continue
            if found_header and len(texts) > 0 and texts[0].isdigit():
                if "acc" in header_map: rev_yoy = safe_float(texts[header_map["acc"]])
                break
        for td in soup.find_all('td'):
            if "機構估稅後EPS" in td.get_text():
                val = td.find_next_sibling('td')
                if val: eps = safe_float(val.get_text())
                break
        return {"eps": eps, "rev_yoy": rev_yoy or 0}
    except:
        return None

# --- Streamlit 介面 ---
st.title("🚀 2026 終極監控系統")
st.markdown("### 【智慧 PE/PB 校準】x【全自動中文辨識】監控儀表板")

default_stocks = "2330.TW, 6789.TW, 8299.TWO, 2337.TW, 6147.TWO, 2401.TW, 8039.TW, 2485.TW, 2474.TW, 3217.TWO, 2476.TW"
user_input = st.text_input("請輸入股票代號 (用英文逗號隔開)", default_stocks)

if st.button("開始全自動全方位診斷"):
    stock_list = [s.strip().upper() for s in user_input.split(",")]
    results = []
    
    with st.spinner('正在分析標的動能與校準模型...'):
        for code in stock_list:
            symbol_short = code.split('.')[0]
            ticker = yf.Ticker(code)
            stock_name = get_stock_name(code)
            
            hist = ticker.history(period="120d")
            if hist.empty: continue

            curr_price = round(hist['Close'].iloc[-1], 2)
            period_high = round(hist['High'].max(), 2)
            drop_from_high = round(((curr_price - period_high) / period_high) * 100, 2)
            
            # 技術指標 (完全保留 MA5/10/20/60)
            ma5 = round(hist['Close'].rolling(5).mean().iloc[-1], 2)
            ma10 = round(hist['Close'].rolling(10).mean().iloc[-1], 2)
            ma20 = round(hist['Close'].rolling(20).mean().iloc[-1], 2)
            ma60 = round(hist['Close'].rolling(60).mean().iloc[-1], 2)
            is_all_up = curr_price > ma5 > ma10 > ma20 > ma60
            bias_5 = round(((curr_price - ma5) / ma5) * 100, 2)
            
            data = get_peicheng_index_data(symbol_short)
            if not data or data['eps'] is None: continue

            # === 智慧 PE 與目標價校準邏輯 (加入負值 PB 處理) ===
            # 先處理動態 PE，避免除以 0
            if data['eps'] > 0:
                dynamic_pe = round(curr_price / data['eps'], 2)
                f_pe = ticker.info.get("forwardPE")
                
                # 優先參考法人預估，若無或數據離譜，則動態校準
                if f_pe and 5 < f_pe < 80:
                    pred_pe = round(f_pe, 2)
                else:
                    if dynamic_pe > 40:
                        pred_pe = round(dynamic_pe * 0.95, 2)
                    elif data['rev_yoy'] > 20:
                        pred_pe = 25.0
                    else:
                        pred_pe = 18.0
                
                target_price = round(data['eps'] * pred_pe, 2)
                pe_pb_label = pred_pe
            else:
                # 虧損轉機股邏輯 (凌陽適用)：改用 P/B 比推算
                dynamic_pe = "虧損"
                book_value = ticker.info.get('bookValue')
                
                if book_value and book_value > 0:
                    # 營收成長給 1.5 倍，否則給 1.2 倍
                    pb_multiplier = 1.5 if data['rev_yoy'] > 15 else 1.2
                    target_price = round(book_value * pb_multiplier, 2)
                    pe_pb_label = f"PB:{pb_multiplier}"
                else:
                    target_price = "需財報支持"
                    pe_pb_label = "N/A"

            # === 抓鬼診斷 4.0 ===
            if drop_from_high < -20 and data['rev_yoy'] > 50: ghost_check = "⚠️重鬼(利多崩跌)"
            elif bias_5 > 10: ghost_check = "🧨超速(乖離過大)" 
            elif drop_from_high > -5 and is_all_up: ghost_check = "✅強勢(大戶鎖籌)"
            elif is_all_up and data['rev_yoy'] > 20: ghost_check = "✅沒鬼(多頭發動)"
            else: ghost_check = "正常"

            # === 進化診斷 ===
            if is_all_up and data['rev_yoy'] > 30: diagnosis = "🔥全線啟動"
            elif data['eps'] <= 0 and data['rev_yoy'] > 10: diagnosis = "🚀轉機啟動"
            elif curr_price < ma60 and data['rev_yoy'] > 100: diagnosis = "💎明珠蒙塵"
            else: diagnosis = "觀察等待"

            results.append({
                "名稱": f"{stock_name} ({symbol_short})",
                "最新價": curr_price,
                "波段高點": period_high,
                "高點回檔": f"{drop_from_high}%",
                "累計年增": f"{data['rev_yoy']}%",
                "動態PE": dynamic_pe,
                "預估PE/PB": pe_pb_label,
                "推算目標": target_price,
                "5日乖離": f"{bias_5}%",
                "站上線": "🌕是" if is_all_up else "🌑否",
                "進化診斷": diagnosis,
                "有沒有鬼": ghost_check
            })

    if results:
        st.dataframe(pd.DataFrame(results), use_container_width=True)
