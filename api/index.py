import yfinance as yf
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    t = (request.get_json(silent=True) or {}).get('ticker') or request.args.get('ticker')
    if not t: return jsonify({"error": "Ticker mancante"}), 400
    ticker = t.upper()

    try:
        stock = yf.Ticker(ticker)
        # 1. Prezzo attuale
        price = stock.fast_info['last_price']
        
        # 2. Trova la scadenza più vicina ai 30 giorni
        target_date = datetime.now() + timedelta(days=30)
        expirations = stock.options
        # Seleziona la data che minimizza la distanza dai 30gg
        closest_exp = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target_date).days))
        
        # 3. Scarica la catena delle opzioni per quella data
        opt_chain = stock.option_chain(closest_exp)
        calls = opt_chain.calls
        puts = opt_chain.puts
        
        # 4. Trova l'opzione ATM (At-The-Money)
        # Cerchiamo lo strike più vicino al prezzo attuale
        idx_c = (calls['strike'] - price).abs().idxmin()
        idx_p = (puts['strike'] - price).abs().idxmin()
        
        iv_call = calls.loc[idx_c, 'impliedVolatility']
        iv_put = puts.loc[idx_p, 'impliedVolatility']
        
        # La IV finale è la media delle due ATM (Standard professionale)
        iv_reale = (iv_call + iv_put) / 2

        # 5. Calcolo Expected Move 30gg (1σ)
        move = price * iv_reale * np.sqrt(30 / 365)
        
        return jsonify({
            "ticker": ticker,
            "price": round(price, 2),
            "volatility": round(iv_reale * 100, 2),
            "high": round(price + move, 2),
            "low": round(price - move, 2),
            "expiration_used": closest_exp
        })
    except Exception as e:
        return jsonify({"error": "Dati opzioni non disponibili per questo ticker"}), 500

handler = app
