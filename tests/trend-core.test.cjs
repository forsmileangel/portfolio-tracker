const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const html = fs.readFileSync(path.join(__dirname, '..', 'portfolio-tracker-v15.html'), 'utf8');
const from = html.indexOf('// #region Trend Core BEGIN (pure)');
const to = html.indexOf('// #endregion Trend Core END');
assert.ok(from >= 0 && to > from, 'Trend Core block found');
const ctx = vm.createContext({});
vm.runInContext(html.slice(from, to), ctx);
const T = ctx;
const J = v => JSON.parse(JSON.stringify(v)); // strip cross-realm prototypes
const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-9, `${a} != ${b}`);
const mk = (time, o, h, l, c) => ({ time, open: o, high: h, low: l, close: c });
const barsFrom = closes => closes.map((c, i) => mk('2025-01-' + String(i + 1).padStart(2, '0'), c, c + 1, c - 1, c));
const day = i => new Date(Date.UTC(2024, 0, 1 + i)).toISOString().slice(0, 10);
const series = closes => closes.map((c, i) => mk(day(i), c, c + 1, c - 1, c));

test('tcSMA / tcEMA hand-computed, short arrays, leading nulls', () => {
    assert.deepEqual(J(T.tcSMA([1, 2, 3, 4, 5], 3)), [null, null, 2, 3, 4]);
    assert.deepEqual(J(T.tcSMA([1, 2], 3)), [null, null]);
    assert.deepEqual(J(T.tcSMA([null, 1, 2, 3, 4], 3)), [null, null, null, 2, 3]);
    const e = T.tcEMA([1, 2, 3, 4, 5], 3); // alpha .5, seed 2
    assert.deepEqual(J(e.slice(0, 2)), [null, null]);
    near(e[2], 2); near(e[3], 3); near(e[4], 4);
    const e2 = T.tcEMA([2, 4, 6, 8], 3); // seed 4, then .5*8+.5*4=6
    near(e2[2], 4); near(e2[3], 6);
    assert.deepEqual(J(T.tcEMA([1, 2], 3)), [null, null]);
    const e3 = T.tcEMA([null, null, 1, 2, 3, 4], 3);
    assert.deepEqual(J(e3.slice(0, 4)), [null, null, null, null]);
    near(e3[4], 2); near(e3[5], 3);
    const e4 = T.tcEMA([1, 2, 3, null, 5], 3);
    assert.equal(e4[3], null); assert.equal(e4[4], null);
});

test('tcTrueRange with a gap', () => {
    const tr = T.tcTrueRange([mk('a', 10, 12, 9, 11), mk('b', 15, 16, 14, 15)]);
    assert.deepEqual(J(tr), [3, 5]); // max(2, |16-11|, |14-11|)
});

test('tcAggregateWeekly', () => {
    const d = [
        mk('2026-01-05', 1, 5, 1, 2), mk('2026-01-06', 2, 6, 2, 3), mk('2026-01-09', 3, 4, 0.5, 4),
        mk('2026-01-13', 10, 11, 9, 10), // Tuesday, Monday missing
        mk('2026-01-14', 10, 12, 8, 9)
    ];
    const w = J(T.tcAggregateWeekly(d));
    assert.equal(w.length, 2);
    assert.deepEqual(w[0], { time: '2026-01-05', open: 1, high: 6, low: 0.5, close: 4, lastTime: '2026-01-09' });
    assert.deepEqual(w[1], { time: '2026-01-13', open: 10, high: 12, low: 8, close: 9, lastTime: '2026-01-14' });
    const y = J(T.tcAggregateWeekly([mk('2025-12-29', 1, 2, 1, 2), mk('2025-12-31', 2, 3, 2, 3), mk('2026-01-02', 3, 4, 3, 4)]));
    assert.equal(y.length, 1);
    assert.equal(y[0].time, '2025-12-29'); assert.equal(y[0].lastTime, '2026-01-02');
    assert.equal(y[0].close, 4);
    const t = J(T.tcAggregateWeekly([mk('2026-01-09', 1, 1, 1, 1), mk('2026-01-12', 2, 2, 2, 2)]));
    assert.equal(t.length, 2); assert.equal(t[1].time, '2026-01-12'); assert.equal(t[1].lastTime, '2026-01-12');
    assert.deepEqual(J(T.tcAggregateWeekly([])), []);
});

test('tcParseYahooChart', () => {
    const chart = (ts, q, meta) => ({ chart: { result: [{ meta, timestamp: ts, indicators: { quote: [q] } }] } });
    // 2025-03-10 00:00:00Z = 08:00 Taipei (03-10) = 20:00 NY previous day (03-09, EDT)
    const t0 = Date.UTC(2025, 2, 10, 0, 0) / 1000;
    const q = { open: [1, 2, 3], high: [2, 3, 4], low: [0.5, 1, 2], close: [1.5, 2.5, 3.5] };
    const tp = T.tcParseYahooChart(chart([t0, t0 + 86400, t0 + 2 * 86400], q, { exchangeTimezoneName: 'Asia/Taipei' }), 'X');
    assert.equal(tp.tz, 'Asia/Taipei');
    assert.deepEqual(J(tp.bars.map(b => b.time)), ['2025-03-10', '2025-03-11', '2025-03-12']);
    const ny = T.tcParseYahooChart(chart([t0], { open: [1], high: [2], low: [1], close: [1] }, { exchangeTimezoneName: 'America/New_York' }), 'X');
    assert.equal(ny.bars[0].time, '2025-03-09');
    // null rows dropped with timestamps
    const n = T.tcParseYahooChart(chart([t0, t0 + 86400, t0 + 2 * 86400],
        { open: [1, null, 3], high: [2, 3, 4], low: [1, 1, 2], close: [1, 2, 3] }, { exchangeTimezoneName: 'UTC' }), 'X');
    assert.deepEqual(J(n.bars.map(b => b.time)), ['2025-03-10', '2025-03-12']);
    // non-positive dropped
    const z = T.tcParseYahooChart(chart([t0], { open: [0], high: [2], low: [1], close: [1] }, { exchangeTimezoneName: 'UTC' }), 'X');
    assert.equal(z.bars.length, 0);
    // duplicate date keeps last
    const dup = T.tcParseYahooChart(chart([t0, t0 + 3600],
        { open: [1, 5], high: [2, 6], low: [1, 4], close: [1, 5] }, { exchangeTimezoneName: 'UTC' }), 'X');
    assert.equal(dup.bars.length, 1); assert.equal(dup.bars[0].close, 5);
    // tz fallback
    const fb = (sym, hint) => T.tcParseYahooChart(chart([t0], { open: [1], high: [1], low: [1], close: [1] }, sym ? { symbol: sym } : {}), hint).tz;
    assert.equal(fb('2330.TW'), 'Asia/Taipei');
    assert.equal(fb('6488.TWO'), 'Asia/Taipei');
    assert.equal(fb('0700.HK'), 'Asia/Hong_Kong');
    assert.equal(fb('BTC-USD'), 'UTC');
    assert.equal(fb('AAPL'), 'America/New_York');
    assert.equal(fb(null, '2330.TW'), 'Asia/Taipei');
    // malformed never throws
    for (const bad of [null, undefined, {}, { chart: {} }, { chart: { result: [] } }, { chart: { result: [{}] } }, { chart: { result: [{ timestamp: [1], indicators: {} }] } }]) {
        const r = T.tcParseYahooChart(bad, 'AAPL');
        assert.deepEqual(J(r.bars), []);
        assert.equal(r.tz, 'America/New_York');
    }
});

test('tcTrendStates rule A', () => {
    const up = barsFrom(Array.from({ length: 30 }, (_, i) => 10 + i));
    const sA = T.tcTrendStates(up, 'A');
    assert.equal(sA.slice(0, 20).every(v => v === null), true);
    assert.equal(sA[20], 'G'); assert.equal(sA[29], 'G');
    const down = barsFrom(Array.from({ length: 30 }, (_, i) => 100 - i));
    assert.equal(T.tcTrendStates(down)[29], 'B');
    // rise then sharp drop: ema falls, sma lags less? turn gives Y at some point
    const turn = barsFrom([...Array.from({ length: 25 }, (_, i) => 10 + i), ...Array.from({ length: 25 }, () => 5)]);
    const st = J(T.tcTrendStates(turn, 'A'));
    assert.ok(st.includes('G') && st.includes('Y') && st.includes('B'));
    assert.deepEqual(J(T.tcTrendStates([], 'A')), []);
});

test('tcTrendStates rule B', () => {
    const up = barsFrom(Array.from({ length: 80 }, (_, i) => 10 + i));
    const s = T.tcTrendStates(up, 'B');
    assert.equal(s.slice(0, 60).every(v => v === null), true); // first i with sma60[i-1] is 60
    assert.equal(s[60], 'G'); assert.equal(s[79], 'G');
    const down = barsFrom(Array.from({ length: 80 }, (_, i) => 200 - i));
    assert.equal(T.tcTrendStates(down, 'B')[79], 'B');
    const mix = barsFrom([...Array.from({ length: 70 }, (_, i) => 10 + i), ...Array.from({ length: 50 }, () => 10)]);
    assert.ok(T.tcTrendStates(mix, 'B').includes('Y'));
});

test('tcTrendStates rule C', () => {
    const c = [...Array.from({ length: 20 }, () => 50), 60, 40];
    const s = T.tcTrendStates(barsFrom(c), 'C');
    assert.equal(s.slice(0, 20).every(v => v === null), true);
    assert.equal(s[20], 'G'); // 60 > c[0]
    assert.equal(s[21], 'Y'); // 40 < c[1] but i < 60
    const long = [...Array.from({ length: 60 }, () => 50), 40];
    assert.equal(T.tcTrendStates(barsFrom(long), 'C')[60], 'B');
    const mid = [...Array.from({ length: 40 }, () => 30), ...Array.from({ length: 20 }, () => 50), 45];
    assert.equal(T.tcTrendStates(barsFrom(mid), 'C')[60], 'Y'); // 45 < c[40]=50 but > c[0]=30
});

test('tcTrendStates rule D', () => {
    const up = barsFrom(Array.from({ length: 30 }, (_, i) => 10 + i));
    const s = T.tcTrendStates(up, 'D');
    assert.equal(s.slice(0, 19).every(v => v === null), true);
    assert.equal(s[19 + 3], 'G'); assert.equal(s[29], 'G');
    assert.equal(s[19], null);
    const down = barsFrom(Array.from({ length: 30 }, (_, i) => 100 - i));
    assert.equal(T.tcTrendStates(down, 'D')[29], 'B');
    const turn = barsFrom([...Array.from({ length: 25 }, (_, i) => 10 + i), 20]);
    assert.ok(T.tcTrendStates(turn, 'D').includes('Y'));
});

test('tcTrendStates rule H (20-pair first, 60-pair breaks ties)', () => {
    const ramp = Array.from({ length: 100 }, (_, i) => 10 + i); // ..109
    const up = barsFrom(ramp);
    const sUp = T.tcTrendStates(up, 'H');
    assert.equal(sUp.slice(0, 20).every(v => v === null), true);
    assert.equal(sUp[20], 'G'); assert.equal(sUp[99], 'G');
    // dip below EMA20 while MA20 still rises: A is gray, H stays green because both 60-lines rise
    const dip = barsFrom([...ramp, 95]);
    assert.equal(T.tcTrendStates(dip, 'A')[100], 'Y');
    assert.equal(T.tcTrendStates(dip, 'H')[100], 'G');
    // mirror: bounce above EMA20 in a downtrend stays black
    const fall = Array.from({ length: 100 }, (_, i) => 200 - i); // ..101
    const bounce = barsFrom([...fall, 115]);
    assert.equal(T.tcTrendStates(bounce, 'A')[100], 'Y');
    assert.equal(T.tcTrendStates(bounce, 'H')[100], 'B');
    // 20-pair agreement wins even against the 60-pair
    assert.equal(T.tcTrendStates(barsFrom(fall), 'H')[99], 'B');
    // 20s disagree and 60-lines not available yet -> gray
    const young = barsFrom([...Array.from({ length: 30 }, (_, i) => 10 + i), 25]);
    assert.equal(T.tcTrendStates(young, 'H')[30], 'Y');
    // flat series: nothing rises or falls -> gray
    assert.equal(T.tcTrendStates(barsFrom(Array.from({ length: 70 }, () => 50)), 'H')[69], 'Y');
});

test('tcLastChange', () => {
    const times = ['t0', 't1', 't2', 't3', 't4'];
    assert.deepEqual(J(T.tcLastChange([], [])), { insufficient: true });
    assert.deepEqual(J(T.tcLastChange(['G', null], ['a', 'b'])), { insufficient: true });
    assert.deepEqual(J(T.tcLastChange([null, null, 'G', 'G', 'G'], times)),
        { insufficient: false, cur: 'G', prev: null, barsAgo: 2, since: 't2' });
    assert.deepEqual(J(T.tcLastChange(['G', 'G', 'G', 'G', 'G'], times)),
        { insufficient: false, cur: 'G', prev: null, barsAgo: 4, since: 't0' });
    assert.deepEqual(J(T.tcLastChange(['G', 'G', 'Y', 'Y', 'B'], times)),
        { insufficient: false, cur: 'B', prev: 'Y', barsAgo: 0, since: 't4' });
    assert.deepEqual(J(T.tcLastChange(['G', 'G', 'B', 'B', 'B'], times)),
        { insufficient: false, cur: 'B', prev: 'G', barsAgo: 2, since: 't2' });
});

test('tcDeductionIdx / tcPriceDeduction', () => {
    assert.equal(T.tcDeductionIdx(100, 20), 79);
    assert.equal(T.tcDeductionIdx(21, 20), 0);
    assert.equal(T.tcDeductionIdx(20, 20), null);
    assert.equal(T.tcDeductionIdx(0, 20), null);
    const d = T.tcPriceDeduction([100, 110, 121], 1);
    assert.equal(d[0], null); near(d[1], 10); near(d[2], 10);
    const z = T.tcPriceDeduction([0, 5, 6], 1);
    assert.equal(z[1], null); near(z[2], 20);
    assert.deepEqual(J(T.tcPriceDeduction([1, 2], 5)), [null, null]);
});

test('tcBuildModel / tcSummary shapes', () => {
    const e = T.tcBuildModel([], 'D', 'A');
    assert.deepEqual(J(e.bars), []); assert.deepEqual(J(e.dots), []);
    assert.deepEqual(J(e.change), { insufficient: true });
    assert.equal(e.lastTime, null); assert.equal(e.tf, 'D'); assert.equal(e.rule, 'A');
    for (const k of ['times', 'states', 'ema20', 'sma20', 'ema60', 'sma60', 'ema120', 'sma120', 'bd', 'atrx', 'dk20', 'dk60', 'dk120', 'risk']) {
        assert.deepEqual(J(e[k]), [], k);
    }
    assert.deepEqual(J(T.tcSummary([], 'A')), {
        D: { insufficient: true, bars: 0 }, W: { insufficient: true, bars: 0 }, lastTime: null
    });

    const small = series(Array.from({ length: 15 }, (_, i) => 10 + i));
    const m = T.tcBuildModel(small, 'D', 'A');
    assert.equal(m.dots.length, 0);
    assert.equal(m.states.every(v => v === null), true);
    assert.equal(m.change.insufficient, true);
    assert.equal(m.lastTime, small[14].time);
    near(m.bd[0], 2 / 10 * 100);

    const big = series(Array.from({ length: 170 }, (_, i) => 100 + i));
    const dm = T.tcBuildModel(big, 'D', 'A');
    assert.deepEqual(J(dm.dots.map(d => [d.n, d.index])), [[20, 149], [60, 109], [120, 49]]);
    assert.equal(dm.dots[0].time, big[149].time); assert.equal(dm.dots[0].low, big[149].low);
    assert.equal(dm.ema120[119] !== null && dm.ema120[118] === null, true);
    near(dm.risk[169], dm.dk20[169] + dm.dk60[169] + dm.dk120[169]);
    assert.equal(dm.risk[118], null);
    assert.equal(dm.change.cur, 'G');

    const wm = T.tcBuildModel(big, 'W', 'A');
    assert.ok(wm.bars.length >= 24 && wm.bars.length <= 26); // 170 days ~ 25 weeks
    assert.equal(wm.sma60.every(v => v === null), true);
    assert.equal(wm.sma120.every(v => v === null), true);
    assert.equal(wm.ema60.every(v => v === null), true);
    assert.equal(wm.dk60.every(v => v === null), true);
    assert.equal(wm.dk120.every(v => v === null), true);
    assert.equal(wm.risk.every(v => v === null), true);
    assert.deepEqual(J(wm.dots.map(d => d.n)), [20]);
    assert.equal(wm.lastTime, big[169].time);
    assert.equal(wm.dots[0].index, wm.bars.length - 21);

    const sum = T.tcSummary(big, 'A');
    assert.equal(sum.D.bars, 170); assert.equal(sum.W.bars, wm.bars.length);
    assert.equal(sum.lastTime, big[169].time);
    assert.equal(sum.D.cur, 'G');
});
