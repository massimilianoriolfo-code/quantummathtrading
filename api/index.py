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

def find_nearest_strike(chain, target):
    strikes = chain['strike'].values
    return strikes[np.abs(strikes - target).argmin()]

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat():
    if request.method == 'OPTIONS': return jsonify({}), 200
    
    data = request.get_json(silent=True) or {}
    # Prova a leggere sia 'query' che 'user_query'
    user_query = (data.get('query') or data.get('user_query') or "").upper()
    
    if not user_query:
        return jsonify({"response": "Please enter a question."})

    try:
        # Inizializzazione Pinecone
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_pc = pc.Index(host=INDEX_HOST)
        
        # Embedding
        emb_url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={GOOGLE_API_KEY}"
        res_emb = requests.post(emb_url, json={
            "model": "models/text-embedding-004",
            "content": {"parts": [{"text": user_query}]}
        }).json()
        
        query_v = res_emb['embedding']['values']
        
        # Ricerca nel libro
        search = index_pc.query(vector=query_v, top_k=5, include_metadata=True)
        context = "\n".join([m.metadata["text"] for m in search.matches if "text" in m.metadata])
        
        # Generazione Gemini
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"
        prompt = f"CONTEXT: {context}\nQUERY: {user_query}\nRespond in English using CRPM methodology."
        
        res_gen = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt}]}]}).json()
        
        return jsonify({"response": res_gen['candidates'][0]['content']['parts'][0]['text']})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/index', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        t = data.get('ticker', '').upper()
    else:
        t = request.args.get('ticker', '').upper()
        
    if not t: return jsonify({"error": "Ticker missing"}), 400
    
    try:
        stock = yf.Ticker(t)
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
            "ticker": t, "company": stock.info.get('longName', t), "price": f2(price),
            "volatility": 27.0, "high": s_call, "low": s_put, "date": "May 04, 2026",
            "machines": [
                {"name": "Machine 1", "action": "BUY CALL", "strike": s_call, "expiry": exp, "prem": f2(p_call), "max_profit": "Unlimited", "max_risk": f"${f2(p_call*100)}", "comment": "Bullish.", "desc": "Appreciation."},
                {"name": "Machine 5", "action": "COMBINED", "strike": f"{s_put}/{s_call}", "expiry": exp, "prem": f2(p_call + p_put), "max_profit": "Yield+", "max_risk": "Basis", "comment": "Cost reduction.", "desc": "Profit."}
            ]
        })
    except Exception as e: return jsonify({"error": str(e)}), 500

handler = app
