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

def get_now():
    return datetime(2026, 5, 14)

def find_nearest_strike(chain, target):
    strikes = chain['strike'].values
    return strikes[np.abs(strikes - target).argmin()]

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}
    user_query = data.get('query', '')
    if not user_query: return jsonify({"response": "Please enter a question."})
    
    try:
        host = INDEX_HOST.strip().replace("https://", "").replace("http://", "").rstrip("/")
        pine_url = f"https://{host}/records/namespaces/book-content/search"
        context = ""
        
        # Chiamata REST a Pinecone (Integrated Index 2026)
        res_pine = requests.post(pine_url, 
            headers={"Api-Key": PINECONE_API_KEY, "Content-Type": "application/json", "X-Pinecone-Api-Version": "2024-10"},
            json={"query": {"inputs": {"text": user_query}, "top_k": 5}}, timeout=10)
        
        if res_pine.status_code == 200:
            hits = res_pine.json().get('result', {}).get('hits', [])
            context = "\n".join([h.get('fields', {}).get('text', '') for h in hits if h.get('fields')])

        # Generazione con Gemini 1.5 Flash (Veloce per evitare timeout)
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"
        prompt = f"IDENTITY: CRPM Assistant. CONTEXT: {context}. QUERY: {user_query}. Rule: Answer using provided book context. English only. Bold titles."
        
        res_ai = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=12).json()
        
        if 'candidates' in res_ai and res_ai['candidates']:
            return jsonify({"response": res_ai['candidates'][0]['content']['parts'][0]['text']})
        return jsonify({"response": "Assistant is analyzing the methodology. Please try again."})
    except Exception as e:
        return jsonify({"response": f"System status: {str(e)}"}), 200

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    t = (request.get_json(silent=True) or {}).get('ticker') or request.args.get('ticker', 'SPY')
    ticker_sym = t.upper()
    try:
        stock = yf.Ticker(ticker_sym)
        price = stock.fast_info['last_price']
        iv = 0.27
        move = price * iv * np.sqrt(30/365)
        
        # Scadenze e Option Chain
        exps = stock.options
        chain_30 = stock.option_chain(exps[0])
        chain_180 = stock.option_chain(exps[-1]) if len(exps) > 5 else chain_30
        
        s_high = float(find_nearest_strike(chain_30.calls, price + move))
        s_low = float(find_nearest_strike(chain_30.puts, price - move))
        s_prot = float(find_nearest_strike(chain_180.puts, price * 1.02))

        return jsonify({
            "ticker": ticker_sym,
            "company": stock.info.get('longName', ticker_sym),
            "price": f"{price:.2f}",
            "inv_cap": f"{price*100:.2f}",
            "volatility": iv * 100,
            "low": f"{s_low:.2f}",
            "high": f"{s_high:.2f}",
            "machines": [
                {"name": "Machine 1: Speculative Call", "action": "BUY CALL", "strike": s_high, "expiry": "30d", "prem": "Market", "max_profit": "UNLIMITED", "max_risk": "Premium", "desc": "Bullish leverage.", "comment": "Volatility check."},
                {"name": "Machine 2: Income Put", "action": "SELL PUT", "strike": s_low, "expiry": "30d", "prem": "Market", "max_profit": "Premium", "max_risk": "Capital", "desc": "Income strategy.", "comment": "Support focus."},
                {"name": "Machine 3: Married Put (Hedge)", "action": "BUY PUT", "strike": s_prot, "expiry": "180d", "prem": "Calculated", "max_profit": "UNLIMITED", "max_risk": "Premium", "desc": "Capital protection.", "comment": "Portfolio insurance."},
                {"name": "Machine 4: Covered Call (Yield)", "action": "SELL CALL", "strike": s_high, "expiry": "30d", "prem": "Market", "max_profit": "Capped", "max_risk": "Stock Ownership", "desc": "Yield generation.", "comment": "Optimization."},
                {"name": "Machine 5: Combined Strategy", "action": "STRANGLE/STRADDLE", "strike": f"{s_low}/{s_high}", "expiry": "30d", "prem": "Net", "max_profit": "Variable", "max_risk": "Calculated", "desc": "Volatility play.", "comment": "CRPM Managed."}
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
