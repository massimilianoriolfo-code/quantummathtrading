import yfinance as yf
import json

def handler(request):
    if request.method == 'OPTIONS':
        return ('', 204, {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Content-Type'})

    try:
        data = request.get_json(silent=True) or {}
        ticker = data.get('ticker', 'SPY').upper()
        
        stock = yf.Ticker(ticker)
        price = stock.history(period="1d")['Close'].iloc[-1]
        
        # Calcolo rapido move (IV 20%)
        move = price * 0.20 * (30/365)**0.5
        
        res = {
            "price": round(price, 2),
            "high": round(price + move, 2),
            "low": round(price - move, 2)
        }
        return (json.dumps(res), 200, {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'})
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500, {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'})
