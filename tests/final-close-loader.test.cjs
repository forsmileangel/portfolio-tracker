const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'portfolio-tracker-v15.html'), 'utf8');
function section(start, end) {
    const from = html.indexOf(start);
    const to = html.indexOf(end, from);
    assert.ok(from >= 0 && to > from, `App section found: ${start}`);
    return html.slice(from, to);
}
const appCode = section('const MARKET_CALENDARS =', 'function _marketPortfolioDayStatus(')
    + section('let _finalCloseData =', 'function _exactFundamentalCloseForDate(');
const payload = (generatedAt = '2026-09-26T01:00:00Z') => ({ generatedAt, symbols: {} });
const response = data => ({ ok: true, status: 200, json: async () => data });

function app(handler, location = { protocol: 'https:', hostname: 'forsmileangel.github.io' }) {
    let now = Date.parse('2026-09-26T01:00:00Z');
    const calls = [], errors = [];
    const context = vm.createContext({
        location, AbortController, setTimeout, clearTimeout,
        Date: class extends Date {
            constructor(...args) { super(...(args.length ? args : [now])); }
            static now() { return now; }
        },
        localStorage: { getItem: () => null }, STORAGE_KEYS: { adhocClosures: 'unused' },
        _recordAppError: (...args) => errors.push(args),
        fetch: async (url, options) => {
            calls.push({ url, options });
            return handler(url, options);
        }
    });
    vm.runInContext(appCode, context);
    return {
        context, calls, errors,
        load: force => context._loadFinalCloseData(force),
        run: code => vm.runInContext(code, context),
        advance: ms => { now += ms; }
    };
}

test('all inline app scripts compile and the visible version matches APP_VERSION', () => {
    for (const [, attrs, code] of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)) {
        if (!/\bsrc\s*=|type\s*=\s*["']application\//i.test(attrs)) new vm.Script(code);
    }
    const versions = [...html.matchAll(/const APP_VERSION\s*=\s*'(v15\.\d+)';/g)];
    assert.equal(versions.length, 1);
    const version = versions[0];
    assert.equal(version[1], 'v15.983');
    const escaped = version[1].replace(/\./g, '\\.');
    assert.match(html, new RegExp(`pointer-events:none;">${escaped}</div>`));
    assert.match(html, new RegExp(`^\\s*${escaped} - `, 'm'));
});

test('latest repository data uses one request for concurrent loads and the 3-minute TTL', async () => {
    const data = payload();
    const a = app(() => response(data));
    const [first, second] = await Promise.all([a.load(), a.load()]);
    assert.equal(first, data);
    assert.equal(second, data);
    assert.equal(a.calls.length, 1);
    assert.match(a.calls[0].url, /^https:\/\/api\.github\.com\/repos\/forsmileangel\/portfolio-tracker\/contents\/data\/final-closes\.json\?ref=main$/);
    assert.equal(a.calls[0].options.headers.Accept, 'application/vnd.github.raw+json');
    assert.equal(a.calls[0].options.cache, 'no-store');
    a.advance(179999);
    await a.load();
    assert.equal(a.calls.length, 1);
    a.advance(1);
    await a.load();
    assert.equal(a.calls.length, 2);
});

test('manual refresh bypasses TTL but an older response cannot replace newer data', async () => {
    let data = payload();
    const a = app(() => response(data));
    const first = await a.load();
    data = payload('2026-09-24T01:00:00Z');
    assert.equal(await a.load(true), first);
    assert.equal(a.calls.length, 2);
    data = payload('2026-09-26T02:00:00Z');
    assert.equal(await a.load(true), data);
});

test('API rate limit falls back to raw repository data', async () => {
    const data = payload();
    const a = app(url => url.includes('api.github.com')
        ? { ok: false, status: 403 } : response(data));
    assert.equal(await a.load(), data);
    assert.equal(a.calls.length, 2);
    assert.match(a.calls[1].url, /^https:\/\/raw\.githubusercontent\.com\//);
});

test('network and malformed responses fall back to the deployed file', async () => {
    const data = payload();
    const a = app(url => {
        if (url.includes('api.github.com')) return response({ symbols: [] });
        if (url.includes('raw.githubusercontent.com')) throw new Error('offline');
        return response(data);
    });
    assert.equal(await a.load(), data);
    assert.equal(a.calls.length, 3);
    assert.equal(a.calls[2].url, './data/final-closes.json');
    assert.equal(a.errors.length, 0);
});

test('total outage retains saved prices, reports error, and recovers on the next retry', async () => {
    let offline = false;
    const data = payload();
    const a = app(() => {
        if (offline) throw new Error('offline');
        return response(data);
    });
    await a.load();
    offline = true;
    assert.equal(await a.load(true), data);
    assert.equal(a.run('_finalCloseDataState'), 'error');
    assert.equal(a.errors.length, 1);
    offline = false;
    assert.equal(await a.load(true), data);
    assert.equal(a.run('_finalCloseDataState'), 'ready');
    assert.equal(a.run('_finalCloseDataPromise'), null);
});

test('local development always reads the local file', async () => {
    for (const location of [
        { protocol: 'file:', hostname: '' },
        ...['localhost', '127.0.0.1', '::1', '[::1]'].map(hostname => ({ protocol: 'http:', hostname }))
    ]) {
        const a = app(() => response(payload()), location);
        await a.load();
        assert.deepEqual(a.calls.map(call => call.url), ['./data/final-closes.json']);
    }
});

test('Yahoo chart final closes resolve exact dates; bootstrap and date gaps remain rejected', async () => {
    const data = payload();
    const bar = close => ({ close, final: true, source: 'yahoo-chart-final', fetchedAt: data.generatedAt });
    data.symbols.MSTR = { market: 'US', byDate: {
        '2026-09-23': bar(162.20), '2026-09-24': bar(161.61), '2026-09-25': bar(158.61)
    } };
    const a = app(() => response(data));
    await a.load();
    const pair = () => a.context._resolveClosePairFromFinalData('MSTR', 'US', '2026-09-25');
    assert.equal(pair().prevDate, '2026-09-24');
    assert.ok(Math.abs(pair().close - pair().prevClose + 3) < 1e-8);
    assert.equal(pair().source, 'final-closes:yahoo-chart-final');
    data.symbols.MSTR.byDate['2026-09-25'].source = 'fundamentals-bootstrap';
    assert.equal(pair(), null);
    data.symbols.MSTR.byDate['2026-09-25'].source = 'yahoo-chart-final';
    delete data.symbols.MSTR.byDate['2026-09-24'];
    assert.equal(pair(), null);
    assert.equal(a.context._resolveClosePairFromFinalData('MSTR', 'TW', '2026-09-24'), null);
});

test('Taipei 08:00 rollover and the Taiwan holiday keep their original market dates', () => {
    const a = app(() => response(payload()));
    assert.equal(a.context._portfolioDay(new Date('2026-09-25T23:59:00Z')), '2026-09-25');
    assert.equal(a.context._portfolioDay(new Date('2026-09-26T00:00:00Z')), '2026-09-26');
    assert.equal(a.context._portfolioPreviousTradingDate('US', '2026-09-26'), '2026-09-25');
    assert.equal(a.context._portfolioPreviousTradingDate('TW', '2026-09-26'), '2026-09-24');
    assert.equal(a.context._isTradingDay('TW', '2026-09-25'), false);
});

// v15.969：Yahoo 收盤後當日 bar close=null 不可被當成臨時休市；meta 成交時間是有開盤的正面證據。
const yahooCode = section('const MARKET_CALENDARS =', 'function _marketPortfolioDayStatus(')
    + section('let _finalCloseData =', 'function _resolveClosePairFromFundamentals(');
const DAY = d => Date.parse(d + 'T13:30:00Z') / 1000;
function chart(days, closes, metaIso, metaPrice) {
    return { chart: { result: [{
        timestamp: days.map(DAY),
        indicators: { quote: [{ close: closes }] },
        meta: metaIso ? { regularMarketTime: Date.parse(metaIso) / 1000, regularMarketPrice: metaPrice } : {}
    }] } };
}
function yahooApp(nowIso, charts, holdings, store = {}) {
    const now = Date.parse(nowIso);
    const errors = [], renders = [];
    const context = vm.createContext({
        Date: class extends Date {
            constructor(...args) { super(...(args.length ? args : [now])); }
            static now() { return now; }
        },
        Intl, console: { log() {}, warn() {} },
        localStorage: {
            getItem: k => (k in store ? store[k] : null),
            setItem: (k, v) => { store[k] = String(v); }
        },
        STORAGE_KEYS: { adhocClosures: 'pt_adhoc_closures_v1' },
        holdings,
        renderAll: () => renders.push(1),
        _recordAppError: (...args) => errors.push(args),
        _isClosePairDateKey: s => /^\d{4}-\d{2}-\d{2}$/.test(String(s)),
        _loadClosePair: () => ({ symbols: {} }),
        _getClosePairForDate: () => null,
        _isFinalClosePair: p => !!(p && p.final === true),
        _exchangeTz: sym => sym.endsWith('.TW') ? 'Asia/Taipei' : sym.endsWith('.HK') ? 'Asia/Hong_Kong' : 'America/New_York',
        yfFetch: async url => {
            const sym = decodeURIComponent(url.split('/chart/')[1].split('?')[0]).replace(/\.(TW|TWO|HK)$/, '');
            return charts[sym];
        }
    });
    vm.runInContext(yahooCode, context);
    return { context, store, errors, renders, run: code => vm.runInContext(code, context) };
}
const usHoldings = ['AAOI', 'MSTU', 'NVDL'].map(symbol => ({ symbol, market: 'US', quantity: 10 }));
const usDays = ['2026-09-29', '2026-09-30', '2026-10-01', '2026-10-02'];
const usCharts = {
    AAOI: chart(usDays, [100.67, 99.26, 107.32, null], '2026-10-02T20:00:00Z', 115.59),
    MSTU: chart(usDays, [40.57, 39.76, 43.47, null], '2026-10-02T20:00:00Z', 43.16),
    NVDL: chart(usDays, [36.39, 36.71, 37.52, null], '2026-10-02T20:00:00Z', 38.5)
};
const falseClosure = () => ({ pt_adhoc_closures_v1: JSON.stringify({ US: { '2026-10-02': {
    detectedAt: '2026-10-02T21:30:00Z', detectedOnMarketDate: '2026-10-02', evidenceVersion: 2,
    status: 'provisional', symbols: ['AAOI', 'MSTU', 'NVDL']
} } }) });

test('null latest Yahoo bar after the US close uses the meta close and never marks a holiday', async () => {
    // 2026-10-03 09:05 台北 = 2026-10-02 21:05 美東（實際出事時段）
    const a = yahooApp('2026-10-03T01:05:00Z', usCharts, usHoldings);
    for (const [sym, close, prev] of [['AAOI', 115.59, 107.32], ['MSTU', 43.16, 43.47], ['NVDL', 38.5, 37.52]]) {
        const pair = await a.context._fetchClosePairFromYahoo(sym, 'US', '2026-10-02', { final: true });
        assert.equal(pair.targetDate, '2026-10-02');
        assert.equal(pair.prevDate, '2026-10-01');
        assert.equal(pair.close, close);
        assert.equal(pair.prevClose, prev);
        assert.equal(pair.final, true);
        assert.match(pair.source, /^yahoo-chart-10d-final\+meta/);
    }
    assert.equal(a.context._isTradingDay('US', '2026-10-02'), true);
    assert.equal(a.context._marketSession('US').lastCompletedTradingDate, '2026-10-02');
    assert.equal(a.store.pt_adhoc_closures_v1, undefined);
});

test('meta close waits for the 30-minute settle buffer but still blocks holiday evidence', async () => {
    const a = yahooApp('2026-10-02T21:10:00Z', usCharts, usHoldings);   // 美東 17:10，已過休市偵測的 +60 分
    for (const sym of ['AAOI', 'MSTU', 'NVDL']) {
        assert.ok(await a.context._fetchClosePairFromYahoo(sym, 'US', '2026-10-02', { final: true }));
    }
    assert.equal(a.store.pt_adhoc_closures_v1, undefined);
    const early = yahooApp('2026-10-02T20:20:00Z', usCharts, usHoldings);   // 美東 16:20，未過 30 分緩衝
    assert.equal(await early.context._fetchClosePairFromYahoo('AAOI', 'US', '2026-10-02', { final: true }), null);
    assert.equal(early.store.pt_adhoc_closures_v1, undefined);
});

test('a false US closure already saved on the device is healed by fetch and by audit', async () => {
    const a = yahooApp('2026-10-03T01:05:00Z', usCharts, usHoldings, falseClosure());
    assert.equal(a.context._isTradingDay('US', '2026-10-02'), false);
    assert.equal(a.context._marketSession('US').status, 'closed_or_holiday');
    // 誤判狀態下 target 已退回 10/01；抓取時看到 meta 落在 10/02 即解除
    assert.ok(await a.context._fetchClosePairFromYahoo('AAOI', 'US', '2026-10-01', { final: true }));
    assert.equal(a.context._isTradingDay('US', '2026-10-02'), true);
    assert.equal(a.context._marketSession('US').status, 'closed');

    const b = yahooApp('2026-10-03T01:05:00Z', usCharts, usHoldings, falseClosure());
    assert.equal(await b.context._auditRecentAdhocClosures('test'), true);
    assert.equal(b.context._isTradingDay('US', '2026-10-02'), true);
});

test('a real unscheduled closure (no trades, meta on the previous day) is still detected', async () => {
    const twHoldings = ['2330', '2317', '0050'].map(symbol => ({ symbol, market: 'TW', quantity: 1000 }));
    const bars = ['2026-09-24', '2026-09-29', '2026-09-30'];
    const charts = Object.fromEntries(twHoldings.map((h, i) =>
        [h.symbol, chart(bars, [100 + i, 101 + i, 102 + i], '2026-09-30T05:30:00Z', 102 + i)]));
    const a = yahooApp('2026-10-01T08:00:00Z', charts, twHoldings);   // 台北 10/01 16:00
    assert.equal(a.context._isTradingDay('TW', '2026-10-01'), true);
    for (const h of twHoldings) {
        assert.equal(await a.context._fetchClosePairFromYahoo(h.symbol, 'TW', '2026-10-01', { final: true }), null);
    }
    assert.equal(a.context._isTradingDay('TW', '2026-10-01'), false);
    assert.equal(JSON.parse(a.store.pt_adhoc_closures_v1).TW['2026-10-01'].status, 'provisional');
});

function extractFunction(source, name) {
    const start = source.indexOf(`function ${name}(`);
    assert.ok(start >= 0, `function ${name} found`);
    let i = source.indexOf('{', start);
    let depth = 0;
    const frames = [{ type: 'code' }];
    const interpDepths = [];
    const frame = () => frames[frames.length - 1];
    for (; i < source.length; i++) {
        const c = source[i];
        const current = frame();
        if (current.type === 'line') {
            if (c === '\n') frames.pop();
            continue;
        }
        if (current.type === 'block') {
            if (c === '*' && source[i + 1] === '/') { frames.pop(); i++; }
            continue;
        }
        if (current.type === 'squote' || current.type === 'dquote' || current.type === 'template') {
            if (current.escape) { current.escape = false; continue; }
            if (c === '\\') { current.escape = true; continue; }
            if (current.type === 'squote' && c === "'") { frames.pop(); continue; }
            if (current.type === 'dquote' && c === '"') { frames.pop(); continue; }
            if (current.type === 'template' && c === '`') { frames.pop(); continue; }
            if (current.type === 'template' && c === '$' && source[i + 1] === '{') {
                frames.push({ type: 'code' });
                depth++;
                interpDepths.push(depth);
                i++;
            }
            continue;
        }
        if (current.type === 'regex') {
            if (current.escape) { current.escape = false; continue; }
            if (c === '\\') { current.escape = true; continue; }
            if (c === '[') { current.class = true; continue; }
            if (c === ']' && current.class) { current.class = false; continue; }
            if (c === '/' && !current.class) frames.pop();
            continue;
        }
        if (c === '/' && source[i + 1] === '/') { frames.push({ type: 'line' }); i++; continue; }
        if (c === '/' && source[i + 1] === '*') { frames.push({ type: 'block' }); i++; continue; }
        if (c === "'") { frames.push({ type: 'squote', escape: false }); continue; }
        if (c === '"') { frames.push({ type: 'dquote', escape: false }); continue; }
        if (c === '`') { frames.push({ type: 'template', escape: false }); continue; }
        if (c === '/') {
            const prev = source.slice(start, i).match(/(\S)\s*$/);
            if (!prev || !/[A-Za-z0-9_$)\]"']/.test(prev[1])) {
                frames.push({ type: 'regex', escape: false, class: false });
                continue;
            }
        }
        if (c === '{') { depth++; continue; }
        if (c === '}') {
            const closing = depth;
            depth--;
            if (interpDepths.length && interpDepths[interpDepths.length - 1] === closing) {
                interpDepths.pop();
                frames.pop();
            }
            if (depth === 0 && frames.length === 1) return source.slice(start, i + 1);
        }
    }
    throw new Error(`unclosed function ${name}`);
}

test('pionex grid numbers use net profit including funding, and fall back when it is missing', () => {
    const names = [
        '_escapeHtml', '_pionexNum', '_pionexDayFigure', '_pionexMonthAverage', '_pionexLive24hAmount',
        '_pionexLive24hSummary', '_pionexEquivalent', '_fmtPionexX', '_pionexLiveEff',
        '_pionexLiveSortValue', '_pionexLiveSortedRows', '_pionexLiveSortTh',
        '_fmtUsdtAmt', '_fmtPionexJournalPnl', '_fmtTwdAmt', '_pnlColor',
        '_pionexLiveFreshness', '_fmtPionexTs', '_pionexFundingShareText', '_pionexMonthlyStats',
        '_renderPionexMonthlyHistory', '_renderPionexLiveCard'
    ];
    const context = vm.createContext({
        pv: value => value,
        _pionexLiveSort: { key: '', dir: 'desc' },
        Date, Number, Math, Object, String, isNaN
    });
    vm.runInContext(names.map(name => extractFunction(html, name)).join('\n'), context);

    const published = context._pionexDayFigure({ daily_profit_usdt: 10, funding_usdt: -3, net_usdt: 7 });
    assert.equal(published.value, 7);
    assert.equal(published.includesFunding, true);
    const summed = context._pionexDayFigure({ daily_profit_usdt: 10, funding_usdt: -3, net_usdt: null });
    assert.equal(summed.value, 7);
    assert.equal(summed.includesFunding, true);
    const pairingOnly = context._pionexDayFigure({ date: '2026-11-02', daily_profit_usdt: 10, funding_usdt: null, net_usdt: null });
    assert.equal(pairingOnly.value, 10);
    assert.equal(pairingOnly.fallback, true);
    assert.equal(pairingOnly.includesFunding, false);

    const withFunding = context._pionexMonthlyStats({
        '2026-11-01': { daily_profit_usdt: 10, funding_usdt: -2, net_usdt: 8 },
        '2026-11-02': { daily_profit_usdt: 10, funding_usdt: null, net_usdt: null }
    }, '2026-11-10');
    const netMonth = context._pionexMonthAverage(withFunding['2026-11']);
    assert.equal(withFunding['2026-11'].hasFunding, true);
    assert.equal(withFunding['2026-11'].funding, -2);
    assert.equal(netMonth.value, 9);
    assert.equal(netMonth.pairPerDay, 10);
    assert.equal(netMonth.fundingPerDay, -1);
    assert.equal(netMonth.includesFunding, true);

    const withoutFunding = context._pionexMonthlyStats({
        '2026-10-01': { daily_profit_usdt: 10 },
        '2026-10-02': { daily_profit_usdt: 6 }
    }, '2026-11-10');
    const pairMonth = context._pionexMonthAverage(withoutFunding['2026-10']);
    assert.equal(pairMonth.value, 8);
    assert.equal(pairMonth.includesFunding, false);

    const history = context._renderPionexMonthlyHistory(
        Object.assign({}, withFunding, withoutFunding), '2026-12');
    assert.equal(history.includes('淨利每日平均'), false);
    assert.match(history, /每日平均（含資金費）/);
    assert.match(history, /配對月均/);
    assert.match(history, />9\.00</);
    assert.match(history, />8\.00</);

    const liveNet = context._pionexLive24hSummary({
        total_profit_24h_usdt: 20, profit_24h_pct: 1.5,
        total_funding_24h_usdt: -4, total_net_24h_usdt: 16, net_24h_pct: 1.2,
        funding_24h_missing: 2
    });
    assert.equal(liveNet.value, 16);
    assert.equal(liveNet.pct, 1.2);
    assert.equal(liveNet.includesFunding, true);
    assert.equal(liveNet.missing, 2);
    const livePending = context._pionexLive24hSummary({
        total_profit_24h_usdt: 20, total_funding_24h_usdt: 3, total_net_24h_usdt: 23, net_24h_pct: 1.7,
        funding_24h_missing: 0, funding_24h_pending: 3
    });
    assert.equal(livePending.value, 23);
    assert.equal(livePending.pending, 3);
    const liveMissing = context._pionexLive24hSummary({
        total_profit_24h_usdt: 20, profit_24h_pct: 1.5, total_net_24h_usdt: null, funding_24h_missing: 2
    });
    assert.equal(liveMissing.value, 20);
    assert.equal(liveMissing.includesFunding, false);
    assert.equal(liveMissing.missing, 2);
    assert.match(html, /倉最新一次結算派網還沒入帳，暫不計/);
    const liveOld = context._pionexLive24hSummary({ total_profit_24h_usdt: 20, profit_24h_pct: 1.5 });
    assert.equal(liveOld.value, 20);
    assert.equal(liveOld.pct, 1.5);
    assert.equal(liveOld.includesFunding, false);
    const rowNet = context._pionexLive24hAmount({ profit_24h_usdt: 5, funding_24h_usdt: -1, net_24h_usdt: 4 });
    const rowOld = context._pionexLive24hAmount({ profit_24h_usdt: 5 });
    assert.equal(rowNet.value, 4);
    assert.equal(rowNet.includesFunding, true);
    assert.equal(rowOld.value, 5);
    assert.equal(rowOld.includesFunding, false);
    assert.match(html, /if \(key === 'profit24h'\) return _pionexLive24hAmount\(r\)\.value/);

    assert.equal(context._pionexFundingShareText(-2, 10), '吃掉配對 20.0%');
    assert.equal(context._pionexFundingShareText(2, 10), '加成配對 20.0%');
    assert.equal(context._pionexFundingShareText(2, 10, '運行中配對'), '加成運行中配對 20.0%');
    assert.equal(context._pionexFundingShareText(0, 10), '');

    const netCard = context._renderPionexLiveCard({
        schema: 1, captured_at: '2026-11-10T01:00:00Z',
        total_profit_24h_usdt: 20, profit_24h_pct: 1.5,
        total_funding_24h_usdt: -4, total_net_24h_usdt: 16, net_24h_pct: 1.2,
        funding_24h_missing: 2, total_equivalent_usdt: 1000,
        rows: [{ symbol: 'BTC', profit_24h_usdt: 5, funding_24h_usdt: -1, net_24h_usdt: 4, investment_usdt: 100, leverage: 3 }]
    });
    assert.match(netCard, /24h 淨利（含資金費）/);
    assert.match(netCard, /16\.00/);
    assert.match(netCard, /1\.200%/);
    assert.match(netCard, /吃掉配對 20\.0%/);
    assert.match(netCard, /有 2 個倉位缺資金費/);
    assert.match(netCard, />4\.00/);
    assert.doesNotMatch(netCard, /暫不含資金費/);
    assert.doesNotMatch(netCard, /24h 網格/);

    const oldCard = context._renderPionexLiveCard({
        schema: 1, captured_at: '2026-11-10T01:00:00Z',
        total_profit_24h_usdt: 20, profit_24h_pct: 1.5, total_equivalent_usdt: 1000,
        rows: [{ symbol: 'BTC', profit_24h_usdt: 5, investment_usdt: 100, leverage: 3 }]
    });
    assert.match(oldCard, /24h 淨利（含資金費）/);
    assert.match(oldCard, /暫不含資金費/);
    assert.match(oldCard, /1\.500%/);
    assert.match(oldCard, />20\.00/);
    assert.match(oldCard, />5\.00/);
    assert.doesNotMatch(oldCard, /1\.200%/);
});

test('pionex calendar opens on the latest ledger day, not on today', () => {
    // v2 1.0.8 files each 08:15 capture under the day before it, so today's cell is empty until tomorrow.
    const context = vm.createContext({
        _taipeiCalendarDate: () => '2026-12-01', Number, String, Array
    });
    vm.runInContext('let _pionexCalMonth = null; let _pionexCalSelected = null; let _pionexCalAutoSelected = false;\n'
        + ['_pionexLatestLedgerDate', '_resetPionexCalToTaipeiToday'].map(name => extractFunction(html, name)).join('\n'), context);
    const state = () => vm.runInContext('({ month: _pionexCalMonth, selected: _pionexCalSelected, auto: _pionexCalAutoSelected })', context);

    // 12/01 morning: the newest cell is 11/30 (the 12/01 capture), so November opens, not an empty December.
    context._resetPionexCalToTaipeiToday({ days: [{ date: '2026-11-29' }, { date: '2026-11-30' }, { date: '2026-11-28' }] });
    assert.deepEqual(JSON.parse(JSON.stringify(state())), { month: { y: 2026, m: 11 }, selected: '2026-11-30', auto: true });

    // Rows without a usable date are ignored.
    assert.equal(context._pionexLatestLedgerDate({ days: [{ date: 'bad' }, { }, { date: '2026-10-02' }] }), '2026-10-02');
    assert.equal(context._pionexLatestLedgerDate({ days: [] }), null);
    assert.equal(context._pionexLatestLedgerDate(null), null);

    // An empty ledger falls back to today.
    context._resetPionexCalToTaipeiToday({ days: [] });
    assert.deepEqual(JSON.parse(JSON.stringify(state())), { month: { y: 2026, m: 12 }, selected: '2026-12-01', auto: true });

    assert.match(html, /每格是當天 08:15 到隔天 08:15 的利潤/);
    assert.doesNotMatch(html, /（或等 08:05 排程）/);
});
