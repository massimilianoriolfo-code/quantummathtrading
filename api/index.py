import requests
import numpy as np
import yfinance as yf
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_KEY = "T8R94SXCQZ4GS6UC"

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    t = (request.get_json(silent=True) or {}).get('ticker') or request.args.get('ticker')
    if not t: return jsonify({"error": "Inserisci Ticker"}), 400
    ticker = t.upper()

    try:
        stock = yf.Ticker(ticker)
        current_price = stock.fast_info['last_price']
        iv_reale = None

        # 1. TENTATIVO PROFESSIONALE (Alpha Vantage)
        try:
            url = f"https://www.alphavantage.co/query?function=IMPLIED_VOLATILITY&symbol={ticker}&apikey={API_KEY}"
            res = requests.get(url, timeout=3).json()
            if "data" in res and res["data"]:
                iv_reale = float(res["data"][0]["implied_volatility"])
        except:
            iv_reale = None

        # 2. BACKUP QUANTITATIVO (Calcolo ATM reale se AV fallisce)
        if not iv_reale:
            chain = stock.option_chain(stock.options[0])
            idx_c = (chain.calls['strike'] - current_price).abs().idxmin()
            idx_p = (chain.puts['strike'] - current_price).abs().idxmin()
            iv_reale = (chain.calls.loc[idx_c, 'impliedVolatility'] + chain.puts.loc[idx_p, 'impliedVolatility']) / 2

        # 3. CALCOLO EXPECTED MOVE
        move = current_price * iv_reale * np.sqrt(30 / 365)
        
        return jsonify({
            "ticker": ticker,
            "price": round(current_price, 2),
            "volatility": round(iv_reale * 100, 2),
            "high": round(current_price + move, 2),
            "low": round(current_price - move, 2)
        })
    except:
        return jsonify({"error": "Dati al momento non disponibili"}), 500

handler = app
