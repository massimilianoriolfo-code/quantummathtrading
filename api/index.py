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

    try:
        stock = yf.Ticker(t.upper())
        price = stock.fast_info['last_price']
        
        # 1. Identifica la scadenza mensile a ~30gg (Standard IV30)
        target = datetime.now() + timedelta(days=30)
        exps = stock.options
        closest_exp = min(exps, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target).days))
        
        # 2. Estrazione IV ATM (Media Bid/Ask IV di Call e Put allo strike più vicino)
        chain = stock.option_chain(closest_exp)
        c = chain.calls.iloc[(chain.calls['strike'] - price).abs().idxmin()]
        p = chain.puts.iloc[(chain.puts['strike'] - price).abs().idxmin()]
        
        iv_reale = (c['impliedVolatility'] + p['impliedVolatility']) / 2
        
        # 3. Filtro di stabilità se i dati delle opzioni sono frammentati
        if iv_reale < 0.05 or iv_reale > 1.2:
            iv_reale = stock.info.get('impliedVolatility', 0.32)

        # 4. Calcolo Expected Move (1σ)
        move = price * iv_reale * np.sqrt(30 / 365)
        
        return jsonify({
            "ticker": t.upper(),
            "price": round(price, 2),
            "volatility": round(iv_reale * 100, 2),
            "high": round(price + move, 2),
            "low": round(price - move, 2)
        })
    except:
        return jsonify({"error": "Dati non disponibili"}), 500

handler = app
