import requests
import numpy as np
import yfinance as yf
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import lru_cache
import time

app = Flask(__name__)
CORS(app)

API_KEY = "T8R94SXCQZ4GS6UC"

# Funzione per ottenere i dati con memoria (Cache) di 1 ora
@lru_cache(maxsize=100)
def get_professional_iv(ticker, timestamp):
    try:
        url = f"https://www.alphavantage.co/query?function=IMPLIED_VOLATILITY&symbol={ticker}&apikey={API_KEY}"
        res = requests.get(url, timeout=5).json()
        if "data" in res and res["data"]:
            return float(res["data"][0]["implied_volatility"])
    except:
        return None
    return None

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    t = (request.get_json(silent=True) or {}).get('ticker') or request.args.get('ticker')
    if not t: return jsonify({"error": "Ticker mancante"}), 400
    ticker = t.upper()

    try:
        stock = yf.Ticker(ticker)
        current_price = stock.fast_info['last_price']
        
        # Arrotondiamo il tempo all'ora attuale per la cache
        hour_timestamp = int(time.time() / 3600)
        
        # Tentativo 1: Alpha Vantage (Dato Professionale)
        iv_reale = get_professional_iv(ticker, hour_timestamp)

        # Tentativo 2: Calcolo ATM Reale (Se AV è bloccato o fallisce)
        if not iv_reale:
            chain = stock.option_chain(stock.options[0])
            idx_c = (chain.calls['strike'] - current_price).abs().idxmin()
            idx_p = (chain.puts['strike'] - current_price).abs().idxmin()
            iv_reale = (chain.calls.loc[idx_c, 'impliedVolatility'] + chain.puts.loc[idx_p, 'impliedVolatility']) / 2

        move = current_price * iv_reale * np.sqrt(30 / 365)
        
        return jsonify({
            "ticker": ticker,
            "price": round(current_price, 2),
            "volatility": round(iv_reale * 100, 2),
            "high": round(current_price + move, 2),
            "low": round(current_price - move, 2)
        })
    except:
        return jsonify({"error": "Servizio momentaneamente in manutenzione"}), 500

handler = app
