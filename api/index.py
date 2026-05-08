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

# Variabili Ambiente caricate da Vercel Dashboard
GOOGLE_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_HOST = os.getenv("INDEX_HOST")

def get_now():
    return datetime(2026, 5, 4)

def find_nearest_strike(chain, target):
    strikes = chain['strike'].values
    return strikes[np.abs(strikes - target).argmin()]

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}
    query = data.get('query', '').upper()
    
    if not GOOGLE_KEY or not PINECONE_KEY:
        return jsonify({"response": "DEBUG ERROR: API Keys missing in Vercel settings."})

    try:
        pc = Pinecone(api_key=PINECONE_KEY)
        index_pc = pc.Index(host=PINECONE_HOST)
        
        # 1. Embedding
        emb_url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={GOOGLE_KEY}"
        res_emb = requests.post(emb_url, json={
            "model": "models/text-embedding-004",
            "content": {"parts": [{"text": query}]}
        }).json()
        
        v_query = res_emb['embedding']['values']
        
        # 2. Ricerca
        search = index_pc.query(vector=v_query, top_k=5, include_metadata=True)
        context = "\n".join([m.metadata["text"] for m in search.matches if "text" in m.metadata])
        
        # 3. Risposta
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_KEY}"
        prompt = f"IDENTITY: CRPM Assistant. CONTEXT: {context}. QUERY: {query}. Respond in English."
        
        res_gen = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt}]}]}).json()
        return jsonify({"response": res_gen['candidates'][0]['content']['parts'][0]['text']})
    except Exception as e:
        return jsonify({"response": f"SYSTEM ERROR: {str(e)}"}), 500

@app.route('/api/index', methods=['GET', 'POST'])
def index():
    t = request.args.get('ticker') or (request.get_json(silent=True) or {}).get('ticker')
    if not t: return jsonify({"error": "Ticker missing"}), 400
    
    try:
        stock = yf.Ticker(t.upper())
        price = stock.fast_info['last_price']
        exp = min(stock.options, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - (get_now() + timedelta(days=30))).days))
        c30 = stock.option_chain(exp)
        move = price * 0.27 * np.sqrt(30 / 365)
        
        s_call = find_nearest_strike(c30.calls, price + move)
        p_call = round(c30.calls[c30.calls['strike'] == s_call]['lastPrice'].values[0], 2)
        s_put = find_nearest_strike(c30.puts, price - move)
        p_put = round(c30.puts[c30.puts['strike'] == s_put]['lastPrice'].values[0], 2)
        
        def f2(v): return "{:.2f}".format(v)
        
        return jsonify({
            "ticker": t.upper(), "company": stock.info.get('longName', t), "price": f2(price),
            "volatility": 27.0, "high": s_call, "low": s_put, "date": "May 04, 2026",
            "machines": [
                {"name": "Machine 1", "action": "BUY CALL", "strike": s_call, "expiry": exp, "prem": f2(p_call), "max_profit": "Unlimited", "max_risk": f"${f2(p_call*100)}", "comment": "Bullish.", "desc": "Appreciation."},
                {"name": "Machine 5", "action": "COMBINED", "strike": f"{s_put}/{s_call}", "expiry": exp, "prem": f2(p_call + p_put), "max_profit": "Yield+", "max_risk": "Basis", "comment": "Cost reduction.", "desc": "Profit."}
            ]
        })
    except Exception as e: return jsonify({"error": str(e)}), 500

handler = app
