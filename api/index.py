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

# --- CONFIGURAZIONE SICURA ---
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

        # --- RAG LOGIC (Knowledge Base) ---
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_pc = pc.Index(host=INDEX_HOST)
        
        search_query = "Machine 1: Long Call Based, Machine 2: Short Put Based, Machine 3: Married Put Based, Machine 4: Covered Call Based, Machine 5: Assigned Short Put + Covered Call"
        
        emb_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:embedContent?key={GOOGLE_API_KEY}"
        res_emb = requests.post(emb_url, json={
            "model": "models/gemini-embedding-2", 
            "content": {"parts": [{"text": search_query}]}, 
            "output_dimensionality": 768
        }).json()
        
        query_v = res_emb['embedding']['values']
        search = index_pc.query(vector=query_v, top_k=15, include_metadata=True)
        context = "\n".join([m.metadata["text"] for m in search.matches])
        
        # --- PROMPT STABILE E COMPLETO ---
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GOOGLE_API_KEY}"
        
        prompt = f"""
        STRICT INSTRUCTION: Respond EXCLUSIVELY in English.
        You are the CRPM Quantitative Analyst. Analyze {ticker} (Price: {price}) using the 30-day 1-Sigma Range: {low} - {high}.
        Current IV: {iv_pct}%.

        MANDATORY TASK: 
        Apply the following 5 CRPM Machines from Massimiliano Riolfo's book to the current {ticker} data:
        1. Machine 1: Long Call Based
        2. Machine 2: Short Put Based
        3. Machine 3: Married Put Based
        4. Machine 4: Covered Call Based
        5. Machine 5: Assigned Short Put + Covered Call

        MATHEMATICAL RULES:
        - For Machine 5, the premiums from the Short Put and the Covered Call MUST BE ADDED TOGETHER to reduce the total cost basis.

        OUTPUT STRUCTURE FOR EACH MACHINE:
        ### [Machine Name]
        **Application:** (description)
        **Technical Details:** (specific strikes based on {low} and {high})
        **Rationale:** (logic from the book)

        CONTEXT FROM THE BOOK:
        {context}

        Volatility Analysis: Technical comment on {iv_pct}% IV.
        Risk Summary: One sentence on discipline and calculated risk.
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
