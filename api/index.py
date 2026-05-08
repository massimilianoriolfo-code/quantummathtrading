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

G_KEY = os.getenv("GOOGLE_API_KEY")
P_KEY = os.getenv("PINECONE_API_KEY")
P_HOST = os.getenv("INDEX_HOST")

def get_now():
    return datetime(2026, 5, 4)

def find_nearest_strike(chain, target):
    strikes = chain['strike'].values
    idx = np.abs(strikes - target).argmin()
    return float(strikes[idx])

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}
    query = data.get('query', '')
    if not query: return jsonify({"response": "No query."})
    try:
        pc = Pinecone(api_key=P_KEY)
        idx_pc = pc.Index(host=P_HOST)
        # Embedding
        res_emb = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={G_KEY}", 
            json={"model": "models/text-embedding-004", "content": {"parts": [{"text": query}]}}).json()
        # Search
        search = idx_pc.query(vector=res_emb['embedding']['values'], top_k=5, include_metadata=True)
        context = "\n".join([m.metadata["text"] for m in search.matches if "text" in m.metadata])
        # Gemini
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={G_KEY}"
        res_gen = requests.post(gen_url, json={"contents": [{"parts": [{"text": f"Context: {context}\nQuestion: {query}"}]}]}).json()
        return jsonify({"response": res_gen['candidates'][0]['content']['parts'][0]['text']})
    except Exception as e:
        return jsonify({"response": f"AI Error: {str(e)}"}), 500

@app.route('/api/index', methods=['GET'])
def index():
    t = request.args.get('ticker', '').upper()
    if not t: return jsonify({"error": "No ticker"}), 400
    try:
        stock = yf.Ticker(t)
        # Recupero prezzo che alimentava il cono
        price = float(stock.fast_info['last_price'])
        expirations = stock.options
        exp = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - (get_now() + timedelta(days=30))).days))
        
        c = stock.option_chain(exp)
        move = price * 0.27 * np.sqrt(30 / 365)
        
        s_call = find_nearest_strike(c.calls, price + move)
        p_call = float(c.calls[c.calls['strike'] == s_call]['lastPrice'].values[0])
        s_put = find_nearest_strike(c.puts, price - move)
        p_put = float(c.puts[c.puts['strike'] == s_put]['lastPrice'].values[0])
        
        def f2(v): return "{:.2f}".format(v)
        
        return jsonify({
            "ticker": t, "company": stock.info.get('longName', t), 
            "price": f2(price), "inv_cap": f2(price * 100),
            "volatility": 27.0, "high": s_call, "low": s_put, "date": "May 04, 2026",
            "machines": [
                {"name": "Machine 1", "action": "BUY CALL", "strike": s_call, "expiry": exp, "prem": f2(p_call), "max_profit": "Unlimited", "max_risk": f"${f2(p_call*100)}", "comment": "Bullish", "desc": "Appreciation"},
                {"name": "Machine 5", "action": "PUT & CALL", "strike": f"{s_put}/{s_call}", "expiry": exp, "prem": f2(p_call + p_put), "max_profit": "Yield+", "max_risk": "Basis", "comment": "Cost reduction", "desc": "Profit"}
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
