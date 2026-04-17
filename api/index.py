import math
import yfinance as yf
import json

def handler(request):
    # Gestione CORS per evitare blocchi del browser
    if request.method == 'OPTIONS':
        return ('', 204, {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
        })

    try:
        # Recupero del ticker dai dati inviati
        request_json = request.get_json(silent=True)
        ticker = request_json.get('ticker', 'SPY').upper()

        # Download dati reali
        stock = yf.Ticker(ticker)
        df = stock.history(period="1d")

        if df.empty:
            return (json.dumps({"error": "Ticker non trovato"}), 404, {'Content-Type': 'application/json'})

        current_price = df['Close'].iloc[-1]

        # Matematica CRPM (IV standard 20% per il test)
        iv = 0.20
        move = current_price * iv * (30 / 365)**0.5

        response_data = {
            "price": round(current_price, 2),
            "high": round(current_price + move, 2),
            "low": round(current_price - move, 2)
        }

       # Questo dice al browser: "Mostra i numeri, non scaricare il file"
        return (json.dumps(response_data), 200, {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        })

    except Exception as e:
        return (json.dumps({"error": str(e)}), 500, {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        })
