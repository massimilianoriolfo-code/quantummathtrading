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
    user_query = data.get('query')
    today_str = get_now().strftime('%B %d, %Y')
    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_pc = pc.Index(host=INDEX_HOST)
        res_emb = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:embedContent?key={GOOGLE_API_KEY}", 
            json={"model": "models/gemini-embedding-2", "content": {"parts": [{"text": user_query}]}, "output_dimensionality": 768}).json()
        query_v = res_emb['embedding']['values']
        search = index_pc.query(vector=query_v, top_k=10, include_metadata=True)
        context = "\n".join([m.metadata["text"] for m in search.matches])
        
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GOOGLE_API_KEY}"
        prompt_chat = f"TODAY IS {today_str}. You are the Assistant for 'The Essence of Quantitative Math Trading'. Use context: {context}. User: {user_query}. Respond in English only."
        res_gen = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt_chat}]}]}).json()
        return jsonify({"response": res_gen['candidates'][0]['content']['parts'][0]['text']})
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
        invested_capital = price * 100
        
        expirations = stock.options
        if not expirations: return jsonify({"error": "No options available"}), 400

        # Scadenze Reali
        exp_30 = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - (today_dt + timedelta(days=30))).days))
        exp_180 = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - (today_dt + timedelta(days=180))).days))

        # Analisi Tattica
        iv_val = 0.27 
        move = price * iv_val * np.sqrt(30 / 365)
        
        chain_30 = stock.option_chain(exp_30)
        chain_180 = stock.option_chain(exp_180)

        # Machine 1 & 4 (Call)
        strike_call = find_nearest_strike(chain_30.calls, price + move)
        prem_call = chain_30.calls[chain_30.calls['strike'] == strike_call]['lastPrice'].values[0]

        # Machine 2 (Put)
        strike_put_30 = find_nearest_strike(chain_30.puts, price - move)
        prem_put_30 = chain_30.puts[chain_30.puts['strike'] == strike_put_30]['lastPrice'].values[0]

        # Machine 3 (Put ITM 6 mesi)
        strike_put_180 = find_nearest_strike(chain_180.puts, price * 1.02)
        prem_put_180 = chain_180.puts[chain_180.puts['strike'] == strike_put_180]['lastPrice'].values[0]

        def fmt_pct(val): return f"{round((val / invested_capital) * 100, 2)}%"

        return jsonify({
            "ticker": ticker_sym, "company": company_name, "price": price,
            "invested_capital": invested_capital, "volatility": round(iv_val*100, 2),
            "high": strike_call, "low": strike_put_30, "date": today_dt.strftime('%B %d, %Y'),
            "machines": [
                {
                    "name": "Machine 1: Long Call Based", "action": "BUY", "instrument": "CALL",
                    "strike": strike_call, "expiry": exp_30, "premium": prem_call,
                    "profit": "Unlimited", "risk": f"${round(prem_call*100, 2)} ({fmt_pct(prem_call*100)})",
                    "comment": "Bullish stance. Leverages momentum at the upper boundary."
                },
                {
                    "name": "Machine 2: Short Put Based", "action": "SELL", "instrument": "PUT",
                    "strike": strike_put_30, "expiry": exp_30, "premium": prem_put_30,
                    "profit": f"${round(prem_put_30*100, 2)} ({fmt_pct(prem_put_30*100)})", 
                    "risk": f"${round(strike_put_30*100, 2)} (Cash Secured)",
                    "comment": "Income generation. Selling the lower boundary."
                },
                {
                    "name": "Machine 3: Married Put Based", "action": "BUY", "instrument": "PUT (+100 Shares)",
                    "strike": strike_put_180, "expiry": exp_180, "premium": prem_put_180,
                    "profit": "UNLIMITED", 
                    "risk": f"${round((prem_put_180 + (price - strike_put_180))*100, 2)} ({fmt_pct((prem_put_180 + (price - strike_put_180))*100)})",
                    "comment": "Strategic protection. ITM Put for structural hedging."
                },
                {
                    "name": "Machine 4: Covered Call Based", "action": "SELL", "instrument": "CALL (+100 Shares)",
                    "strike": strike_call, "expiry": exp_30, "premium": prem_call,
                    "profit": f"${round((prem_call + (strike_call - price))*100, 2)} ({fmt_pct((prem_call + (strike_call - price))*100)})",
                    "risk": "Finite (Stock Ownership)",
                    "comment": "Yield enhancement. Monetizing sideways or slightly bullish markets."
                },
                {
                    "name": "Machine 5: Assigned Short Put + Covered Call", "action": "COMBINED", "instrument": "PUT & CALL",
                    "strike": f"{strike_put_30} / {strike_call}", "expiry": exp_30, "premium": round(prem_call + prem_put_30, 2),
                    "profit": "Enhanced Yield", "risk": "Reduced Cost Basis",
                    "comment": "Systematic cost basis reduction via dual premium harvesting."
                }
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
