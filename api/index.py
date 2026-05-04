import yfinance as yf
import numpy as np
import requests
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

def get_now():
    return datetime(2026, 5, 4)

def find_nearest_strike(chain, target):
    strikes = chain['strike'].values
    return strikes[np.abs(strikes - target).argmin()]

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    data = request.get_json(silent=True) or {}
    t = data.get('ticker') or request.args.get('ticker')
    if not t: return jsonify({"error": "Ticker missing"}), 400
    ticker_sym = t.upper()
    today_dt = get_now()

    try:
        stock = yf.Ticker(ticker_sym)
        company_name = stock.info.get('longName', ticker_sym)
        price = round(stock.fast_info['last_price'], 2)
        invested_capital = price * 100
        
        # 1. Recupero scadenze reali
        expirations = stock.options
        if not expirations: return jsonify({"error": "No options available"}), 400

        # Scadenza 30gg (Tattica)
        target_30 = today_dt + timedelta(days=30)
        exp_30 = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target_30).days))
        
        # Scadenza 6 mesi (Strategica)
        target_180 = today_dt + timedelta(days=180)
        exp_180 = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target_180).days))

        # 2. Analisi Tattica (1-Sigma)
        iv_val = 0.27 # Utilizziamo IV media per il calcolo del cono
        move = price * iv_val * np.sqrt(30 / 365)
        high_target, low_target = price + move, price - move

        # 3. Estrazione Premi Reali per Macchine
        chain_30 = stock.option_chain(exp_30)
        chain_180 = stock.option_chain(exp_180)

        # Machine 1 & 4 (Call)
        strike_call = find_nearest_strike(chain_30.calls, high_target)
        prem_call = chain_30.calls[chain_30.calls['strike'] == strike_call]['lastPrice'].values[0]

        # Machine 2 (Put)
        strike_put_30 = find_nearest_strike(chain_30.puts, low_target)
        prem_put_30 = chain_30.puts[chain_30.puts['strike'] == strike_put_30]['lastPrice'].values[0]

        # Machine 3 (Put ITM 6 mesi)
        strike_put_180 = find_nearest_strike(chain_180.puts, price * 1.02)
        prem_put_180 = chain_180.puts[chain_180.puts['strike'] == strike_put_180]['lastPrice'].values[0]

        def fmt_pct(val): return f"{round((val / invested_capital) * 100, 2)}%"

        return jsonify({
            "ticker": ticker_sym, "company": company_name, "price": price,
            "invested_capital": invested_capital, "date": today_dt.strftime('%B %d, %Y'),
            "machines": [
                {
                    "name": "Machine 1: Long Call Based", "action": "BUY", "instrument": "CALL",
                    "strike": strike_call, "expiry": exp_30, "premium": prem_call,
                    "profit": "Unlimited", "risk": f"${prem_call*100} ({fmt_pct(prem_call*100)})",
                    "comment": "Bullish. Buying the upper boundary strike."
                },
                {
                    "name": "Machine 2: Short Put Based", "action": "SELL", "instrument": "PUT",
                    "strike": strike_put_30, "expiry": exp_30, "premium": prem_put_30,
                    "profit": f"${prem_put_30*100} ({fmt_pct(prem_put_30*100)})", "risk": f"${strike_put_30*100} (Cash Secured)",
                    "comment": "Income. Selling the lower boundary strike."
                },
                {
                    "name": "Machine 3: Married Put Based", "action": "BUY", "instrument": "PUT (+100 Shares)",
                    "strike": strike_put_180, "expiry": exp_180, "premium": prem_put_180,
                    "profit": "UNLIMITED", "risk": f"${round((prem_put_180 + (price - strike_put_180))*100, 2)} ({fmt_pct((prem_put_180 + (price - strike_put_180))*100)})",
                    "comment": "Strategic protection with ITM Put 6+ months."
                }
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
