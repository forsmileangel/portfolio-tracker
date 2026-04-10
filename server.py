#!/usr/bin/env python3
"""
Portfolio Tracker Backend
- Static file server (local dev only)
- GET  /proxy?url=...         → CORS proxy for Yahoo Finance chart
- GET  /yfundamentals?symbol= → PE/FPE/PEG/EPS via yfinance
- POST /update-symbols        → 更新 GitHub repo 的 data/symbols.json
"""
import http.server
import urllib.request
import urllib.parse
import json
import os
import threading

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO  = 'forsmileangel/portfolio-tracker'
SYMBOLS_PATH = 'data/symbols.json'
CACHE_PATH   = 'data/cache.json'

PORT = int(os.environ.get('PORT', 3000))
DIR  = os.path.dirname(os.path.abspath(__file__))

_yf_cache = {}
_yf_lock  = threading.Lock()

def get_fundamentals(symbol):
    with _yf_lock:
        if symbol in _yf_cache:
            return _yf_cache[symbol]
    try:
        import yfinance as yf
        import pandas as pd
        t    = yf.Ticker(symbol)
        info = t.info

        # EPS 本季 / 下季預估
        eps_cur_q  = None
        eps_next_q = None
        try:
            ee = t.earnings_estimate
            if ee is not None:
                if '0q' in ee.index:
                    eps_cur_q  = float(ee.loc['0q',  'avg'])
                if '+1q' in ee.index:
                    eps_next_q = float(ee.loc['+1q', 'avg'])
        except Exception:
            pass

        # Revenue Growth FWD (next year)
        rev_fwd = None
        try:
            re = t.revenue_estimate
            if re is not None and '+1y' in re.index:
                rev_fwd = float(re.loc['+1y', 'growth'])
        except Exception:
            pass

        # 歷史平均 PE (近 5 年季頻)
        hist_avg_pe = None
        try:
            hist = t.history(period='5y', interval='3mo')['Close']
            hist.index = hist.index.tz_localize(None)
            fin = t.quarterly_financials
            for row in ['Diluted EPS', 'Basic EPS', 'EPS']:
                if row in fin.index:
                    eps_s = fin.loc[row].sort_index()
                    eps_s.index = pd.to_datetime(eps_s.index).tz_localize(None)
                    pe_list = []
                    for date, price in hist.items():
                        ttm = eps_s[eps_s.index <= date].head(4).sum()
                        if ttm > 0:
                            pe_list.append(price / ttm)
                    if pe_list:
                        hist_avg_pe = round(sum(pe_list) / len(pe_list), 2)
                    break
        except Exception:
            pass

        result = {
            'pe':           info.get('trailingPE'),
            'fpe':          info.get('forwardPE'),
            'peg':          info.get('trailingPegRatio'),
            'ps':           info.get('priceToSalesTrailing12Months'),
            'pb':           info.get('priceToBook'),
            'rev_yoy':      info.get('revenueGrowth'),
            'rev_fwd':      rev_fwd,
            'hist_avg_pe':  hist_avg_pe,
            'eps_ttm':      info.get('trailingEps'),
            'eps_cur_q':    eps_cur_q,
            'eps_next_q2':  eps_next_q,
            'eps_cur_y':    info.get('epsCurrentYear'),
            'eps_next_y':   info.get('epsForward'),
        }
    except Exception as e:
        result = {'error': str(e)}
    with _yf_lock:
        _yf_cache[symbol] = result
    return result


def github_update_symbols(symbols):
    import base64
    api_url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{SYMBOLS_PATH}'
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json',
        'User-Agent': 'portfolio-tracker-backend',
    }
    req = urllib.request.Request(api_url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        current = json.loads(r.read())
    sha = current['sha']
    content = base64.b64encode(json.dumps(symbols, indent=2, ensure_ascii=False).encode()).decode()
    body = json.dumps({'message': 'update symbols', 'content': content, 'sha': sha}).encode()
    req = urllib.request.Request(api_url, data=body, headers=headers, method='PUT')
    with urllib.request.urlopen(req, timeout=15) as r:
        r.read()


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/proxy':
            self._proxy(parsed)
        elif parsed.path == '/yfundamentals':
            self._fundamentals(parsed)
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/update-symbols':
            self._update_symbols()
        else:
            self.send_error(404)

    def _update_symbols(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            symbols = json.loads(self.rfile.read(length))
            if not GITHUB_TOKEN:
                self._send_json({'error': 'GITHUB_TOKEN not configured'}, 500); return
            github_update_symbols(symbols)
            self._send_json({'ok': True})
        except Exception as e:
            self._send_json({'error': str(e)}, 500)

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(body)

    def _proxy(self, parsed):
        params = urllib.parse.parse_qs(parsed.query)
        target = params.get('url', [''])[0]
        if not target:
            self.send_error(400, 'Missing url parameter'); return
        try:
            req = urllib.request.Request(target, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
                              ' AppleWebKit/537.36 (KHTML, like Gecko)'
                              ' Chrome/124.0 Safari/537.36',
                'Accept': 'application/json, */*',
                'Accept-Language': 'en-US,en;q=0.9',
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_error(502, str(e))

    def _fundamentals(self, parsed):
        params = urllib.parse.parse_qs(parsed.query)
        symbol = params.get('symbol', [''])[0].upper()
        if not symbol:
            self.send_error(400, 'Missing symbol parameter'); return
        self._send_json(get_fundamentals(symbol))

    def log_message(self, fmt, *args):
        pass

if __name__ == '__main__':
    with http.server.ThreadingHTTPServer(('0.0.0.0', PORT), Handler) as srv:
        print(f'Server running: http://localhost:{PORT}')
        srv.serve_forever()
