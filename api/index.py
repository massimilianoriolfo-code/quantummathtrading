import requests
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# INSERISCI QUI LA TUA CHIAVE ALPHA VANTAGE
API_KEY = "T8R94SXCQZ4GS6UC"

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    t = (request.get_json(silent=True) or {}).get('ticker') or request.args.get('ticker')
    if not t: return jsonify({"error": "Ticker mancante"}), 400
    
    ticker = t.upper()

    try:
        # 1. Recupero Prezzo Real-Time
        price_url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={API_KEY}"
        price_data = requests.get(price_url).json()
        current_price = float(price_data['Global Quote']['05. price'])

        # 2. Recupero IV30 Professionale (Endpoint certificato)
        iv_url = f"https://www.alphavantage.co/query?function=IMPLIED_VOLATILITY&symbol={ticker}&apikey={API_KEY}"
        iv_data = requests.get(iv_url).json()
        
        # AlphaVantage restituisce una lista di IV storiche, noi prendiamo la più recente
        # Il dato è già filtrato e ponderato a 30gg dai loro algoritmi
        iv_reale = float(iv_data['data'][0]['implied_volatility'])

        # 3. Calcolo Expected Move (1σ - 30gg) dal tuo libro
        move = current_price * iv_reale * np.sqrt(30 / 365)
        
        return jsonify({
            "ticker": ticker,
            "price": round(current_price, 2),
            "volatility": round(iv_reale * 100, 2),
            "high": round(current_price + move, 2),
            "low": round(current_price - move, 2),
            "source": "AlphaVantage Real-Time"
        })
    except Exception as e:
        return jsonify({"error": "Errore API: Verifica la chiave o il ticker"}), 500

handler = app
