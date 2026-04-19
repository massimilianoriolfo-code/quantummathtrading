import yfinance as yf
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    ticker_symbol = (request.get_json(silent=True) or {}).get('ticker') or request.args.get('ticker')
    if not ticker_symbol: return jsonify({"error": "Ticker mancante"}), 400

    try:
        stock = yf.Ticker(ticker_symbol.upper())
        current_price = stock.fast_info['last_price']
        
        # Calcolo IV ATM reale (Media Call/Put strike più vicino)
        options = stock.option_chain(stock.options[0])
        calls, puts = options.calls, options.puts
        
        strike_call = calls.loc[(calls['strike'] - current_price).abs().idxmin()]
        strike_put = puts.loc[(puts['strike'] - current_price).abs().idxmin()]
        
        # Questa è la IV reale di mercato
        iv_reale = (strike_call['impliedVolatility'] + strike_put['impliedVolatility']) / 2
        
        # Limite di sicurezza
        if iv_reale > 1.2 or iv_reale < 0.05:
            iv_reale = stock.info.get('impliedVolatility', 0.32)

        move = current_price * iv_reale * np.sqrt(30 / 365)
        
        return jsonify({
            "ticker": ticker_symbol.upper(),
            "price": round(current_price, 2),
            "volatility": round(iv_reale * 100, 2),
            "high": round(current_price + move, 2),
            "low": round(current_price - move, 2)
        })
    except:
        return jsonify({"error": "Dati non disponibili"}), 500

handler = app
