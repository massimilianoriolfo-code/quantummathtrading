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
        
        # --- 1. LIVELLO: CALCOLO MATEMATICO RIGIDO (Dati yfinance) ---
        expirations = stock.options
        target_date = datetime.now() + timedelta(days=30)
        closest_exp = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target_date).days))
        opt_chain = stock.option_chain(closest_exp)
        
        iv_val = (opt_chain.calls.iloc[(opt_chain.calls['strike'] - price).abs().idxmin()]['impliedVolatility'] + 
                  opt_chain.puts.iloc[(opt_chain.puts['strike'] - price).abs().idxmin()]['impliedVolatility']) / 2
        
        move = price * iv_val * np.sqrt(30 / 365)
        high, low = round(price + move, 2), round(price - move, 2)
        iv_pct = round(iv_val * 100, 2)

        # --- 2. LIVELLO: ANCORAGGIO AL TESTO (Retrieval Pinecone) ---
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_pc = pc.Index(host=INDEX_HOST)
        
        search_query = "Detailed technical explanation of CRPM Machines 8.1 to 8.6: Long Call, Short Put, Married Put, Covered Call, Assigned Short Put + Covered Call"
        
        emb_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:embedContent?key={GOOGLE_API_KEY}"
        res_emb = requests.post(emb_url, json={
            "model": "models/gemini-embedding-2", 
            "content": {"parts": [{"text": search_query}]}, 
            "output_dimensionality": 768
        }).json()
        
        query_v = res_emb['embedding']['values']
        search = index_pc.query(vector=query_v, top_k=15, include_metadata=True)
        context = "\n".join([m.metadata["text"] for m in search.matches])
        
        # --- 3. LIVELLO: FILTRO INGEGNERISTICO (Prompt Blindato) ---
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GOOGLE_API_KEY}"
        
        prompt = f"""
        STRICT INSTRUCTION: Respond EXCLUSIVELY in English. Use a dry, technical, engineering-style tone. 
        You are the CRPM Execution Engine for Massimiliano Riolfo. 
        
        TARGET ANALYSIS: {ticker} @ {price} | 30d 1-Sigma Cone: [{low} - {high}] | IV: {iv_pct}%

        CORE RULES FOR ALL STRATEGIES:
        - NEVER deviate from the mathematical logic of the book. 
        - Refer specifically to Paragraphs 8.1, 8.2, 8.3, 8.4, and 8.6 for strategy definitions.
        - SHORT OPTIONS (Machine 2, 4, 5): Premiums are ALWAYS positive cash inflows (credits) that reduce risk or cost basis.
        - MACHINE 5 (Para 8.6): You MUST mathematically ADD the premium from the Short Put and the Covered Call to reduce the cost basis. 
        - MACHINE 3 (Para 8.3): Premium is a DEBIT (Cost of Insurance) that establishes a hard price floor.

        TASK: Describe the operational setup for {ticker} using the 5 CRPM Machines:
        1. Machine 1: Long Call Based (Para 8.1)
        2. Machine 2: Short Put Based (Para 8.2)
        3. Machine 3: Married Put Based (Para 8.3)
        4. Machine 4: Covered Call Based (Para 8.4)
        5. Machine 5: Assigned Short Put + Covered Call (Para 8.6)

        NO conversational filler. NO financial advice. ONLY technical execution logic based on the provided context.

        CONTEXT FROM THE BOOK:
        {context}
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
