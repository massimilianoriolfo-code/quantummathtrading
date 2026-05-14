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

# Credenziali Ambiente
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
    if not user_query:
        return jsonify({"response": "No query provided."})
    
    today_str = get_now().strftime('%B %d, %Y')
    
    try:
        # Ricerca nel libro su Pinecone
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_pc = pc.Index(host=INDEX_HOST)
        
        # Sintassi originale del 4 maggio
        search_res = index_pc.query(
            vector=[0] * 768, # Placeholder per ricerca testuale semplice
            top_k=5,
            include_metadata=True,
            filter={"text": {"$exists": True}}
        )
        
        context_parts = [match['metadata']['text'] for match in search_res['matches'] if 'text' in match['metadata']]
        context = "\n".join(context_parts)

        # Chiamata a Gemini
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GOOGLE_API_KEY}"
        
        prompt = f"TODAY: {today_str}. CONTEXT: {context}. QUERY: {user_query}. Answer as CRPM Assistant. English only. Bold titles."
        
        res_ai = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt}]}]}).json()
        
        return jsonify({"response": res_ai['candidates'][0]['content']['parts'][0]['text']})
    except Exception as e:
        return jsonify({"response": f"System error: {str(e)}"}), 200

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    t = (request.get_json(silent=True) or {}).get('ticker') or request.args.get('ticker', 'SPY')
    ticker_sym = t.upper()
    today_dt = get_now()

    try:
        stock = yf.Ticker(ticker_sym)
        price = stock.fast_info['last_price']
        inv_cap = price * 100
        
        # Calcolo opzioni a 30 giorni
        exp = stock.options[0]
        chain = stock.option_chain(exp)
        move = price * 0.27 * np.sqrt(30/365)
        
        s_call = find_nearest_strike(chain.calls, price + move)
        s_put = find_nearest_strike(chain.puts, price - move)

        return jsonify({
            "ticker": ticker_sym,
            "company": stock.info.get('longName', ticker_sym),
            "price": f"{price:.2f}",
            "inv_cap": f"{inv_cap:.2f}",
            "volatility": 27.0,
            "low": f"{s_put:.2f}",
            "high": f"{s_call:.2f}",
            "machines": [
                {"name": "Machine 1: Long Call", "action": "BUY CALL", "strike": s_call, "expiry": exp, "prem": "Market", "max_profit": "UNLIMITED", "max_risk": "Premium", "desc": "Bullish strategy.", "comment": "Volatility check."},
                {"name": "Machine 2: Short Put", "action": "SELL PUT", "strike": s_put, "expiry": exp, "prem": "Market", "max_profit": "Premium", "max_risk": "Capital", "desc": "Income strategy.", "comment": "Support level."}
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
