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

# --- CONFIGURATION ---
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
        
        # --- QUANTITATIVE ENGINE ---
        expirations = stock.options
        target_date = datetime.now() + timedelta(days=30)
        closest_exp = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target_date).days))
        opt_chain = stock.option_chain(closest_exp)
        
        iv_val = (opt_chain.calls.iloc[(opt_chain.calls['strike'] - price).abs().idxmin()]['impliedVolatility'] + 
                  opt_chain.puts.iloc[(opt_chain.puts['strike'] - price).abs().idxmin()]['impliedVolatility']) / 2
        
        move = price * iv_val * np.sqrt(30 / 365)
        high, low = round(price + move, 2), round(price - move, 2)
        iv_pct = round(iv_val * 100, 2)

        # --- RAG LOGIC ---
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_pc = pc.Index(host=INDEX_HOST)
        
        search_query = "Long Call Based, Short Put Based, Married Put Based, Covered Call Based, Assigned Short Put + Covered Call"
        
        emb_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:embedContent?key={GOOGLE_API_KEY}"
        res_emb = requests.post(emb_url, json={
            "model": "models/gemini-embedding-2", 
            "content": {"parts": [{"text": search_query}]}, 
            "output_dimensionality": 768
        }).json()
        
        query_v = res_emb['embedding']['values']
        search = index_pc.query(vector=query_v, top_k=15, include_metadata=True)
        context_text = "\n".join([m.metadata["text"] for m in search.matches])
        
        # --- PROMPT QUANTITATIVO AVANZATO (Corretto) ---
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GOOGLE_API_KEY}"
        
        # Usiamo variabili pulite senza parentesi graffe extra che mandano in crash Python
        prompt = f"""
STRICT INSTRUCTION: Respond EXCLUSIVELY in English. Use a technical, engineering-style tone.
Act as the CRPM Execution Engine for Massimiliano Riolfo. 

ANALYSIS TARGET: {ticker} @ {price}
30-DAY PARAMETERS: 1-Sigma Range [{low} - {high}] | IV: {iv_pct}%

Using the methodology from Chapter 8 (Calculated Risk and Profit Machines), generate an operational setup for each machine:

1. Machine 1: Long Call Based (Para 8.1)
   - Target Strike: Based on {high}. Discuss delta exposure and risk of total premium loss.
2. Machine 2: Short Put Based (Para 8.2)
   - Target Strike: Safety margin relative to {low}. Analyze the "Calculated Profit" vs assignment risk.
3. Machine 3: Married Put Based (Para 8.3)
   - Setup: Synthetic floor placement. Calculate the "Cost of Insurance" for the {ticker} position.
4. Machine 4: Covered Call Based (Para 8.4)
   - Setup: Income generation. Strike selection at the upper {high} boundary to maximize Theta decay.
5. Machine 5: Assigned Short Put + Covered Call (Para 8.6)
   - Strategy: The "Wheel" transition. Managing cost basis after assignment and strike selection for the Call leg.

MANDATORY: 
- Refer to price levels {low} and {high} as hard boundaries for strike selection.
- Maintain focus on "Calculated Risk" and "Profit Machines" as disciplined processes, not guesses.
- NO general advice. ONLY technical execution logic.

CONTEXT FROM BOOK:
{context_text}
"""
        
        res_gen = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt}]}]}).json()
        ai_analysis_result = res_gen['candidates'][0]['content']['parts'][0]['text']

        return jsonify({
            "ticker": ticker,
            "price": round(price, 2),
            "volatility": iv_pct,
            "high": high,
            "low": low,
            "ai_analysis": ai_analysis_result,
            "date": "2026-05-01"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
