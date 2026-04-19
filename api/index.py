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
        current_price = stock.fast_info['last_price']
        
        # Estrazione diretta IV30 filtrata
        iv_raw = stock.info.get('impliedVolatility')

        # Filtro di validità: se assente o fuori scala (>150%), usa la volatilità storica 30gg
        if iv_raw is None or iv_raw > 1.5 or iv_raw < 0.05:
            hist = stock.history(period="1mo")
            log_returns = np.log(hist['Close'] / hist['Close'].shift(1))
            iv_reale = log_returns.std() * np.sqrt(252)
        else:
            iv_reale = iv_raw

        # Formula Expected Move 30gg
        move = current_price * iv_reale * np.sqrt(30 / 365)
        
        return jsonify({
            "ticker": ticker_symbol,
            "price": round(current_price, 2),
            "volatility": round(iv_reale * 100, 2),
            "high": round(current_price + move, 2),
            "low": round(current_price - move, 2)
        })

    except Exception as e:
        return jsonify({"error": "Errore tecnico dati"}), 500

handler = app
