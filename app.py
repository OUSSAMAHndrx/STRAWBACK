import streamlit as st
import subprocess
import os

st.set_page_config(page_title="Quant Control Center", layout="wide")

st.title("📈 Quant Control Center")
st.markdown("Automatically generate, update, and execute your backtesting infrastructure.")

# --- TABS ---
tab1, tab2 = st.tabs(["📥 Data Downloader", "⚙️ Strategy Builder"])

# ==========================================
# TAB 1: DATA DOWNLOADER UI
# ==========================================
with tab1:
    st.header("Configure Historical Data")
    
    col1, col2 = st.columns(2)
    with col1:
        api_key = st.text_input("OANDA API Key (Practice)", type="password")
        symbol = st.selectbox("Trading Pair", ["XAU_USD", "EUR_USD", "GBP_USD", "USD_JPY", "BTC_USD"])
    with col2:
        timeframe_1 = st.selectbox("Primary Timeframe (Trend)", ["H1", "H4", "D"])
        timeframe_2 = st.selectbox("Execution Timeframe (Trigger)", ["M15", "M5", "M1"])
        candles = st.number_input("Number of Candles to Fetch (Max 75000)", min_value=1000, max_value=100000, value=20000, step=1000)

    if st.button("Generate & Download Data", type="primary"):
        if not api_key:
            st.error("Please enter your API Key!")
        else:
            with st.spinner(f"Generating script and pulling {candles} candles for {symbol}..."):
                # 1. Generate the download_data.py script dynamically
                download_script = f"""import pandas as pd
import time
from oandapyV20 import API
import oandapyV20.endpoints.instruments as instruments

client = API(access_token="{api_key}", environment="practice")

def fetch_data(symbol, tf, target):
    all_candles = []
    last_time = None
    batches = (target // 5000) + 1
    
    print(f"Downloading {{symbol}} {{tf}}...")
    for i in range(batches):
        params = {{"count": 5000, "granularity": tf, "price": "M"}}
        if last_time: params["to"] = last_time
        
        try:
            r = instruments.InstrumentsCandles(instrument=symbol, params=params)
            client.request(r)
            candles = r.response.get('candles', [])
            if not candles: break
            
            batch_data = [{{'time': c['time'][:19].replace('T', ' '), 'open': float(c['mid']['o']), 'high': float(c['mid']['h']), 'low': float(c['mid']['l']), 'close': float(c['mid']['c']), 'volume': int(c['volume'])}} for c in candles if c['complete']]
            
            if not batch_data: break
            last_time = candles[0]['time']
            all_candles = batch_data + all_candles
            time.sleep(0.5)
        except Exception as e:
            print(f"Error: {{e}}")
            break

    if all_candles:
        df = pd.DataFrame(all_candles)
        df.drop_duplicates(subset=['time'], inplace=True)
        df.sort_values('time', inplace=True)
        clean_tf = tf.replace('M15', '15m').replace('M5', '5m').replace('M1', '1m').replace('H1', '1H').replace('H4', '4H')
        df.to_csv(f"{{symbol.replace('_', '')}}_{{clean_tf}}.csv", index=False)
        print(f"Saved {{len(df)}} rows for {{tf}}.")

fetch_data("{symbol}", "{timeframe_1}", {candles})
fetch_data("{symbol}", "{timeframe_2}", {candles})
"""
                # Write to file with UTF-8 encoding
                with open("download_data.py", "w", encoding="utf-8") as f:
                    f.write(download_script)
                
                # Execute the file and capture output
                result = subprocess.run(["python", "download_data.py"], capture_output=True, text=True)
                
                if result.returncode == 0:
                    st.success("Data Downloaded Successfully!")
                    st.code(result.stdout, language="text")
                else:
                    st.error("Script failed.")
                    st.code(result.stderr, language="text")

# ==========================================
# TAB 2: STRATEGY BUILDER UI
# ==========================================
with tab2:
    st.header("Strategy Editor")
    st.markdown("Write or paste your `main.py` code here. Clicking run will overwrite the file and execute it.")
    
    # Try to load existing main.py if it exists to populate the text area
    default_code = "# Paste your Backtrader code here..."
    if os.path.exists("main.py"):
        # Read with UTF-8 encoding to prevent Windows charmap errors
        with open("main.py", "r", encoding="utf-8") as f:
            default_code = f.read()

    # The giant text box for your strategy
    strategy_code = st.text_area("main.py Code", value=default_code, height=500)
    
    if st.button("💾 Save & Run Backtest", type="primary"):
        with st.spinner("Executing Backtest..."):
            # Overwrite main.py with UTF-8 encoding
            with open("main.py", "w", encoding="utf-8") as f:
                f.write(strategy_code)
                
            # Run main.py and capture the report
            # Force subprocess to use utf-8 encoding as well
            result = subprocess.run(["python", "main.py"], capture_output=True, text=True, encoding="utf-8")
            
            # Display results
            st.subheader("Terminal Output")
            if result.returncode == 0:
                st.code(result.stdout, language="text")
            else:
                st.error("Strategy crashed! See traceback below:")
                st.code(result.stderr, language="text")