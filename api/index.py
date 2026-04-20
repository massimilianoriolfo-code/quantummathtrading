import requests
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# CHIAVE ALPHA VANTAGE
API_KEY = "T8R94SXCQZ4GS6UC"

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    t = (request.get_json(silent=True) or {}).get('ticker') or request.args.get('ticker')
    if not t: return jsonify({"error": "Inserisci un Ticker"}), 400
    ticker = t.upper()

    try:
        # 1. Prezzo (Global Quote)
        p_res = requests.get(f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={API_KEY}").json()
        if "Global Quote" not in p_res or not p_res["Global Quote"]:
            return jsonify({"error": "Ticker non trovato o limite API raggiunto"}), 400
        
        current_price = float(p_res['Global Quote']['05. price'])

        # 2. Volatilità Implicita Real-Time (IV30)
        # Usiamo la funzione specifica per avere il dato di Interactive Brokers / MarketChameleon
        iv_url = f"https://www.alphavantage.co/query?function=IMPLIED_VOLATILITY&symbol={ticker}&apikey={API_KEY}"
        iv_res = requests.get(iv_url).json()
        
        if "data" not in iv_res or not iv_res["data"]:
            return jsonify({"error": f"Dati IV non disponibili per {ticker}"}), 400
            
        # Prendiamo il primo dato della lista (il più recente)
        iv_reale = float(iv_res['data'][0]['implied_volatility'])

        # 3. Calcolo Expected Move 30gg (1σ)
        # EM = Prezzo * IV * radice(30/365)
        move = current_price * iv_reale * np.sqrt(30 / 365)
        
        return jsonify({
            "ticker": ticker,
            "price": round(current_price, 2),
            "volatility": round(iv_reale * 100, 2),
            "high": round(current_price + move, 2),
            "low": round(current_price - move, 2)
        })
    except Exception as e:
        return jsonify({"error": "Errore: Limite API Alpha Vantage (5 chiamate al minuto)"}), 500

handler = app
