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

test('all inline app scripts compile and version stays v15.968', () => {
    for (const [, attrs, code] of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)) {
        if (!/\bsrc\s*=|type\s*=\s*["']application\//i.test(attrs)) new vm.Script(code);
    }
    assert.match(html, /const APP_VERSION\s*=\s*'v15\.968'/);
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
