# 📈 Quant Control Center

Welcome to STRAWBACK the Quant Control Center! This is a complete, cloud-hosted backtesting laboratory built with Python, Backtrader, and Streamlit. It allows you to dynamically fetch historical forex/crypto data and test algorithmic trading strategies right in your browser.

🚀 **[Click here to launch the Live App!](https://strawback-lrkltapxfysfpl3qzprk94.streamlit.app/)**

---

## 🛠️ Features

* **Cloud Data Downloader:** Fetches up to 100,000 candles of historical market data via the OANDA API directly to the cloud server.
* **Built-in IDE:** Write, edit, and save Backtrader `main.py` strategy logic directly from the web interface.
* **Hedge-Fund Grade Reporting:** Automatically calculates advanced quantitative metrics including:
  * Sharpe Ratio & Sortino Ratio
  * Calmar Ratio (Return / Max Drawdown)
  * Profit Factor & Expectancy per Trade
  * Equity Curve Volatility

## 🔐 Security Note
This app is completely decentralized and secure. It does **not** store your OANDA API key. You must generate and provide your own Practice API key for the current session to download new data. 

## 💻 Running Locally
If you prefer to run this on your own machine instead of the cloud:

1. Clone this repository.
2. Install the requirements: `pip install -r requirements.txt`
3. Run the Streamlit server: `streamlit run app.py`
