import yfinance as yf
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    t = (request.get_json(silent=True) or {}).get('ticker') or request.args.get('ticker')
    if not t: return jsonify({"error": "Ticker mancante"}), 400
    ticker = t.upper()

    try:
        stock = yf.Ticker(ticker)
        # Prezzo Last
        price = stock.fast_info['last_price']
        
        # 1. CALCOLO VOLATILITÀ REALE (Infallibile)
        # Invece di fidarci di IV esterne che danno 0.39%, calcoliamo la volatilità 
        # reale dei prezzi dell'ultimo mese. È un dato solido e professionale.
        hist = stock.history(period="1mo")
        if len(hist) < 10:
             return jsonify({"error": "Dati storici insufficienti"}), 400
             
        log_returns = np.log(hist['Close'] / hist['Close'].shift(1))
        vol_annua = log_returns.std() * np.sqrt(252)

        # 2. SE DISPONIBILE, USA LA IV DELLE OPZIONI COME FILTRO
        try:
            chain = stock.option_chain(stock.options[0])
            idx = (chain.calls['strike'] - price).abs().idxmin()
            iv_market = chain.calls.loc[idx, 'impliedVolatility']
            # Se la IV delle opzioni è sensata, facciamo una media, altrimenti usiamo la storica
            if 0.10 < iv_market < 1.20:
                vol_finale = (vol_annua + iv_market) / 2
            else:
                vol_finale = vol_annua
        except:
            vol_finale = vol_annua

        # 3. CALCOLO RANGE ATTESO (1 Sigma - 30gg)
        move = price * vol_finale * np.sqrt(30 / 365)
        
        return jsonify({
            "ticker": ticker,
            "price": round(price, 2),
            "volatility": round(vol_finale * 100, 2),
            "high": round(price + move, 2),
            "low": round(price - move, 2)
        })
    except Exception:
        return jsonify({"error": "Errore nel calcolo dei dati"}), 500

handler = app
