import yfinance as yf
import numpy as np
import requests
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_HOST = os.getenv("INDEX_HOST")

def get_now(): return datetime(2026, 5, 14)

def find_nearest_strike(chain, target):
    strikes = chain['strike'].values
    return strikes[np.abs(strikes - target).argmin()]

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}
    user_query = data.get('query', '')
    if not user_query: return jsonify({"response": "No query."})
    
    try:
        host = INDEX_HOST.strip().replace("https://", "").replace("http://", "").rstrip("/")
        pine_url = f"https://{host}/records/namespaces/book-content/search"
        
        res_pine = requests.post(pine_url, 
            headers={"Api-Key": PINECONE_API_KEY, "Content-Type": "application/json", "X-Pinecone-Api-Version": "2024-10"},
            json={"query": {"inputs": {"text": user_query}, "top_k": 5}}, timeout=10)
        
        context = ""
        if res_pine.status_code == 200:
            hits = res_pine.json().get('result', {}).get('hits', [])
            context = "\n".join([h.get('fields', {}).get('text', '') for h in hits if h.get('fields')])

        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"
        prompt = f"Using Massimiliano Riolfo's CRPM book context: {context}\nQuestion: {user_query}\nRule: Professional, English only, bold titles."
        
        res_ai = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=12).json()
        
        if 'candidates' in res_ai and res_ai['candidates']:
            return jsonify({"response": res_ai['candidates'][0]['content']['parts'][0]['text']})
        return jsonify({"response": "Analytical engine recalibrating. Please try again."})
    except Exception as e:
        return jsonify({"response": f"System error: {str(e)}"}), 200

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    t = (request.get_json(silent=True) or {}).get('ticker') or request.args.get('ticker', 'AAPL')
    ticker_sym = t.upper()
    try:
        stock = yf.Ticker(ticker_sym)
        price = stock.fast_info['last_price']
        iv = 0.27
        move = price * iv * np.sqrt(30/365)
        
        exp_30 = stock.options[0]
        chain_30 = stock.option_chain(exp_30)
        
        s_call = float(find_nearest_strike(chain_30.calls, price + move))
        s_put = float(find_nearest_strike(chain_30.puts, price - move))

        return jsonify({
            "ticker": ticker_sym,
            "company": stock.info.get('longName', ticker_sym),
            "price": f"{price:.2f}",
            "inv_cap": f"{price*100:.2f}",
            "volatility": 27.0,
            "low": f"{s_put:.2f}",
            "high": f"{s_call:.2f}",
            "machines": [
                {"id": 1, "name": "MACHINE 1: LONG CALL BASE", "action": "BUY CALL", "strike": s_call, "expiry": "30d", "prem": "Market", "max_profit": "UNLIMITED", "max_risk": "Premium"},
                {"id": 2, "name": "MACHINE 2: SHORT PUT BASED", "action": "SELL PUT", "strike": s_put, "expiry": "30d", "prem": "Market", "max_profit": "Premium", "max_risk": "Capital"},
                {"id": 3, "name": "MACHINE 3: MARRIED PUT (PROTECTION)", "action": "BUY PUT", "strike": price, "expiry": "180d", "prem": "Calculated", "max_profit": "UNLIMITED", "max_risk": "Premium"},
                {"id": 4, "name": "MACHINE 4: COVERED CALL (INCOME)", "action": "SELL CALL", "strike": s_call, "expiry": "30d", "prem": "Market", "max_profit": "Capped", "max_risk": "Stock Ownership"},
                {"id": 5, "name": "MACHINE 5: COMBINED SHORT PUT & COVERED CALL", "action": "PUT & CALL", "strike": f"{s_put}/{s_call}", "expiry": "30d", "prem": "Net", "max_profit": "Yield", "max_risk": "Calculated"}
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
