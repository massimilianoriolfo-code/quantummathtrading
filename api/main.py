import math
import yfinance as yf
from flask import Flask, request, jsonify

def handler(request):
    request_json = request.get_json(silent=True)
    ticker = request_json.get('ticker', 'SPY')
    
    stock = yf.Ticker(ticker)
    price = stock.history(period="1d")['Close'].iloc[-1]
    iv = 0.20 # Volatilità standard di test
    
    move = price * iv * math.sqrt(30 / 365)
    
    return jsonify({
        "price": round(price, 2),
        "high": round(price + move, 2),
        "low": round(price - move, 2)
    })
