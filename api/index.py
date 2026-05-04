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

# Funzione per ottenere la data odierna formattata
def get_now():
    return datetime.now()

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
        prompt_chat = f"""TODAY IS {today_str}. 
        You are the expert Assistant for 'The Essence of Quantitative Math Trading with Options'.
        BOOK CONTEXT: {context}
        USER QUESTION: {user_query}
        
        INSTRUCTIONS:
        - Reference the current date ({today_str}) for any calculation.
        - Explain Machine 3 (Married Put) as: Long Stock + Put Option.
        - Machine 3 expiry must be at least 6 months from today, so around { (get_now() + timedelta(days=180)).strftime('%B %Y') }.
        - Maintain a professional, quantitative tone."""
        
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
    today_str = today_dt.strftime('%B %d, %Y')

    try:
        stock = yf.Ticker(ticker_sym)
        company_name = stock.info.get('longName', ticker_sym)
        price = stock.fast_info['last_price']
        
        # Logica Volatilità
        expirations = stock.options
        iv_val = 0.25 # Fallback
        if expirations:
            target_30 = today_dt + timedelta(days=30)
            closest_exp = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target_30).days))
            opt_chain = stock.option_chain(closest_exp)
            iv_val = (opt_chain.calls.iloc[(opt_chain.calls['strike'] - price).abs().idxmin()]['impliedVolatility'] + 
                      opt_chain.puts.iloc[(opt_chain.puts['strike'] - price).abs().idxmin()]['impliedVolatility']) / 2

        # Analisi Tattica
        move = price * iv_val * np.sqrt(30 / 365)
        high, low = round(price + move, 2), round(price - move, 2)
        exp_30_str = (today_dt + timedelta(days=30)).strftime('%B %d, %Y')
        
        # Machine 3 Strategica
        m3_strike = round(price * 1.02, 2)
        m3_expiry_dt = today_dt + timedelta(days=180)
        m3_expiry_str = m3_expiry_dt.strftime('%B %Y')
        max_risk_pct = round(((price * 0.08 - (m3_strike - price)) / price) * 100, 2)

        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GOOGLE_API_KEY}"
        prompt = f"""STRICT: TODAY IS {today_str}. All analysis must use the year 2026.
        DATA: {company_name} @ {round(price, 2)} | IV: {round(iv_val*100,2)}%
        
        1. Machine 1: Long Call. Target: {high}. Expiry: {exp_30_str}.
        2. Machine 2: Short Put. Target: {low}. Expiry: {exp_30_str}.
        3. Machine 3: Married Put. Strike: {m3_strike} (ITM). Expiry: {m3_expiry_str}. Profit: UNLIMITED. Risk: {max_risk_pct}%.
        4. Machine 4: Covered Call. Strike: {high}. Expiry: {exp_30_str}.
        5. Machine 5: Combined Premiums.
        
        Format as technical tables. Ensure NO mentions of 2023 or other past years."""
        
        res_gen = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt}]}]}).json()
        ai_analysis_result = res_gen['candidates'][0]['content']['parts'][0]['text']

        return jsonify({
            "ticker": ticker_sym, "company": company_name, "price": round(price, 2), 
            "volatility": round(iv_val*100,2), "high": high, "low": low,
            "ai_analysis": ai_analysis_result, "date": today_str
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
