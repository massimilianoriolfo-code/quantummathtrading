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
        current_price = round(price, 2)

        # --- KNOWLEDGE RETRIEVAL ---
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_pc = pc.Index(host=INDEX_HOST)
        
        # Query specifica per forzare il recupero delle 5 macchine CRPM
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
        
        # --- RIGID CRPM PROMPT ---
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GOOGLE_API_KEY}"
        
        prompt = f"""
        STRICT INSTRUCTION: Respond EXCLUSIVELY in English. 
        Tone: Neutral, Clinical, Quantitative. NO author names. 
        NO asterisks (*). Use professional headings.

        DATA: {ticker} @ {current_price} | 30-day 1-Sigma: {low} - {high} | IV: {iv_pct}%

        MANDATORY STRUCTURE:
        1. Volatility Analysis: Technical comment on {iv_pct}% IV and market context for {ticker}.
        
        2. You MUST analyze EXACTLY these 5 Machines from the CRPM methodology:
        
        ### Machine 1: Long Call Based
        **Application:** (Setup for {ticker})
        **Technical Details:** (Strike selection near {high}. Round strikes to 2 decimals)
        **Rationale:** (Quantitative logic)

        ### Machine 2: Short Put Based
        **Application:** (Setup for {ticker})
        **Technical Details:** (Strike selection near {low}. Round strikes to 2 decimals)
        **Rationale:** (Quantitative logic)

        ### Machine 3: Married Put Based
        **Application:** (Protection setup for {ticker})
        **Technical Details:** (Floor placement based on {low})
        **Rationale:** (Quantitative logic)

        ### Machine 4: Covered Call Based
        **Application:** (Income setup for {ticker})
        **Technical Details:** (Strike selection near {high})
        **Rationale:** (Quantitative logic)

        ### Machine 5: Assigned Short Put + Covered Call
        **Application:** (Wheel transition setup)
        **Technical Details:** (MANDATORY: Explain that Put premium + Call premium are ADDED together to reduce net cost basis)
        **Rationale:** (Quantitative logic)

        Risk Summary: One sentence on discipline and calculated risk.

        CONTEXT FROM THE BOOK:
        {context}
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
