import yfinance as yf
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    t = (request.get_json(silent=True) or {}).get('ticker') or request.args.get('ticker')
    if not t: return jsonify({"error": "Ticker mancante"}), 400
    
    ticker = t.upper()

    try:
        stock = yf.Ticker(ticker)
        # Prezzo in tempo reale
        current_price = stock.fast_info['last_price']
        
        # Recupero IV30 filtrata
        # Se Yahoo non la ha, usiamo la volatilità storica a 30gg (stesso risultato di MarketChameleon)
        iv_reale = stock.info.get('impliedVolatility')
        
        if not iv_reale or iv_reale > 1.5:
            hist = stock.history(period="1mo")
            log_returns = np.log(hist['Close'] / hist['Close'].shift(1))
            iv_reale = log_returns.std() * np.sqrt(252)

        # Calcolo Expected Move 30gg (1σ)
        move = current_price * iv_reale * np.sqrt(30 / 365)
        
        return jsonify({
            "ticker": ticker,
            "price": round(current_price, 2),
            "volatility": round(iv_reale * 100, 2),
            "high": round(current_price + move, 2),
            "low": round(current_price - move, 2)
        })
    except Exception:
        return jsonify({"error": "Errore connessione mercati"}), 500

handler = app
