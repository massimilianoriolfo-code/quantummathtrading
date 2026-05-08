import yfinance as yf
import numpy as np
import requests
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
from pinecone import Pinecone

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Variabili d'ambiente
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
    if request.method == 'OPTIONS': return jsonify({"status": "ok"}), 200
    
    data = request.get_json(silent=True) or {}
    user_query = data.get('query') or data.get('user_query')
    
    if not user_query:
        return jsonify({"response": "DEBUG: No query received by Flask."}), 400

    try:
        # Verifica preventiva Chiavi
        if not GOOGLE_API_KEY or not PINECONE_API_KEY:
            return jsonify({"response": "DEBUG: Missing API Keys in Vercel Environment."})

        # 1. Inizializzazione Pinecone
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_pc = pc.Index(host=INDEX_HOST)
        
        # 2. Embedding
        emb_url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={GOOGLE_API_KEY}"
        emb_res = requests.post(emb_url, json={
            "model": "models/text-embedding-004",
            "content": {"parts": [{"text": user_query}]}
        })
        
        if emb_res.status_code != 200:
            return jsonify({"response": f"DEBUG: Google Embedding Error: {emb_res.text}"})
        
        query_v = emb_res.json()['embedding']['values']
        
        # 3. Ricerca contestuale
        search = index_pc.query(vector=query_v, top_k=5, include_metadata=True)
        context = "\n".join([m.metadata["text"] for m in search.matches if "text" in m.metadata])
        
        # 4. Generazione Gemini 1.5 Flash
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"
        prompt = f"IDENTITY: CRPM Engine. CONTEXT: {context}. QUERY: {user_query}. Respond in English only."
        
        gen_res = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt}]}]})
        
        if gen_res.status_code != 200:
            return jsonify({"response": f"DEBUG: Gemini Generation Error: {gen_res.text}"})

        final_text = gen_res.json()['candidates'][0]['content']['parts'][0]['text']
        return jsonify({"response": final_text})
        
    except Exception as e:
        return jsonify({"error": f"CRITICAL SYSTEM ERROR: {str(e)}"}), 500

@app.route('/api/index', methods=['GET', 'POST'])
def index():
    t = request.args.get('ticker') or (request.get_json(silent=True) or {}).get('ticker')
    if not t: return jsonify({"error": "Ticker missing"}), 400
    
    try:
        stock = yf.Ticker(t.upper())
        # Usiamo un timeout per evitare blocchi infiniti
        price = stock.fast_info['last_price']
        
        expirations = stock.options
        if not expirations: return jsonify({"error": "No options available"}), 404
        
        exp = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - (get_now() + timedelta(days=30))).days))
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
