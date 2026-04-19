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
        
        # 1. Prezzo Last (Veloce)
        current_price = stock.fast_info['last_price']
        
        # 2. RECUPERO IV PROFESSIONALE
        # Prendiamo direttamente il dato del sommario che Yahoo calcola come media 30gg
        info = stock.info
        iv_reale = info.get('impliedVolatility')

        # Se il campo sopra è vuoto (succede su alcuni ticker), 
        # prendiamo la IV della prima opzione ATM disponibile
        if not iv_reale or iv_reale < 0.05:
            try:
                # Accediamo alla catena opzioni
                opt = stock.option_chain(stock.options[0])
                # Media IV delle prime 5 Call ATM per stabilità
                iv_reale = opt.calls.iloc[0:5]['impliedVolatility'].mean()
            except:
                # Ultimo fallback se tutto fallisce
                iv_reale = info.get('fiftyTwoWeekVolatility', 0)

        # 3. Formula Expected Move (1 Deviazione Standard - 30gg)
        # EM = Prezzo * IV * sqrt(30 / 365)
        move = current_price * iv_reale * np.sqrt(30 / 365)
        
        return jsonify({
            "ticker": ticker_symbol,
            "price": round(current_price, 2),
            "volatility": round(iv_reale * 100, 2), # Qui NVDA deve segnare circa 32.7%
            "high": round(current_price + move, 2),
            "low": round(current_price - move, 2)
        })

    except Exception as e:
        return jsonify({"error": "Dati non disponibili. Riprova."}), 500

handler = app
