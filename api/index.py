import yfinance as yf
import numpy as np
import requests
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta

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
    data = request.get_json(silent=True) or {}
    user_query = data.get('query', '')
    if not user_query:
        return jsonify({"response": "Query missing."})
        
    today_str = get_now().strftime('%B %d, %Y')
    
    try:
        # BYPASS TOTALE DELL'SDK PINECONE
        # Comunichiamo direttamente con il server per evitare incompatibilità della libreria.
        clean_host = INDEX_HOST.replace("https://", "").replace("http://", "").strip("/")
        rest_url = f"https://{clean_host}/records/namespaces/__default__/search"
        
        headers = {
            "Api-Key": PINECONE_API_KEY,
            "Content-Type": "application/json",
            "X-Pinecone-Api-Version": "2024-10" # Versione esatta richiesta per i Document API
        }
        
        payload = {
            "query": {
                "inputs": {"text": user_query},
                "top_k": 5
            }
        }
        
        # Invia la richiesta direttamente al database CRPM
        search_res_raw = requests.post(rest_url, headers=headers, json=payload, timeout=10)
        
        if search_res_raw.status_code != 200:
            return jsonify({"response": f"Pinecone Connection Error [{search_res_raw.status_code}]: {search_res_raw.text}"})
            
        search_res = search_res_raw.json()
        
        # Estrazione del testo dai capitoli trovati
        context_parts = []
        hits = search_res.get('result', {}).get('hits', []) or search_res.get('hits', [])
        for h in hits:
            text_fragment = h.get('fields', {}).get('text', '')
            if text_fragment:
                context_parts.append(text_fragment)
                
        context = "\n".join(context_parts)
        
        if not context.strip():
            context = "No specific text found in the methodology book. Rely on core CRPM principles."
        
        # Generazione della risposta con l'AI di Google
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"
        
        prompt_chat = f"""TODAY IS {today_str}. 
        IDENTITY: CRPM quantitative engine based on the methodology in the book.
        CONTEXT: {context}.
        USER QUERY: {user_query}. 
        RULES: English only. Bold section titles. Aseptic tone. Always present Machine 3 and 4 options if query is about 100 shares."""
        
        res_gen_raw = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt_chat}]}]}, timeout=12)
        
        if res_gen_raw.status_code != 200:
             return jsonify({"response": f"Google AI Error [{res_gen_raw.status_code}]: {res_gen_raw.text}"})
             
        res_gen = res_gen_raw.json()
        
        if 'candidates' in res_gen and len(res_gen['candidates']) > 0:
            ai_text = res_gen['candidates'][0]['content']['parts'][0]['text']
            return jsonify({"response": ai_text})
        else:
            return jsonify({"response": "Calculation processed but no output generated. Please try again."})
            
    except requests.exceptions.Timeout:
        return jsonify({"response": "The server timed out because the analysis took too long. Please try a simpler query."})
    except Exception as e:
        return jsonify({"response": f"System Error: {str(e)}"}), 200

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
        def f2(v): return "{:.2f}".format(v)

        return jsonify({
            "ticker": ticker_sym, "company": company_name, "price": f2(price), "inv_cap": f2(inv_cap),
            "volatility": 27.0, "high": s_call, "low": s_put_30, "date": today_dt.strftime('%B %d, %Y'),
            "machines": [
                {"name": "Machine 1: Long Call Based", "action": "BUY CALL", "strike": s_call, "expiry": exp_30, "prem": f2(p_call), "max_profit": "Unlimited", "max_risk": f"${f2(p_call*100)} ({pct(p_call*100)})", "comment": "Bullish.", "desc": "Capital appreciation."},
                {"name": "Machine 2: Short Put Based", "action": "SELL PUT", "strike": s_put_30, "expiry": exp_30, "prem": f2(p_put_30), "max_profit": f"${f2(p_put_30*100)} ({pct(p_put_30*100)})", "max_risk": f"${f2(round((s_put_30 - p_put_30)*100, 2))} ({pct((s_put_30 - p_put_30)*100)})", "comment": "Income.", "desc": "Harvests volatility."},
                {"name": "Machine 3: Married Put Based", "action": "BUY PUT (+100 Shares)", "strike": s_put_180, "expiry": exp_180, "prem": f2(p_put_180), "max_profit": "UNLIMITED", "max_risk": f"${f2(round((p_put_180 + (price - s_put_180))*100, 2))} ({pct((p_put_180 + (price - s_put_180))*100)})", "comment": "Structural.", "desc": "Capital protection."},
                {"name": "Machine 4: Covered Call Based", "action": "SELL CALL (+100 Shares)", "strike": s_call, "expiry": exp_30, "prem": f2(p_call), "max_profit": f"${f2(round((p_call + (s_call - price))*100, 2))} ({pct((p_call + (s_call - price))*100)})", "max_risk": "Finite", "comment": "Yield enhancement.", "desc": "Generates income."},
                {"name": "Machine 5: Assigned Short Put + Covered Call", "action": "COMBINED", "strike": f"{s_put_30} / {s_call}", "expiry": exp_30, "prem": f2(round(p_call + p_put_30, 2)), "max_profit": "Enhanced Yield", "max_risk": "Reduced Basis", "comment": "Cost reduction.", "desc": "Profit from instability."}
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
