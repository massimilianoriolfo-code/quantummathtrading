import yfinance as yf
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        ticker_symbol = (data.get('ticker') or "").upper()
    else:
        ticker_symbol = (request.args.get('ticker') or "").upper()

    if not ticker_symbol:
        return jsonify({"error": "Ticker mancante"}), 400

    try:
        stock = yf.Ticker(ticker_symbol)
        
        # Prezzo Last
        current_price = stock.fast_info['last_price']
        
        # Recupero IV30 (Standard Professionale)
        # Se Yahoo fornisce il dato nel sommario lo prendiamo, altrimenti calcolo rapido ATM
        iv_reale = stock.info.get('impliedVolatility')

        # Filtro di sicurezza per evitare errori come il 393% o lo 0%
        if iv_reale is None or iv_reale > 1.5 or iv_reale < 0.05:
            # Fallback su volatilità storica 30gg (più stabile e veritiera)
            hist = stock.history(period="1mo")
            log_returns = np.log(hist['Close'] / hist['Close'].shift(1))
            iv_reale = log_returns.std() * np.sqrt(252)

        # Formula Expected Move (1σ - 30gg)
        move = current_price * iv_reale * np.sqrt(30 / 365)
        
        return jsonify({
            "ticker": ticker_symbol,
            "price": round(current_price, 2),
            "volatility": round(iv_reale * 100, 2),
            "high": round(current_price + move, 2),
            "low": round(current_price - move, 2)
        })

    except Exception:
        return jsonify({"error": "Errore caricamento dati"}), 500

handler = app
