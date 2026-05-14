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
    return datetime(2026, 5, 4)

def find_nearest_strike(chain, target):
    strikes = chain['strike'].values
    return strikes[np.abs(strikes - target).argmin()]

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}
    user_query = data.get('query', '')
    if not user_query: return jsonify({"response": "Please enter a question."})
    
    try:
        # RICERCA NEL LIBRO (REST API)
        host = INDEX_HOST.strip().replace("https://", "").replace("http://", "").rstrip("/")
        pine_url = f"https://{host}/records/namespaces/book-content/search"
        
        context = ""
        res_pine = requests.post(pine_url, 
            headers={"Api-Key": PINECONE_API_KEY, "Content-Type": "application/json", "X-Pinecone-Api-Version": "2024-10"},
            json={"query": {"inputs": {"text": user_query}, "top_k": 5}},
            timeout=8
        )
        
        if res_pine.status_code == 200:
            hits = res_pine.json().get('result', {}).get('hits', [])
            context = "\n".join([h.get('fields', {}).get('text', '') for h in hits if h.get('fields')])

        # GENERAZIONE RISPOSTA AI
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"
        prompt = f"Context from Massimiliano Riolfo's book: {context}\nQuestion: {user_query}\nRule: English only, bold titles, professional CRPM style."
        
        res_ai = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10).json()
        response = res_ai['candidates'][0]['content']['parts'][0]['text'] if 'candidates' in res_ai else "Assistant temporarily unavailable."
        return jsonify({"response": response})
    except Exception as e:
        return jsonify({"response": f"System Status: {str(e)}"}), 200

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    t = (request.get_json(silent=True) or {}).get('ticker') or request.args.get('ticker', 'AAPL')
    try:
        ticker_sym = t.upper()
        stock = yf.Ticker(ticker_sym)
        price = stock.fast_info['last_price']
        
        # Calcolo Opzioni per simulatore
        exp = stock.options[0] # Prende la scadenza più vicina
        chain = stock.option_chain(exp)
        move = price * 0.27 * np.sqrt(30/365) # 1-Sigma approssimato
        
        s_call = float(find_nearest_strike(chain.calls, price + move))
        s_put = float(find_nearest_strike(chain.puts, price - move))

        return jsonify({
            "ticker": ticker_sym,
            "company": stock.info.get('longName', ticker_sym),
            "price": f"{price:.2f}",
            "inv_cap": f"{price*100:.2f}",
            "volatility": 27.0,
            "low": f"{s_put:.2f}",
            "high": f"{s_call:.2f}",
            "machines": [
                {"name": "Machine 1: Long Call", "action": "BUY CALL", "strike": s_call, "expiry": exp, "prem": "Calculated", "max_profit": "UNLIMITED", "max_risk": "Premium", "desc": "Bullish leverage.", "comment": "Volatility check required."},
                {"name": "Machine 2: Short Put", "action": "SELL PUT", "strike": s_put, "expiry": exp, "prem": "Calculated", "max_profit": "Premium", "max_risk": "Capital", "desc": "Income strategy.", "comment": "Support level focus."}
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
