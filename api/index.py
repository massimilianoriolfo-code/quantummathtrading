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

# --- CONFIGURAZIONE ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_HOST = os.getenv("INDEX_HOST")

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    data = request.get_json(silent=True) or {}
    t = data.get('ticker') or request.args.get('ticker')
    if not t: return jsonify({"error": "Ticker missing"}), 400
    ticker = t.upper()

    try:
        stock = yf.Ticker(ticker)
        price = stock.fast_info['last_price']
        
        # --- MOTORE QUANTITATIVO ---
        expirations = stock.options
        target_date = datetime.now() + timedelta(days=30)
        closest_exp = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target_date).days))
        opt_chain = stock.option_chain(closest_exp)
        
        iv_val = (opt_chain.calls.iloc[(opt_chain.calls['strike'] - price).abs().idxmin()]['impliedVolatility'] + 
                  opt_chain.puts.iloc[(opt_chain.puts['strike'] - price).abs().idxmin()]['impliedVolatility']) / 2
        
        move = price * iv_val * np.sqrt(30 / 365)
        high, low = round(price + move, 2), round(price - move, 2)
        iv_pct = round(iv_val * 100, 2)
        current_price = round(price, 2)

        # --- KNOWLEDGE RETRIEVAL ---
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_pc = pc.Index(host=INDEX_HOST)
        search_query = "Machine 1: Long Call Based, Machine 2: Short Put Based, Machine 3: Married Put Based, Machine 4: Covered Call Based, Machine 5: Assigned Short Put + Covered Call"
        
        emb_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:embedContent?key={GOOGLE_API_KEY}"
        res_emb = requests.post(emb_url, json={"model": "models/gemini-embedding-2", "content": {"parts": [{"text": search_query}]}, "output_dimensionality": 768}).json()
        query_v = res_emb['embedding']['values']
        search = index_pc.query(vector=query_v, top_k=15, include_metadata=True)
        context = "\n".join([m.metadata["text"] for m in search.matches])
        
        # --- PROMPT DEFINITIVO (LOGICA + ESTETICA) ---
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GOOGLE_API_KEY}"
        
        prompt = f"""
        STRICT INSTRUCTION: Respond EXCLUSIVELY in English. Use a technical and quantitative tone.
        NEVER mention any author names. Refer only to "the methodology" or "the model".
        DO NOT use any asterisks (*) or hash symbols (#).

        You are the CRPM Quantitative Analyst. Analyze {ticker} @ {current_price}.
        30-day 1-Sigma Range: {low} - {high}.
        Current IV: {iv_pct}%.

        MANDATORY FORMATTING:
        - Use ONLY standard bold text (double stars will be stripped, so use plain CAPS or simple Bold headers).
        - Use _italics_ for these labels: _Application:_, _Technical Details:_, _Rationale:_.
        - NO # symbols. Titles must be plain text.

        TASK: Apply EXACTLY these 5 Machines:
        1. Machine 1: Long Call Based
        2. Machine 2: Short Put Based
        3. Machine 3: Married Put Based
        4. Machine 4: Covered Call Based
        5. Machine 5: Assigned Short Put + Covered Call (RULE: Put premium + Call premium are ADDED as inflows).

        For Technical Details, use the nearest tradable strike (integer or .5) for {low} and {high}.

        CONTEXT FROM THE BOOK:
        {context}

        FINAL DISCLAIMER:
        This analysis is based on mathematical models and does not constitute financial advice. All trading involves risk.
        """
        
        res_gen = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt}]}]}).json()
        ai_analysis_result = res_gen['candidates'][0]['content']['parts'][0]['text']

        return jsonify({
            "ticker": ticker,
            "price": current_price,
            "volatility": iv_pct,
            "high": high,
            "low": low,
            "ai_analysis": ai_analysis_result,
            "date": "2026-05-01"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
