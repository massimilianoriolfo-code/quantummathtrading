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
        
        # Prezzo Last
        fast = stock.fast_info
        current_price = fast['last_price']
        
        # Prova a prendere la IV dal sommario (la più precisa per il tuo 32.7%)
        # Se non esiste, usiamo la volatilità storica a 52 settimane come backup
        iv_reale = stock.info.get('impliedVolatility')
        
        if iv_reale is None or iv_reale == 0:
            iv_reale = stock.info.get('fiftyTwoWeekVolatility')
            
        if iv_reale is None:
            # Ultima spiaggia: calcolo dai dati storici recenti
            hist = stock.history(period="1mo")
            log_returns = np.log(hist['Close'] / hist['Close'].shift(1))
            iv_reale = log_returns.std() * np.sqrt(252)

        # Calcolo Expected Move a 30gg (Formula del tuo libro)
        days = 30
        move = current_price * iv_reale * np.sqrt(days / 365)
        
        return jsonify({
            "ticker": ticker_symbol,
            "price": round(current_price, 2),
            "volatility": round(iv_reale * 100, 2),
            "high": round(current_price + move, 2),
            "low": round(current_price - move, 2),
            "message": "Dati aggiornati in tempo reale"
        })

    except Exception as e:
        return jsonify({"error": "Servizio momentaneamente occupato. Riprova."}), 500

handler = app
