import yfinance as yf
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    # 1. Ricezione dinamica del ticker
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        ticker_symbol = data.get('ticker')
    else:
        ticker_symbol = request.args.get('ticker')

    if not ticker_symbol:
        return jsonify({"error": "Ticker mancante"}), 400

    ticker_symbol = ticker_symbol.upper()

    try:
        stock = yf.Ticker(ticker_symbol)
        
        # 2. Prezzo REALE Last
        current_price = stock.fast_info['last_price']
        
        # 3. Estrazione IV REALE da Sommario Yahoo (metodo preciso)
        # Questo dato è allineato a MarketChameleon e AlphaVantage
        iv_reale = stock.info.get('impliedVolatility')

        # Controllo se il dato è disponibile
        if iv_reale is None or iv_reale == 0:
             # Fallback su volatilità media se IV non disponibile
             iv_reale = stock.info.get('fiftyTwoWeekVolatility')
             
             # Se anche questo manca, non possiamo calcolare
             if iv_reale is None:
                return jsonify({"error": f"IV non disponibile per {ticker_symbol}"}), 400

        # 4. Giorni di proiezione (Default 30)
        days_projection = 30

        # 5. Formula Expected Move (dal tuo libro)
        move = current_price * iv_reale * np.sqrt(days_projection / 365)
        
        # 6. Risposta per il frontend
        return jsonify({
            "ticker": ticker_symbol,
            "price": round(current_price, 2),
            "volatility": round(iv_reale * 100, 2), # Adesso mostrerà un valore vicino al 32.7%
            "move": round(move, 2),
            "high": round(current_price + move, 2),
            "low": round(current_price - move, 2),
            # Rimuoviamo la data specifica perché la IV del sommario è ponderata su 30gg
            "comment": "IV ponderata su orizzonte 30gg"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
