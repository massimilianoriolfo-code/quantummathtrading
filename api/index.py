import yfinance as yf
import pandas as pd
import json

def handler(request):
    # Risposta per il browser (CORS)
    if request.method == 'OPTIONS':
        return ('', 204, {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        })

    try:
        # Carica il ticker
        payload = request.get_json(silent=True) or {}
        ticker = payload.get('ticker', 'SPY').upper()
        
        # Scarica dati
        stock = yf.Ticker(ticker)
        df = stock.history(period="1d")
        
        if df.empty:
            return (json.dumps({"error": "Ticker non trovato"}), 404, {'Content-Type': 'application/json'})

        price = float(df['Close'].iloc[-1])
        # Formula CRPM
        move = price * 0.20 * (30/365)**0.5
        
        res = {
            "price": round(price, 2),
            "high": round(price + move, 2),
            "low": round(price - move, 2)
        }
        
        return (json.dumps(res), 200, {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        })

    except Exception as e:
        return (json.dumps({"error": str(e)}), 500, {'Content-Type': 'application/json'})
