iimport yfinance as yf
import numpy as np
import requests
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# Fallback per la data se get_now fallisce
def get_now():
    return datetime(2026, 5, 4)

def find_nearest_strike(chain, target):
    strikes = chain['strike'].values
    return strikes[np.abs(strikes - target).argmin()]

@app.route('/api/index', methods=['GET'])
def index():
    ticker_sym = request.args.get('ticker', '').upper()
    if not ticker_sym:
        return jsonify({"error": "Ticker missing"}), 400

    try:
        stock = yf.Ticker(ticker_sym)
        # Usiamo fast_info perché è più veloce e meno soggetto a blocchi
        price = round(stock.fast_info['last_price'], 2)
        inv_cap = price * 100
        
        expirations = stock.options
        if not expirations:
            return jsonify({"error": "No options found for this ticker"}), 404

        # Calcolo scadenze 30 e 180 giorni
        target_30 = get_now() + timedelta(days=30)
        exp_30 = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target_30).days))
        
        target_180 = get_now() + timedelta(days=180)
        exp_180 = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target_180).days))

        c30 = stock.option_chain(exp_30)
        c180 = stock.option_chain(exp_180)
        
        move = price * 0.27 * np.sqrt(30 / 365)
        
        s_call = find_nearest_strike(c30.calls, price + move)
        p_call = round(c30.calls[c30.calls['strike'] == s_call]['lastPrice'].values[0], 2)
        
        s_put30 = find_nearest_strike(c30.puts, price - move)
        p_put30 = round(c30.puts[c30.puts['strike'] == s_put30]['lastPrice'].values[0], 2)
        
        s_put180 = find_nearest_strike(c180.puts, price * 1.02)
        p_put180 = round(c180.puts[c180.puts['strike'] == s_put180]['lastPrice'].values[0], 2)

        def f2(v): return "{:.2f}".format(v)

        return jsonify({
            "ticker": ticker_sym,
            "company": stock.info.get('longName', ticker_sym),
            "price": f2(price),
            "inv_cap": f2(inv_cap),
            "volatility": 27.0,
            "high": s_call,
            "low": s_put30,
            "date": get_now().strftime('%B %d, %Y'),
            "machines": [
                {"name": "Machine 1: Long Call", "action": "BUY CALL", "strike": s_call, "expiry": exp_30, "prem": f2(p_call), "max_profit": "Unlimited", "max_risk": f"${f2(p_call*100)}", "comment": "Bullish.", "desc": "Capital appreciation."},
                {"name": "Machine 2: Short Put", "action": "SELL PUT", "strike": s_put30, "expiry": exp_30, "prem": f2(p_put30), "max_profit": f"${f2(p_put30*100)}", "max_risk": f"${f2((s_put30-p_put30)*100)}", "comment": "Income.", "desc": "Volatility harvest."},
                {"name": "Machine 3: Married Put", "action": "BUY PUT", "strike": s_put180, "expiry": exp_180, "prem": f2(p_put180), "max_profit": "Unlimited", "max_risk": f"${f2((p_put180+(price-s_put180))*100)}", "comment": "Hedging.", "desc": "Protection."},
                {"name": "Machine 4: Covered Call", "action": "SELL CALL", "strike": s_call, "expiry": exp_30, "prem": f2(p_call), "max_profit": f"${f2((p_call+(s_call-price))*100)}", "max_risk": "Stock Ownership", "comment": "Yield.", "desc": "Income."},
                {"name": "Machine 5: Combined", "action": "PUT & CALL", "strike": f"{s_put30}/{s_call}", "expiry": exp_30, "prem": f2(p_call + p_put30), "max_profit": "Enhanced Yield", "max_risk": "Basis Reduction", "comment": "Cost reduction.", "desc": "Profit."}
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
