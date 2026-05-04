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
        # Prompt istruito per formattazione pulita senza Markdown "sporco"
        prompt_chat = f"""TODAY IS {today_str}. 
        You are the Assistant for 'The Essence of Quantitative Math Trading'. 
        Context: {context}. User: {user_query}. 
        
        STRICT FORMATTING RULES:
        - Use ONLY English.
        - Break text into short paragraphs.
        - Use bold titles for sections.
        - NEVER use raw table syntax (| or -).
        - Use bullet points for lists.
        - Keep it clean and clinical."""
        
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
        def f2(v): return "{:.2f}".format(v) # Forza due decimali sempre

        return jsonify({
            "ticker": ticker_sym, "company": company_name, "price": f2(price), "inv_cap": f2(inv_cap),
            "volatility": 27.0, "high": s_call, "low": s_put_30, "date": today_dt.strftime('%B %d, %Y'),
            "machines": [
                {
                    "name": "Machine 1: Long Call Based", "action": "BUY CALL", "strike": s_call, "expiry": exp_30, "prem": f2(p_call),
                    "max_profit": "Unlimited", "max_risk": f"${f2(p_call*100)} ({pct(p_call*100)})",
                    "comment": "Bullish momentum strategy.",
                    "desc": "This machine seeks to capitalize on price appreciation beyond the 1-Sigma upper boundary. It offers high leverage with risk limited strictly to the premium paid."
                },
                {
                    "name": "Machine 2: Short Put Based", "action": "SELL PUT", "strike": s_put_30, "expiry": exp_30, "prem": f2(p_put_30),
                    "max_profit": f"${f2(p_put_30*100)} ({pct(p_put_30*100)})", "max_risk": f"${f2(round((s_put_30 - p_put_30)*100, 2))} ({pct((s_put_30 - p_put_30)*100)})",
                    "comment": "Income generation strategy.",
                    "desc": "Designed to harvest volatility by selling the lower probability boundary. The maximum risk is the net cost of the stock if assigned (Strike minus Premium)."
                },
                {
                    "name": "Machine 3: Married Put Based", "action": "BUY PUT (+100 Shares)", "strike": s_put_180, "expiry": exp_180, "prem": f2(p_put_180),
                    "max_profit": "UNLIMITED", "max_risk": f"${f2(round((p_put_180 + (price - s_put_180))*100, 2))} ({pct((p_put_180 + (price - s_put_180))*100)})",
                    "comment": "Structural hedging strategy.",
                    "desc": "A strategic long-term protection. By using an ITM Put with 6+ months to expiry, it minimizes time decay while ensuring the portfolio remains protected against tail risks."
                },
                {
                    "name": "Machine 4: Covered Call Based", "action": "SELL CALL (+100 Shares)", "strike": s_call, "expiry": exp_30, "prem": f2(p_call),
                    "max_profit": f"${f2(round((p_call + (s_call - price))*100, 2))} ({pct((p_call + (s_call - price))*100)})", "max_risk": "Finite (Stock Ownership)",
                    "comment": "Yield enhancement strategy.",
                    "desc": "Used to generate recurring income on existing stock holdings. It caps the upside at the strike price in exchange for the immediate premium income."
                },
                {
                    "name": "Machine 5: Assigned Short Put + Covered Call", "action": "COMBINED PUT & CALL", "strike": f"{s_put_30} / {s_call}", "expiry": exp_30, "prem": f2(round(p_call + p_put_30, 2)),
                    "max_profit": "Enhanced Yield", "max_risk": "Reduced Cost Basis",
                    "comment": "Cost basis reduction strategy.",
                    "desc": "This machine combines the premiums from multiple directions to aggressively lower the break-even point of a position, transforming market instability into measurable profit."
                }
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
