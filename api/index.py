
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
    if not user_query: return jsonify({"response": "No query provided."})
    
    try:
        # 1. RICERCA LIBRO (Namespace forzato 'book-content')
        context = ""
        try:
            host = INDEX_HOST.strip().replace("https://", "").replace("http://", "").rstrip("/")
            pine_url = f"https://{host}/records/namespaces/book-content/search"
            headers = {"Api-Key": PINECONE_API_KEY, "Content-Type": "application/json", "X-Pinecone-Api-Version": "2024-10"}
            res_pine = requests.post(pine_url, headers=headers, json={"query": {"inputs": {"text": user_query}, "top_k": 3}}, timeout=5)
            if res_pine.status_code == 200:
                hits = res_pine.json().get('result', {}).get('hits', [])
                context = "\n".join([h.get('fields', {}).get('text', '') for h in hits])
        except: context = "Context unavailable. Use standard CRPM rules."

        # 2. GENERAZIONE RISPOSTA AI
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"
        prompt = f"Today is May 4, 2026. Context: {context}. Query: {user_query}. Rule: English, Bold titles, Professional tone."
        
        res_ai = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10).json()
        
        if 'candidates' in res_ai:
            return jsonify({"response": res_ai['candidates'][0]['content']['parts'][0]['text']})
        return jsonify({"response": "The Analytical Engine is busy. Please try again."})
    except Exception as e:
        return jsonify({"response": f"Status: {str(e)}"}), 200

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    data = request.get_json(silent=True) or {}
    ticker = data.get('ticker') or request.args.get('ticker')
    if not ticker: return jsonify({"error": "Ticker required"}), 400
    
    try:
        t_sym = ticker.upper()
        stock = yf.Ticker(t_sym)
        
        # PREZZO DI MERCATO (Risolve il problema 'undefined' nell'immagine)
        info = stock.fast_info
        price = round(info['last_price'], 2)
        inv_cap = price * 100
        
        # OPZIONI
        exps = stock.options
        target_30 = get_now() + timedelta(days=30)
        exp_30 = min(exps, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target_30).days))
        
        chain = stock.option_chain(exp_30)
        iv = 0.27
        move = price * iv * np.sqrt(30/365)
        
        s_call = find_nearest_strike(chain.calls, price + move)
        p_call = round(chain.calls[chain.calls['strike'] == s_call]['lastPrice'].values[0], 2)
        s_put = find_nearest_strike(chain.puts, price - move)
        p_put = round(chain.puts[chain.puts['strike'] == s_put]['lastPrice'].values[0], 2)

        return jsonify({
            "ticker": t_sym,
            "company": stock.info.get('longName', t_sym),
            "price": "{:.2f}".format(price),
            "inv_cap": "{:.2f}".format(inv_cap),
            "volatility": 27.0,
            "high": s_call,
            "low": s_put,
            "date": "May 04, 2026",
            "machines": [
                {"name": "Machine 1: Long Call", "action": "BUY CALL", "strike": s_call, "expiry": exp_30, "prem": "{:.2f}".format(p_call)},
                {"name": "Machine 2: Short Put", "action": "SELL PUT", "strike": s_put, "expiry": exp_30, "prem": "{:.2f}".format(p_put)}
            ]
        })
    except Exception as e:
        return jsonify({"error": f"Data Error: {str(e)}"}), 500

handler = app
