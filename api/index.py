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
    if not user_query:
        return jsonify({"response": "Query missing."})
        
    today_str = get_now().strftime('%B %d, %Y')
    
    try:
        # PULIZIA HOST E COSTRUZIONE URL CORRETTA PER INTEGRATED INDEX
        host = INDEX_HOST.strip()
        if not host.startswith("https://"):
            host = f"https://{host}"
        
        # Endpoint specifico per la ricerca nei database documentali Pinecone 2026
        pine_url = f"{host}/records/namespaces/book-content/search"
        
        headers = {
            "Api-Key": PINECONE_API_KEY,
            "Content-Type": "application/json",
            "X-Pinecone-Api-Version": "2024-10"
        }
        
        # Payload di ricerca
        payload = {"query": {"inputs": {"text": user_query}, "top_k": 5}}
        
        res_pine = requests.post(pine_url, headers=headers, json=payload, timeout=10)
        
        if res_pine.status_code != 200:
            return jsonify({"response": f"Database Error: {res_pine.status_code} - {res_pine.text}"})

        data_pine = res_pine.json()
        context_parts = []
        hits = data_pine.get('result', {}).get('hits', []) or data_pine.get('hits', [])
        
        for h in hits:
            txt = h.get('fields', {}).get('text', '')
            if txt: context_parts.append(txt)
            
        context = "\n".join(context_parts) if context_parts else "Use CRPM methodology."

        # CHIAMATA GOOGLE GEMINI
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"
        
        ai_payload = {
            "contents": [{"parts": [{"text": f"TODAY: {today_str}. CONTEXT: {context}. QUERY: {user_query}. English only. Bold titles."}]}]
        }

        res_ai = requests.post(gen_url, json=ai_payload, timeout=12).json()
        
        if 'candidates' in res_ai:
            return jsonify({"response": res_ai['candidates'][0]['content']['parts'][0]['text']})
        
        return jsonify({"response": "AI Engine returned an empty response. Check API Key."})

    except Exception as e:
        return jsonify({"response": f"Connection Error: {str(e)}"}), 200

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
        
        chain_30 = stock.option_chain(exp_30)
        iv_val = 0.27
        move = price * iv_val * np.sqrt(30 / 365)

        s_call = find_nearest_strike(chain_30.calls, price + move)
        p_call = round(chain_30.calls[chain_30.calls['strike'] == s_call]['lastPrice'].values[0], 2)
        s_put = find_nearest_strike(chain_30.puts, price - move)
        p_put = round(chain_30.puts[chain_30.puts['strike'] == s_put]['lastPrice'].values[0], 2)

        def f2(v): return "{:.2f}".format(v)

        return jsonify({
            "ticker": ticker_sym, "company": company_name, "price": f2(price), "inv_cap": f2(inv_cap),
            "volatility": 27.0, "high": s_call, "low": s_put, "date": today_dt.strftime('%B %d, %Y'),
            "machines": [
                {"name": "Machine 1", "action": "BUY CALL", "strike": s_call, "expiry": exp_30, "prem": f2(p_call), "max_profit": "Unlimited", "max_risk": f"${f2(p_call*100)}"},
                {"name": "Machine 2", "action": "SELL PUT", "strike": s_put, "expiry": exp_30, "prem": f2(p_put), "max_profit": f"${f2(p_put*100)}", "max_risk": f"${f2(round((s_put - p_put)*100, 2))}"}
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
