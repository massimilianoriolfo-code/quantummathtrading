import requests
import numpy as np
import yfinance as yf
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import lru_cache
import timimport requests
import numpy as np
import yfinance as yf
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import lru_cache
import time

app = Flask(__name__)
CORS(app)

API_KEY = "T8R94SXCQZ4GS6UC"

def get_fallback_iv(stock):
    """Calcolo statistico se le API falliscono o danno dati folli"""
    hist = stock.history(period="1mo")
    if len(hist) < 2: return 0.30 # Default prudenziale
    log_returns = np.log(hist['Close'] / hist['Close'].shift(1))
    return log_returns.std() * np.sqrt(252)

@lru_cache(maxsize=128)
def fetch_iv_data(ticker, hour_block):
    """Tenta Alpha Vantage, poi Option Chain, poi Statistica"""
    try:
        # 1. Alpha Vantage IV30
        url = f"https://www.alphavantage.co/query?function=IMPLIED_VOLATILITY&symbol={ticker}&apikey={API_KEY}"
        res = requests.get(url, timeout=3).json()
        iv = float(res['data'][0]['implied_volatility'])
        if iv > 0.05: return iv
    except:
        pass
    
    try:
        # 2. Yahoo Option Chain ATM
        s = yf.Ticker(ticker)
        price = s.fast_info['last_price']
        chain = s.option_chain(s.options[0])
        c_iv = chain.calls.iloc[(chain.calls['strike'] - price).abs().idxmin()]['impliedVolatility']
        p_iv = chain.puts.iloc[(chain.puts['strike'] - price).abs().idxmin()]['impliedVolatility']
        iv = (c_iv + p_iv) / 2
        if iv > 0.05: return iv
    except:
        pass
        
    # 3. Fallback Statistico (Infallibile)
    return get_fallback_iv(yf.Ticker(ticker))

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    t = (request.get_json(silent=True) or {}).get('ticker') or request.args.get('ticker')
    if not t: return jsonify({"error": "Ticker mancante"}), 400
    ticker = t.upper()

    try:
        stock = yf.Ticker(ticker)
        current_price = stock.fast_info['last_price']
        
        # Cache oraria per evitare blocchi API
        hour_block = int(time.time() / 3600)
        iv_final = fetch_iv_data(ticker, hour_block)

        # Expected Move 30gg (1 Sigma)
        move = current_price * iv_final * np.sqrt(30 / 365)
        
        return jsonify({
            "ticker": ticker,
            "price": round(current_price, 2),
            "volatility": round(iv_final * 100, 2),
            "high": round(current_price + move, 2),
            "low": round(current_price - move, 2),
            "status": "Premium Data"
        })
    except Exception as e:
        return jsonify({"error": "Inserire un ticker valido"}), 500

handler = app
