import math
import yfinance as yf
import json

def handler(request):
    # Gestione semplice senza Flask per massima compatibilità
    try:
        if request.method == 'POST':
            request_json = request.get_json(silent=True)
            ticker = request_json.get('ticker', 'SPY').upper()
            
            stock = yf.Ticker(ticker)
            price = stock.history(period="1d")['Close'].iloc[-1]
            iv = 0.20
            move = price * iv * math.sqrt(30 / 365)
            
            return (json.dumps({
                "price": round(price, 2),
                "high": round(price + move, 2),
                "low": round(price - move, 2)
            }), 200, {'Content-Type': 'application/json'})
        else:
            return ("Metodo non consentito", 405)
    except Exception as e:
        return (json.dumps({"error": str(e)}), 500, {'Content-Type': 'application/json'})
