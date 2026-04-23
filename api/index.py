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

# Funzione con memoria (Cache) - Salva il dato per 1 ora
@lru_cache(maxsize=128)
def get_institutional_iv(ticker, hour_block):
    try:
        # Tenta Alpha Vantage (Dato Professionale)
        url = f"https://www.alphavantage.co/query?function=IMPLIED_VOLATILITY&symbol={ticker}&apikey={API_KEY}"
        res = requests.get(url, timeout=5).json()
        if "data" in res and res["data"]:
            iv = float(res["data"][0]["implied_volatility"])
            if iv > 0.05: return iv
    except:
        pass
    return None

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    t = (request.get_json(silent=True) or {}).get('ticker') or request.args.get('ticker')
    if not t: return jsonify({"error": "Inserisci Ticker"}), 400
    ticker = t.upper()

    try:
        # 1. Prezzo Last (Sempre in tempo reale da yfinance, che è gratis e senza limiti)
        stock = yf.Ticker(ticker)
        current_price = stock.fast_info['last_price']
        
        # 2. Volatilità (Dalla memoria se cercata nell'ultima ora)
        hour_block = int(time.time() / 3600)
        iv_reale = get_institutional_iv(ticker, hour_block)

        # 3. Fallback se l'API è bloccata o il dato è assente
        if not iv_reale:
            # Calcolo istantaneo dalla Option Chain
            chain = stock.option_chain(stock.options[0])
            c_iv = chain.calls.iloc[(chain.calls['strike'] - current_price).abs().idxmin()]['impliedVolatility']
            p_iv = chain.puts.iloc[(chain.puts['strike'] - current_price).abs().idxmin()]['impliedVolatility']
            iv_reale = (c_iv + p_iv) / 2

        # 4. Calcolo Expected Move (1σ)
        move = current_price * iv_reale * np.sqrt(30 / 365)
        
        return jsonify({
            "ticker": ticker,
            "price": round(current_price, 2),
            "volatility": round(iv_reale * 100, 2),
            "high": round(current_price + move, 2),
            "low": round(current_price - move, 2)
        })
    except:
        return jsonify({"error": "Dati non disponibili"}), 500

handler = app
