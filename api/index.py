import yfinance as yf
import numpy as np
import os
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
from pinecone import Pinecone

app = Flask(__name__)
CORS(app)

# Configurazione API
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_HOST = os.getenv("INDEX_HOST")

# Inizializzazione Ufficiale
genai.configure(api_key=GOOGLE_API_KEY)

def get_now():
    return datetime(2026, 5, 4)

def find_nearest_strike(chain, target):
    strikes = chain['strike'].values
    return strikes[np.abs(strikes - target).argmin()]

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_query = data.get('query').upper()
    today_str = get_now().strftime('%B %d, %Y')
    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_pc = pc.Index(host=INDEX_HOST)
        
        # Embedding tramite libreria ufficiale
        res_emb = genai.embed_content(
            model="models/text-embedding-004",
            content=user_query,
            task_type="retrieval_query"
        )
        query_v = res_emb['embedding']
        
        search = index_pc.query(vector=query_v, top_k=10, include_metadata=True)
        context = "\n".join([m.metadata["text"] for m in search.matches])
        
        # Generazione con Gemini 1.5 Flash (Enterprise Stable)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt_chat = f"TODAY: {today_str}. CONTEXT: {context}. QUERY: {user_query}. Respond in English, aseptic, quantitative tone."
        
        res_gen = model.generate_content(prompt_chat)
        return jsonify({"response": res_gen.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    data = request.get_json(silent=True) or {}
    t = data.get('ticker') or request.args.get('ticker')
    if not t: return jsonify({"error": "Ticker missing"}), 400
    ticker_sym = t.upper()
    today_dt = get_now()
    try:
        stock = yf.Ticker(ticker_sym)
        company_name = stock.info.get('longName', ticker_sym)
        price = round(stock.fast_info['last_price'], 2)
        inv_cap = price * 100
        expirations = stock.options
        exp_30 = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - (today_dt + timedelta(days=30))).days))
        exp_180 = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - (today_dt + timedelta(days=180))).days))
        chain_30 = stock.option_chain(exp_30)
        chain_180 = stock.option_chain(exp_180)
        iv_val = 0.27
        move = price * iv_val * np.sqrt(30 / 365)
        s_call = find_nearest_strike(chain_30.calls, price + move)
        p_call = round(chain_30.calls[chain_30.calls['strike'] == s_call]['lastPrice'].values[0], 2)
        s_put_30 = find_nearest_strike(chain_30.puts, price - move)
        p_put_30 = round(chain_30.puts[chain_30.puts['strike'] == s_put_30]['lastPrice'].values[0], 2)
        s_put_180 = find_nearest_strike(chain_180.puts, price * 1.02)
        p_put_180 = round(chain_180.puts[chain_180.puts['strike'] == s_put_180]['lastPrice'].values[0], 2)
        def pct(v): return f"{round((v / inv_cap) * 100, 2)}%"
        def f2(v): return "{:.2f}".format(v)
        return jsonify({
            "ticker": ticker_sym, "company": company_name, "price": f2(price), "inv_cap": f2(inv_cap),
            "volatility": 27.0, "high": s_call, "low": s_put_30, "date": today_dt.strftime('%B %d, %Y'),
            "machines": [
                {"name": "Machine 1: Long Call", "action": "BUY CALL", "strike": s_call, "expiry": exp_30, "prem": f2(p_call), "max_profit": "Unlimited", "max_risk": f"${f2(p_call*100)} ({pct(p_call*100)})", "desc": "Bullish momentum."},
                {"name": "Machine 2: Short Put", "action": "SELL PUT", "strike": s_put_30, "expiry": exp_30, "prem": f2(p_put_30), "max_profit": f"${f2(p_put_30*100)}", "max_risk": f"${f2((s_put_30-p_put_30)*100)}", "desc": "Income generation."},
                {"name": "Machine 3: Married Put", "action": "BUY PUT (+100 Shares)", "strike": s_put_180, "expiry": exp_180, "prem": f2(p_put_180), "max_profit": "UNLIMITED", "max_risk": f"${f2((p_put_180+(price-s_put_180))*100)}", "desc": "Structural hedging."},
                {"name": "Machine 4: Covered Call", "action": "SELL CALL (+100 Shares)", "strike": s_call, "expiry": exp_30, "prem": f2(p_call), "max_profit": f"${f2((p_call+(s_call-price))*100)}", "max_risk": "Stock Ownership", "desc": "Yield enhancement."},
                {"name": "Machine 5: Assigned Combined", "action": "PUT & CALL", "strike": f"{s_put_30}/{s_call}", "expiry": exp_30, "prem": f2(p_call+p_put_30), "max_profit": "Enhanced Yield", "max_risk": "Reduced Basis", "desc": "Cost reduction."}
            ]
        })
    except Exception as e: return jsonify({"error": str(e)}), 500

handler = app
