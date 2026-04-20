import requests
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# USA LA TUA CHIAVE REALE QUI
API_KEY = "T8R94SXCQZ4GS6UC"

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    t = (request.get_json(silent=True) or {}).get('ticker') or request.args.get('ticker')
    if not t: return jsonify({"error": "Inserisci un Ticker"}), 400
    ticker = t.upper()

    try:
        # 1. Prezzo
        p_res = requests.get(f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={API_KEY}").json()
        if "Global Quote" not in p_res or not p_res["Global Quote"]:
            return jsonify({"error": "Ticker non trovato o limite API raggiunto"}), 400
        
        current_price = float(p_res['Global Quote']['05. price'])

        # 2. Volatilità Implicita (IV)
        iv_res = requests.get(f"https://www.alphavantage.co/query?function=HISTORICAL_OPTIONS&symbol={ticker}&apikey={API_KEY}").json()
        
        # Alpha Vantage a volte cambia struttura: cerchiamo il dato iv30 o quello più recente
        # Se non disponibile, usiamo la IV calcolata da Yahoo come fallback immediato
        try:
            # Cerchiamo di estrarre la IV dall'ultimo dato disponibile
            iv_reale = float(iv_res['data'][0]['implied_volatility'])
        except:
            # Fallback se Alpha Vantage IV fallisce
            import yfinance as yf
            stock = yf.Ticker(ticker)
            iv_reale = stock.info.get('impliedVolatility', 0.27)

        # 3. Calcolo Expected Move 30gg (1σ)
        move = current_price * iv_reale * np.sqrt(30 / 365)
        
        return jsonify({
            "ticker": ticker,
            "price": round(current_price, 2),
            "volatility": round(iv_reale * 100, 2),
            "high": round(current_price + move, 2),
            "low": round(current_price - move, 2)
        })
    except Exception as e:
        return jsonify({"error": f"Errore tecnico: {str(e)}"}), 500

handler = app
