import yfinance as yf
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        ticker_symbol = data.get('ticker')
        days_projection = int(data.get('days', 30))
    else:
        ticker_symbol = request.args.get('ticker')
        days_projection = int(request.args.get('days', 30))

    if not ticker_symbol:
        return jsonify({"error": "Ticker mancante"}), 400

    try:
        stock = yf.Ticker(ticker_symbol.upper())
        # Prezzo Last preciso
        current_price = stock.fast_info['last_price']
        
        # Selezione scadenza corretta (circa 30gg)
        expirations = stock.options
        target_date = datetime.now() + timedelta(days=days_projection)
        closest_exp = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target_date).days))
        
        opt_chain = stock.option_chain(closest_exp)
        
        # FILTRO ATM: Cerchiamo lo strike più vicino al prezzo attuale
        calls = opt_chain.calls
        puts = opt_chain.puts
        
        # Troviamo l'indice dello strike ATM
        idx_call = (calls['strike'] - current_price).abs().idxmin()
        idx_put = (puts['strike'] - current_price).abs().idxmin()
        
        iv_call = calls.loc[idx_call, 'impliedVolatility']
        iv_put = puts.loc[idx_put, 'impliedVolatility']
        
        # MEDIA PONDERATA: La IV reale ATM è la media tra Call e Put
        iv_reale = (iv_call + iv_put) / 2
        
        # Se la IV estratta è chiaramente un errore (es. > 200% o 0), 
        # yfinance a volte ha buchi nei dati.
        if iv_reale < 0.05 or iv_reale > 2.5:
             # Fallback su un dato più stabile se il calcolo ATM fallisce
             iv_reale = stock.info.get('impliedVolatility', iv_reale)

        # Formula Expected Move
        move = current_price * iv_reale * np.sqrt(days_projection / 365)
        
        return jsonify({
            "ticker": ticker_symbol.upper(),
            "price": round(current_price, 2),
            "volatility": round(iv_reale * 100, 2),
            "expiry_used": closest_exp,
            "high": round(current_price + move, 2),
            "low": round(current_price - move, 2)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
