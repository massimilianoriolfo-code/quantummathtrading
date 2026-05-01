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
        
        # --- MOTORE QUANTITATIVO (Dati Oggettivi) ---
        expirations = stock.options
        target_date = datetime.now() + timedelta(days=30)
        closest_exp = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target_date).days))
        opt_chain = stock.option_chain(closest_exp)
        
        iv_val = (opt_chain.calls.iloc[(opt_chain.calls['strike'] - price).abs().idxmin()]['impliedVolatility'] + 
                  opt_chain.puts.iloc[(opt_chain.puts['strike'] - price).abs().idxmin()]['impliedVolatility']) / 2
        
        move = price * iv_val * np.sqrt(30 / 365)
        high, low = round(price + move, 2), round(price - move, 2)
        iv_pct = round(iv_val * 100, 2)
        curr_p = round(price, 2)

        # --- RAG LOGIC ---
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_pc = pc.Index(host=INDEX_HOST)
        search_query = "Technical definitions: Machine 1 to 5, Long Call, Short Put, Married Put, Covered Call, Assigned Short Put + Covered Call"
        
        res_emb = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:embedContent?key={GOOGLE_API_KEY}", 
            json={"model": "models/gemini-embedding-2", "content": {"parts": [{"text": search_query}]}, "output_dimensionality": 768}).json()
        
        query_v = res_emb['embedding']['values']
        search = index_pc.query(vector=query_v, top_k=15, include_metadata=True)
        context = "\n".join([m.metadata["text"] for m in search.matches])
        
        # --- PROMPT INVIOLABILE ---
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GOOGLE_API_KEY}"
        
        prompt = f"""
        STRICT INSTRUCTION: Respond EXCLUSIVELY in English. Tone: Clinical and Quantitative.
        NO names. Refer only to "the methodology" or "the model".
        DO NOT use asterisks (*). No hash symbols (#).

        DATA: {ticker} @ {curr_p} | 30-day 1-Sigma: {low} - {high} | IV: {iv_pct}%

        MANDATORY MACHINE LOGIC:
        1. Machine 1: Long Call Based. (Action: BUY Call).
        2. Machine 2: Short Put Based. (Action: SELL Put).
        3. Machine 3: Married Put Based. (Action: Long Stock + BUY Put Option. This is a COST for insurance).
        4. Machine 4: Covered Call Based. (Action: Long Stock + SELL Call).
        5. Machine 5: Assigned Short Put + Covered Call. (Action: Combined premiums from Put and Call are ADDED to reduce cost basis).

        For Technical Details, select strikes as integers or .5 based on {low} and {high}.

        OUTPUT STRUCTURE:
        Volatility Analysis: (Technical comment)

        Machine 1: Long Call Based
        Application: 
        Technical Details: 
        Rationale: 

        Machine 2: Short Put Based
        Application: 
        Technical Details: 
        Rationale: 

        Machine 3: Married Put Based
        Application: (Buying protection for the underlying)
        Technical Details: (Buying Put at nearest strike to {low})
        Rationale: 

        Machine 4: Covered Call Based
        Application: 
        Technical Details:_ (Selling Call at nearest strike to {high})
        Rationale: 

        Machine 5: Assigned Short Put + Covered Call**
        Application: 
        Technical Details: (Explain the sum of premiums received)
        Rationale: 

        Risk Summary:** (One sentence)

        IMPORTANT LEGAL NOTE:
        This analysis is based on mathematical models and does not constitute financial advice. All trading involves risk.
        """
        
        res_gen = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt}]}]}).json()
        ai_analysis_result = res_gen['candidates'][0]['content']['parts'][0]['text']

        return jsonify({
            "ticker": ticker, "price": curr_p, "volatility": iv_pct, "high": high, "low": low,
            "ai_analysis": ai_analysis_result, "date": "2026-05-01"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
