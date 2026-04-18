import yfinance as yf
import pandas as pd
import json

def handler(request):
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Content-Type': 'application/json'
    }

    if request.method == 'OPTIONS':
        return ('', 204, headers)

    try:
        payload = request.get_json(silent=True) or {}
        ticker = payload.get('ticker', 'SPY').upper()
        
        stock = yf.Ticker(ticker)
        df = stock.history(period="1d")
        
        if df.empty:
            return (json.dumps({"error": "Ticker non trovato"}), 404, headers)

        price = float(df['Close'].iloc[-1])
        move = price * 0.20 * (30/365)**0.5
        
        res = {
            "price": round(price, 2),
            "high": round(price + move, 2),
            "low": round(price - move, 2)
        }
        return (json.dumps(res), 200, headers)

    except Exception as e:
        return (json.dumps({"error": str(e)}), 500, headers)
