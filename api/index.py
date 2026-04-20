import requests
import numpy as np
import yfinance as yf
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_KEY = "T8R94SXCQZ4GS6UC"

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    t = (request.get_json(silent=True) or {}).get('ticker') or request.args.get('ticker')
    if not t: return jsonify({"error": "Inserisci un Ticker"}), 400
    ticker = t.upper()

    try:
        # 1. Prezzo Last
        stock = yf.Ticker(ticker)
        current_price = stock.fast_info['last_price']

        # 2. Tentativo IV Professionale (Alpha Vantage)
        iv_reale = None
        try:
            iv_url = f"https://www.alphavantage.co/query?function=IMPLIED_VOLATILITY&symbol={ticker}&apikey={API_KEY}"
            iv_res = requests.get(iv_url, timeout=5).json()
            if "data" in iv_res and iv_res["data"]:
                iv_reale = float(iv_res["data"][0]["implied_volatility"])
        except:
            iv_reale = None

        # 3. BACKUP MATEMATICO (Se Alpha Vantage fallisce, calcoliamo la IV ATM reale)
        if not iv_reale:
            try:
                options = stock.options
                chain = stock.option_chain(options[0])
                c_iv = chain.calls.iloc[(chain.calls['strike'] - current_price).abs().idxmin()]['impliedVolatility']
                p_iv = chain.puts.iloc[(chain.puts['strike'] - current_price).abs().idxmin()]['impliedVolatility']
                iv_reale = (c_iv + p_iv) / 2
            except:
                # Ultima spiaggia: Volatilità storica 30gg (vicina alla IV30)
                hist = stock.history(period="1mo")
                log_ret = np.log(hist['Close'] / hist['Close'].shift(1))
                iv_reale = log_ret.std() * np.sqrt(252)

        # 4. Calcolo Expected Move 30gg
        move = current_price * iv_reale * np.sqrt(30 / 365)
        
        return jsonify({
            "ticker": ticker,
            "price": round(current_price, 2),
            "volatility": round(iv_reale * 100, 2),
            "high": round(current_price + move, 2),
            "low": round(current_price - move, 2)
        })
    except Exception as e:
        return jsonify({"error": "Servizio mercati occupato. Riprova."}), 500

handler = app        # 3. Calcolo Expected Move 30gg (1σ)
        # EM = Prezzo * IV * radice(30/365)
        move = current_price * iv_reale * np.sqrt(30 / 365)
        
        return jsonify({
            "ticker": ticker,
            "price": round(current_price, 2),
            "volatility": round(iv_reale * 100, 2),
            "high": round(current_price + move, 2),
            "low": round(current_price - move, 2)
        })
    except Exception as e:
        return jsonify({"error": "Errore: Limite API Alpha Vantage (5 chiamate al minuto)"}), 500

handler = app
