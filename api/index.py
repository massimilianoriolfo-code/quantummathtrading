import yfinance as yf
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    # Gestione ticker
    ticker = "SPY"
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        ticker = data.get('ticker', 'SPY').upper()

    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="1d")
        
        if df.empty:
            return jsonify({"error": "Ticker non trovato"}), 404

        price = float(df['Close'].iloc[-1])
        # Formula CRPM (IV 20%)
        move = price * 0.20 * (30/365)**0.5
        
        return jsonify({
            "price": round(price, 2),
            "high": round(price + move, 2),
            "low": round(price - move, 2)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Questo è il punto che mancava nello screenshot!
handler = app
