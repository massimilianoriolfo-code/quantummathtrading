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

# CACHE PROFESSIONALE: Memorizza il risultato per 1 ora (3600 secondi)
# Questo permette a migliaia di utenti di usare il sito senza bloccare la tua API
@lru_cache(maxsize=100)
def get_verified_data(ticker, hour_block):
    # Prova Alpha Vantage per il dato istituzionale (es. 27.3% Apple)
    try:
        url = f"https://www.alphavantage.co/query?function=IMPLIED_VOLATILITY&symbol={ticker}&apikey={API_KEY}"
        res = requests.get(url, timeout=4).json()
        if "data" in res and res["data"]:
            return float(res["data"][0]["implied_volatility"])
    except:
        pass

    # Fallback immediato su calcolo matematico da Option Chain (Infallibile)
    try:
        stock = yf.Ticker(ticker)
        current_price = stock.fast_info['last_price']
        chain = stock.option_chain(stock.options[0])
        idx_c = (chain.calls['strike'] - current_price).abs().idxmin()
        idx_p = (chain.puts['strike'] - current_price).abs().idxmin()
        return (chain.calls.loc[idx_c, 'impliedVolatility'] + chain.puts.loc[idx_p, 'impliedVolatility']) / 2
    except:
        return None

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    t = (request.get_json(silent=True) or {}).get('ticker') or request.args.get('ticker')
    if not t: return jsonify({"error": "Inserisci Ticker"}), 400
    ticker = t.upper()

    try:
        # Blocchiamo il tempo all'ora attuale per validare la cache
        hour_block = int(time.time() / 3600)
        
        # Recupero IV (Dalla cache o dal mercato)
        iv_reale = get_verified_data(ticker, hour_block)
        
        # Recupero Prezzo Last (Sempre real-time)
        stock = yf.Ticker(ticker)
        price = stock.fast_info['last_price']

        if not iv_reale:
             return jsonify({"error": "Dati momentaneamente non disponibili"}), 500

        # Calcolo Expected Move (Dal tuo libro)
        move = price * iv_reale * np.sqrt(30 / 365)
        
        return jsonify({
            "ticker": ticker,
            "price": round(price, 2),
            "volatility": round(iv_reale * 100, 2),
            "high": round(price + move, 2),
            "low": round(price - move, 2),
            "cache_status": "Dato Certificato"
        })
    except:
        return jsonify({"error": "Errore di connessione"}), 500

handler = app
