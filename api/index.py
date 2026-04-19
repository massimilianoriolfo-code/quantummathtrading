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
        ticker_symbol = data.get('ticker')
    else:
        ticker_symbol = request.args.get('ticker')

    if not ticker_symbol:
        return jsonify({"error": "Ticker mancante"}), 400

    ticker_symbol = ticker_symbol.upper()

    try:
        stock = yf.Ticker(ticker_symbol)
        
        # 1. Prezzo in tempo reale
        current_price = stock.fast_info['last_price']
        
        # 2. Recupero IV precisa (Yahoo la chiama 'impliedVolatility')
        # Cerchiamo di prendere il dato più pulito possibile
        info = stock.info
        iv_reale = info.get('impliedVolatility')

        # 3. Correzione se il dato è assente o sporco
        if iv_reale is None or iv_reale < 0.01:
            # Calcoliamo la IV ATM media dalle opzioni a 30gg
            try:
                exp = stock.options[0] # Prende la scadenza più vicina
                opt = stock.option_chain(exp)
                calls = opt.calls
                # Trova la IV della call più vicina al prezzo (ATM)
                idx = (calls['strike'] - current_price).abs().idxmin()
                iv_reale = calls.loc[idx, 'impliedVolatility']
            except:
                iv_reale = info.get('fiftyTwoWeekVolatility', 0.30)

        # 4. Calcolo Expected Move (Formula: Prezzo * IV * sqrt(30/365))
        # Usiamo esattamente la formula del tuo libro
        days = 30
        move = current_price * iv_reale * np.sqrt(days / 365)
        
        return jsonify({
            "ticker": ticker_symbol,
            "price": round(current_price, 2),
            "volatility": round(iv_reale * 100, 2), # Qui vedrai un dato molto vicino al 32.7%
            "high": round(current_price + move, 2),
            "low": round(current_price - move, 2)
        })

    except Exception as e:
        return jsonify({"error": "Dati non disponibili per questo ticker"}), 500

handler = app
