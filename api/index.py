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

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_query = data.get('query', '').upper()
    today_str = get_now().strftime('%B %d, %Y')
    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_pc = pc.Index(host=INDEX_HOST)
        
        # 1. Embedding
        res_emb = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={GOOGLE_API_KEY}", 
            json={"model": "models/text-embedding-004", "content": {"parts": [{"text": user_query}]}}
        ).json()
        query_v = res_emb['embedding']['values']
        
        # 2. Search
        search = index_pc.query(vector=query_v, top_k=10, include_metadata=True)
        context = "\n".join([m.metadata["text"] for m in search.matches])
        
        # 3. Generation
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"
        prompt_chat = f"TODAY IS {today_str}. CONTEXT: {context}. QUERY: {user_query}. Respond in English. Professional tone."
        
        res_gen = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt_chat}]}]}).json()
        ai_response = res_gen['candidates'][0]['content']['parts'][0]['text']
        return jsonify({"response": ai_response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/index', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        ticker_sym = data.get('ticker', '').upper()
    else:
        ticker_sym = request.args.get('ticker', '').upper()

    if not ticker_sym:
        return jsonify({"error": "Ticker missing"}), 400

    today_dt = get_now()
    try:
        stock = yf.Ticker(ticker_sym)
        company_name = stock.info.get('longName', ticker_sym)
        price = round(stock.fast_info['last_price'], 2)
        inv_cap = price * 100
        expirations = stock.options
        
        exp_30 = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - (today_dt + timedelta(days=30))).days))
        c30 = stock.option_chain(exp_30)
        move = price * 0.27 * np.sqrt(30 / 365)
        
        s_call = find_nearest_strike(c30.calls, price + move)
        p_call = round(c30.calls[c30.calls['strike'] == s_call]['lastPrice'].values[0], 2)
        s_put30 = find_nearest_strike(c30.puts, price - move)
        p_put30 = round(c30.puts[c30.puts['strike'] == s_put30]['lastPrice'].values[0], 2)

        def f2(v): return "{:.2f}".format(v)

        return jsonify({
            "ticker": ticker_sym, "company": company_name, "price": f2(price), "inv_cap": f2(inv_cap),
            "volatility": 27.0, "high": s_call, "low": s_put30, "date": today_dt.strftime('%B %d, %Y'),
            "machines": [
                {"name": "Machine 1: Long Call Based", "action": "BUY CALL", "strike": s_call, "expiry": exp_30, "prem": f2(p_call), "max_profit": "Unlimited", "max_risk": f"${f2(p_call*100)}", "comment": "Bullish.", "desc": "Appreciation."},
                {"name": "Machine 2: Short Put Based", "action": "SELL PUT", "strike": s_put30, "expiry": exp_30, "prem": f2(p_put30), "max_profit": f"${f2(p_put30*100)}", "max_risk": f"${f2((s_put30-p_put30)*100)}", "comment": "Income.", "desc": "Harvest."},
                {"name": "Machine 5: Combined", "action": "PUT & CALL", "strike": f"{s_put30}/{s_call}", "expiry": exp_30, "prem": f2(p_call + p_put30), "max_profit": "Yield+", "max_risk": "Basis Reduction", "comment": "Cost reduction.", "desc": "Profit."}
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
