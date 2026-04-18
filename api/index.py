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
        # Recupero ticker
        data = request.get_json(silent=True) or {}
        ticker = data.get('ticker', 'SPY').upper()
        
        # Sourcing
        stock = yf.Ticker(ticker)
        df = stock.history(period="1d")
        
        if df.empty:
            return (json.dumps({"error": "Ticker non trovato"}), 404, headers)

        current_price = float(df['Close'].iloc[-1])
        move = current_price * 0.20 * (30/365)**0.5
        
        return (json.dumps({
            "price": round(current_price, 2),
            "high": round(current_price + move, 2),
            "low": round(current_price - move, 2)
        }), 200, headers)

    except Exception as e:
        return (json.dumps({"error": str(e)}), 500, headers)
