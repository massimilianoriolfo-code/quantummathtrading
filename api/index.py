import yfinance as yf
import numpy as np
import requests
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
from pinecone import Pinecone

app = Flask(__name__)
CORS(app)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_HOST = os.getenv("INDEX_HOST")

def get_now():
    return datetime(2026, 5, 4)

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
        iv_val = 0.27 # Fixed for consistent calculation
        
        exp_30_str = (today_dt + timedelta(days=30)).strftime('%d %b %Y')
        m3_expiry_str = (today_dt + timedelta(days=180)).strftime('%B %Y')
        
        move = price * iv_val * np.sqrt(30 / 365)
        high, low = round(price + move, 2), round(price - move, 2)
        
        # Machine 3 specific
        m3_strike = round(price * 1.02, 2)
        m3_premium = round(price * 0.08, 2)
        max_risk_pct = round(((m3_premium - (m3_strike - price)) / price) * 100, 2)

        # Machine 4 & 5 premiums (Simulated from IV)
        call_prem_30d = round(price * 0.025, 2)
        put_prem_30d = round(price * 0.022, 2)

        return jsonify({
            "ticker": ticker_sym,
            "company": company_name,
            "price": price,
            "volatility": round(iv_val*100, 2),
            "high": high,
            "low": low,
            "date": today_dt.strftime('%B %d, %Y'),
            "machines": [
                {
                    "id": "1", "name": "Machine 1: Long Call Based", "action": "BUY", "instrument": "CALL",
                    "strike": high, "expiry": exp_30_str, "premium": call_prem_30d, "profit": "Unlimited", "risk": "Finite (Premium Paid)",
                    "comment": "Bullish stance. Buying the upper boundary to leverage momentum with defined risk."
                },
                {
                    "id": "2", "name": "Machine 2: Short Put Based", "action": "SELL", "instrument": "PUT",
                    "strike": low, "expiry": exp_30_str, "premium": put_prem_30d, "profit": "Finite (Premium Received)", "risk": "Finite (Cash Secured)",
                    "comment": "Income generation. Selling the lower boundary. Ideal if you are willing to own the stock at a discount."
                },
                {
                    "id": "3", "name": "Machine 3: Married Put Based", "action": "BUY", "instrument": "PUT (+100 Shares)",
                    "strike": m3_strike, "expiry": m3_expiry_str, "premium": m3_premium, "profit": "UNLIMITED", "risk": f"{max_risk_pct}% of Capital",
                    "comment": "Strategic protection. Using ITM Put and 6+ months to minimize Theta decay while keeping upside open."
                },
                {
                    "id": "4", "name": "Machine 4: Covered Call Based", "action": "SELL", "instrument": "CALL (+100 Shares)",
                    "strike": high, "expiry": exp_30_str, "premium": call_prem_30d, "profit": "Finite (Cap at Strike)", "risk": "Finite (Stock Ownership)",
                    "comment": "Yield enhancement for existing positions. Selling the upper boundary to monetize sideways markets."
                },
                {
                    "id": "5", "name": "Machine 5: Assigned Short Put + Covered Call", "action": "COMBINED", "instrument": "PUT & CALL",
                    "strike": f"{low} / {high}", "expiry": exp_30_str, "premium": round(call_prem_30d + put_prem_30d, 2), "profit": "Enhanced Yield", "risk": "Reduced Basis",
                    "comment": "Systematic cost basis reduction. Combining premiums from multiple machines to lower the break-even point."
                }
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
