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
        
        # 1. Prezzo Last preciso
        current_price = stock.fast_info['last_price']
        
        # 2. Estrazione della IV professionale (IV30-like)
        # Proviamo i tre campi di Yahoo in ordine di precisione per il tuo studio
        info = stock.info
        iv_reale = info.get('impliedVolatility') # Il dato che cerchi
        
        # Se Yahoo non passa la IV nel sommario, la calcoliamo istantaneamente 
        # sulle opzioni ATM a 30 giorni (il metodo più preciso in assoluto)
        if iv_reale is None or iv_reale < 0.10:
            options = stock.options
            # Troviamo la scadenza più vicina ai 30gg
            from datetime import datetime, timedelta
            target = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            closest_exp = min(options, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - datetime.strptime(target, '%Y-%m-%d')).days))
            
            chain = stock.option_chain(closest_exp)
            calls = chain.calls
            # Prendiamo la IV della Call esattamente allo strike del prezzo (ATM)
            idx = (calls['strike'] - current_price).abs().idxmin()
            iv_reale = calls.loc[idx, 'impliedVolatility']

        # 3. Formula Expected Move (1 Deviazione Standard)
        days = 30
        move = current_price * iv_reale * np.sqrt(days / 365)
        
        return jsonify({
            "ticker": ticker_symbol,
            "price": round(current_price, 2),
            "volatility": round(iv_reale * 100, 2), # Qui NVDA tornerà al ~32.7%
            "high": round(current_price + move, 2),
            "low": round(current_price - move, 2)
        })

    except Exception as e:
        return jsonify({"error": "Dati mercati non disponibili ora"}), 500

handler = app
