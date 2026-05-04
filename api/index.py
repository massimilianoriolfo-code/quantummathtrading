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

# --- NUOVO ENDPOINT PER LA CHAT LIBERA CON IL LIBRO ---
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_query = data.get('query')
    if not user_query: return jsonify({"error": "Query missing"}), 400
    
    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_pc = pc.Index(host=INDEX_HOST)
        
        # Embedding della domanda
        res_emb = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:embedContent?key={GOOGLE_API_KEY}", 
            json={"model": "models/gemini-embedding-2", "content": {"parts": [{"text": user_query}]}, "output_dimensionality": 768}).json()
        query_v = res_emb['embedding']['values']
        
        # Recupero contesto dal libro
        search = index_pc.query(vector=query_v, top_k=5, include_metadata=True)
        context = "\n".join([m.metadata["text"] for m in search.matches])
        
        # Generazione risposta citando il libro
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GOOGLE_API_KEY}"
        prompt_chat = f"""You are the Assistant for 'The Essence of Quantitative Math Trading with Options'. 
        Based ONLY on this context: {context}
        Answer the user: {user_query}. 
        Cite chapters if mentioned. Tone: Professional. No financial advice."""
        
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

    try:
        stock = yf.Ticker(ticker_sym)
        company_name = stock.info.get('longName', ticker_sym)
        price = stock.fast_info['last_price']
        
        expirations = stock.options
        target_date = datetime.now() + timedelta(days=30)
        closest_exp = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target_date).days))
        opt_chain = stock.option_chain(closest_exp)
        
        iv_val = (opt_chain.calls.iloc[(opt_chain.calls['strike'] - price).abs().idxmin()]['impliedVolatility'] + 
                  opt_chain.puts.iloc[(opt_chain.puts['strike'] - price).abs().idxmin()]['impliedVolatility']) / 2
        
        if iv_val <= 0:
            hist = stock.history(period="1mo")
            iv_val = np.log(hist['Close'] / hist['Close'].shift(1)).std() * np.sqrt(252) if not hist.empty else 0.25

        move = price * iv_val * np.sqrt(30 / 365)
        high, low = round(price + move, 2), round(price - move, 2)
        
        m3_strike = round(price * 1.02, 2)
        m3_expiry = (datetime.now() + timedelta(days=180)).strftime('%B %Y')
        est_premium = price * 0.08
        max_risk_monetary = round((est_premium - (m3_strike - price)) * 100, 2)
        max_risk_pct = round((max_risk_monetary / (price * 100)) * 100, 2)

        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GOOGLE_API_KEY}"
        
        # PROMPT STRUTTURATO PER TABELLE TECNICHE
        prompt = f"""
        STRICT INSTRUCTION: Respond EXCLUSIVELY in English. Use clinical, quantitative tone. No asterisks.
        FORMAT: Provide a structured technical summary for each Machine (1-5).
        
        DATA: {company_name} ({ticker_sym}) @ {round(price, 2)} | 1-Sigma: {low}-{high}
        
        For each Machine, list:
        - TARGET: (Bullish/Neutral/Protection)
        - TECHNICALS: (Strike and Expiry)
        - RISK PROFILE: (Finite or Unbounded)
        - PROFIT PROFILE: (Finite or Unbounded)
        - RATIONALE: (Why per CRPM methodology)

        Machine 3 must use {m3_strike} strike and {m3_expiry} expiry. Others use 30-day targets.
        """
        
        res_gen = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt}]}]}).json()
        ai_analysis_result = res_gen['candidates'][0]['content']['parts'][0]['text']

        return jsonify({
            "ticker": ticker_sym, "company": company_name, "price": round(price, 2), 
            "volatility": round(iv_val*100,2), "high": high, "low": low,
            "ai_analysis": ai_analysis_result, "m3_risk_pct": max_risk_pct, "date": "2026-05-04"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
