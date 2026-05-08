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

def get_now():
    return datetime(2026, 5, 4)

def find_nearest_strike(chain, target):
    strikes = chain['strike'].values
    return strikes[np.abs(strikes - target).argmin()]

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}
    user_query = data.get('query', '')
    today_str = get_now().strftime('%B %d, %Y')
    
    if not user_query:
        return jsonify({"response": "Query missing."})

    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_pc = pc.Index(host=INDEX_HOST)
        
        # LA SVOLTA: Usiamo la nuova API Document di Pinecone.
        # Nessun modello di embedding esterno, fa tutto il database!
        try:
            res_search = index_pc.search(
                query={
                    "inputs": {"text": user_query},
                    "top_k": 5
                }
            )
        except Exception as search_err:
            return jsonify({"response": f"Pinecone Document API Error: {str(search_err)}"})
            
        # Estrazione del contesto dai risultati nativi di Pinecone
        context_parts = []
        try:
            # Gestione sicura del formato JSON di ritorno
            if isinstance(res_search, dict):
                hits = res_search.get('result', {}).get('hits', [])
                for h in hits:
                    fields = h.get('fields', {})
                    context_parts.append(fields.get('text', str(fields)))
            else:
                hits = res_search.result.hits if hasattr(res_search, 'result') else getattr(res_search, 'hits', [])
                for h in hits:
                    fields = getattr(h, 'fields', {})
                    text_val = fields.get('text', str(fields)) if isinstance(fields, dict) else str(fields)
                    context_parts.append(text_val)
        except Exception:
            pass
            
        context = "\n".join(context_parts)
        
        # 2. Motore di Generazione della Risposta CRPM
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GOOGLE_API_KEY}"
        
        prompt_chat = f"""TODAY IS {today_str}. 
        IDENTITY: CRPM Engine. CONTEXT: {context}. QUERY: {user_query}. 
        STRICT RULES: English only. Professional tone. Section titles in bold."""
        
        res_gen_raw = requests.post(gen_url, json={"contents": [{"parts": [{"text": prompt_chat}]}]}, timeout=12)
        res_gen = res_gen_raw.json()
        
        if 'candidates' in res_gen and res_gen['candidates']:
            ai_text = res_gen['candidates'][0]['content']['parts'][0]['text']
            return jsonify({"response": ai_text})
        else:
            err_msg = res_gen.get('error', {}).get('message', 'No output generated')
            return jsonify({"response": f"Google Generation Error: {err_msg}"})
            
    except requests.exceptions.Timeout:
        return jsonify({"response": "API provider timeout. Please try a simpler query."})
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
                {"name": "Machine 1: Long Call Based", "action": "BUY CALL", "strike": s_call, "expiry": exp_30, "prem": f2(p_call), "max_profit": "Unlimited", "max_risk": f"${f2(p_call*100)} ({pct(p_call*100)})", "comment": "Bullish momentum.", "desc": "Capital appreciation."},
                {"name": "Machine 2: Short Put Based", "action": "SELL PUT", "strike": s_put_30, "expiry": exp_30, "prem": f2(p_put_30), "max_profit": f"${f2(p_put_30*100)} ({pct(p_put_30*100)})", "max_risk": f"${f2(round((s_put_30 - p_put_30)*100, 2))} ({pct((s_put_30 - p_put_30)*100)})", "comment": "Income.", "desc": "Harvests volatility."},
                {"name": "Machine 3: Married Put Based", "action": "BUY PUT (+100 Shares)", "strike": s_put_180, "expiry": exp_180, "prem": f2(p_put_180), "max_profit": "UNLIMITED", "max_risk": f"${f2(round((p_put_180 + (price - s_put_180))*100, 2))} ({pct((p_put_180 + (price - s_put_180))*100)})", "comment": "Structural hedging.", "desc": "Long-term protection."},
                {"name": "Machine 4: Covered Call Based", "action": "SELL CALL (+100 Shares)", "strike": s_call, "expiry": exp_30, "prem": f2(p_call), "max_profit": f"${f2(round((p_call + (s_call - price))*100, 2))} ({pct((p_call + (s_call - price))*100)})", "max_risk": "Finite (Stock Ownership)", "comment": "Yield enhancement.", "desc": "Generates income."},
                {"name": "Machine 5: Assigned Short Put + Covered Call", "action": "COMBINED PUT & CALL", "strike": f"{s_put_30} / {s_call}", "expiry": exp_30, "prem": f2(round(p_call + p_put_30, 2)), "max_profit": "Enhanced Yield", "max_risk": "Reduced Cost Basis", "comment": "Cost basis reduction.", "desc": "Profit from instability."}
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app
