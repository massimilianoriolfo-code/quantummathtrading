import math
import yfinance as yf
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/api/main', methods=['POST'])
def handler():
    try:
        data = request.get_json(silent=True) or {}
        ticker = data.get('ticker', 'SPY').upper()
        
        # Recupero dati reali
        stock = yf.Ticker(ticker)
        price = stock.history(period="1d")['Close'].iloc[-1]
        
        # Calcolo Expected Move (IV 20% standard per ora)
        iv = 0.20
        move = price * iv * math.sqrt(30 / 365)
        
        return jsonify({
            "price": round(price, 2),
            "high": round(price + move, 2),
            "low": round(price - move, 2)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Questo serve a Vercel per esporre la funzione
def main(request):
    return handler()
