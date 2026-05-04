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

@app.route('/api/index', methods=['POST', 'GET'])
def index():
    data = request.get_json(silent=True) or {}
    t = data.get('ticker') or request.args.get('ticker')
    if not t: return jsonify({"error": "Ticker missing"}), 400
    ticker_sym = t.upper()

    try:
        stock = yf.Ticker(ticker_sym)
        # Recupero Nome Azienda e Prezzo
        company_name = stock.info.get('longName', ticker_sym)
        price = stock.fast_info['last_price']
        
        # --- GESTIONE VOLATILITÀ (FALLBACK SE 0) ---
        expirations = stock.options
        target_date = datetime.now() + timedelta(days=30)
        closest_exp = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target_date).days))
        opt_chain = stock.option_chain(closest_exp)
        
        iv_val = (opt_chain.calls.iloc[(opt_chain.calls['strike'] - price).abs().idxmin()]['impliedVolatility'] + 
                  opt_chain.puts.iloc[(opt_chain.puts['strike'] - price).abs().idxmin()]['impliedVolatility']) / 2
        
        if iv_val <= 0: # Fallback su volatilità storica se mercato chiuso
            hist = stock.history(period="1mo")
            iv_val = np.log(hist['Close'] / hist['Close'].shift(1)).std() * np.sqrt(252) if not hist.empty else 0.25

        # --- MOTORE QUANTITATIVO ---
        move = price * iv_val * np.sqrt(30 / 365)
        high, low = round(price + move, 2), round(price - move, 2)
        
        # --- PARAMETRI MACHINE 3 (LIBRO) ---
        m3_strike = round(price * 1.02, 2) # ITM
        m3_expiry = (datetime.now() + timedelta(days=180)).strftime('%B %Y')
        est_premium = price * 0.08 # Stima premio 6 mesi
        max_risk_monetary = round((est_premium - (m3_strike - price)) * 100, 2)
        max_risk_pct = round((max_risk_monetary / (price * 100)) * 100, 2)

        # --- RAG LOGIC ---
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_pc = pc.Index(host=INDEX_HOST)
        search_query = "Technical definitions: Machine 3 Married Put ITM 6 months unlimited profit"
        
        res_emb = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:embedContent?key={GOOGLE_API_KEY}", 
            json={"model": "models/gemini-embedding-2", "content": {"parts": [{"text": search_query}]}, "output_dimensionality": 768}).json()
        
        query_v = res_emb['embedding']['values']
        search = index_pc.query(vector=query_v, top_k=10, include_metadata=True)
        context = "\n".join([m.metadata["text"] for m in search.matches])
        
        # --- PROMPT AGGIORNATO ---
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={GOOGLE_API_KEY}"
        prompt = f"""
        STRICT INSTRUCTION: Respond EXCLUSIVELY in English. Tone: Clinical and Quantitative.
        NO names. Refer only to "the methodology" or "the model". No asterisks or hashes.

        DATA: {company_name} ({ticker_sym}) @ {round(price, 2)}
        30-day 1-Sigma: {low} - {high} | IV: {round(iv_val*100,2)}%
        Machine 3 Params: Strike {m3_strike} ITM, Expiry {m3_expiry}, Max Risk {max_risk_pct}%.

        MANDATORY STRUCTURE:
        Volatility Analysis: (Technical comment on IV and price boundaries)

        Machine 1: Long Call Based
        Application: Bullish
        Technical Details: Strike near {high}
        Rationale: Quantitative upside exposure.

        Machine 2: Short Put Based
        Application: Neutral-Bullish
        Technical Details: Strike near {low}
        Rationale: Volatility harvesting.

        Machine 3: Married Put Based
        Application: Strategic Protection for underlying shares.
        Technical Details: Buy Put at {m3_strike} with expiry {m3_expiry}.
        Rationale: As per the book, uses ITM strike and 6+ months duration to minimize Theta decay. 
        Max Risk: {max_risk_pct}% of capital. Max Profit: UNLIMITED.

        Machine 4: Covered Call Based
        Application: Yield generation.
        Technical Details: Sell Call at {high}.
        Rationale: Disciplined profit harvesting at upper boundary.

        Machine 5: Assigned Short Put + Covered Call
        Application: Cost basis reduction.
        Technical Details: Sum of premiums from Put and Call.
        Rationale: Building measurable returns through market instability.

        Risk Summary: Investing is transformed from an intuitive act into a disciplined process.
        LEGAL: This is a mathematical model, not financial advice.
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
