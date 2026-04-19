import yfinance as yf
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    # 1. Ricezione dinamica dei dati (Ticker e Giorni)
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        ticker_symbol = data.get('ticker')
        days_projection = int(data.get('days', 30))
    else:
        ticker_symbol = request.args.get('ticker')
        days_projection = int(request.args.get('days', 30))

    if not ticker_symbol:
        return jsonify({"error": "Inserire un ticker valido"}), 400

    try:
        stock = yf.Ticker(ticker_symbol.upper())
        
        # 2. Prezzo Last Reale (estratto direttamente dai dati veloci)
        current_price = stock.fast_info['last_price']
        
        # 3. Ricerca Scadenza Opzioni ~30gg per estrarre la IV reale
        expirations = stock.options
        if not expirations:
            return jsonify({"error": "Opzioni non disponibili per questo ticker"}), 400
            
        target_date = datetime.now() + timedelta(days=30)
        closest_exp = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target_date).days))
        
        # 4. Estrazione IV ATM (Media Call/Put per precisione millimetrica)
        opt_chain = stock.option_chain(closest_exp)
        calls = opt_chain.calls
        puts = opt_chain.puts
        
        # Trova lo strike più vicino al prezzo attuale (ATM)
        idx_call = (calls['strike'] - current_price).abs().idxmin()
        idx_put = (puts['strike'] - current_price).abs().idxmin()
        
        iv_call = calls.loc[idx_call, 'impliedVolatility']
        iv_put = puts.loc[idx_put, 'impliedVolatility']
        
        # Media della volatilità implicita (il dato univoco che vedi su Yahoo)
        iv_reale = (iv_call + iv_put) / 2

        # 5. Formula Expected Move (dal tuo libro)
        # EM = Prezzo * IV * sqrt(Giorni / 365)
        move = current_price * iv_reale * np.sqrt(days_projection / 365)
        
        return jsonify({
            "ticker": ticker_symbol.upper(),
            "price": round(current_price, 2),
            "volatility": round(iv_reale * 100, 2),
            "days": days_projection,
            "move": round(move, 2),
            "high": round(current_price + move, 2),
            "low": round(current_price - move, 2),
            "expiry_used": closest_exp
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Fondamentale per Vercel
handler = app
