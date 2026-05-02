with open('portfolio-tracker-v15.html', encoding='utf-8') as f:
    src = f.read()

# Patch 1: 切段邏輯加 [Deposits] [OtherAssets]
old1 = r"""            // ── 分離 [TradeHistory] 區段 ──
            let holdingsPart = csvText;
            let tradeHistoryPart = '';
            const thIdx = csvText.indexOf('[TradeHistory]');
            if (thIdx >= 0) {
                holdingsPart = csvText.substring(0, thIdx);
                tradeHistoryPart = csvText.substring(thIdx + '[TradeHistory]'.length);
            }"""
new1 = r"""            // ── v15.077：依序分離 [TradeHistory] / [Deposits] / [OtherAssets] 區段 ──
            let holdingsPart = csvText;
            let tradeHistoryPart = '', depositsPart = '', otherAssetsPart = '';
            const _markers = [
                { key: 'tradeHistory', tag: '[TradeHistory]' },
                { key: 'deposits',     tag: '[Deposits]' },
                { key: 'otherAssets',  tag: '[OtherAssets]' }
            ];
            const _positions = _markers
                .map(m => ({ ...m, idx: csvText.indexOf(m.tag) }))
                .filter(p => p.idx >= 0)
                .sort((a, b) => a.idx - b.idx);
            if (_positions.length > 0) {
                holdingsPart = csvText.substring(0, _positions[0].idx);
                _positions.forEach((p, i) => {
                    const start = p.idx + p.tag.length;
                    const end   = (i + 1 < _positions.length) ? _positions[i + 1].idx : csvText.length;
                    const seg   = csvText.substring(start, end);
                    if (p.key === 'tradeHistory') tradeHistoryPart = seg;
                    else if (p.key === 'deposits') depositsPart = seg;
                    else if (p.key === 'otherAssets') otherAssetsPart = seg;
                });
            }"""

# Patch 2: 解析 deposits / otherAssets
old2 = r"""            pendingCsvRows = rows;
            pendingCsvTrades = importedTrades;
            if (rows.length > 0) {
                // 自動匯入，不需要按確認鍵
                confirmCsvImport();
            } else {
                renderCsvPreview(rows, errors);
            }
        }"""
new2 = r"""            // v15.077：解析 [Deposits]
            let importedDeposits = null;
            if (depositsPart.trim()) {
                const dLines = depositsPart.trim().split(/\r?\n|\r/).filter(l => l.trim());
                const dFirst = (dLines[0] || '').toLowerCase();
                const dHasHeader = dFirst.includes('bank') || dFirst.includes('currency') || dFirst.includes('amount');
                const dData = dHasHeader ? dLines.slice(1) : dLines;
                importedDeposits = [];
                dData.forEach(line => {
                    const c = parseCSVLine(line);
                    const bank = (c[0] || '').trim();
                    const cur  = (c[1] || 'TWD').toUpperCase();
                    const amt  = parseFloat(c[2]) || 0;
                    if (bank && amt > 0) importedDeposits.push({ id: Date.now() + Math.random(), bank, currency: cur, amount: amt });
                });
            }
            // v15.077：解析 [OtherAssets]（key=value 單值欄位）
            let importedOther = null;
            if (otherAssetsPart.trim()) {
                importedOther = {};
                otherAssetsPart.trim().split(/\r?\n|\r/).forEach(line => {
                    const eq = line.indexOf('=');
                    if (eq < 0) return;
                    const k = line.substring(0, eq).trim();
                    const v = line.substring(eq + 1).trim();
                    if (k) importedOther[k] = v;
                });
            }

            pendingCsvRows = rows;
            pendingCsvTrades = importedTrades;
            pendingCsvDeposits = importedDeposits;
            pendingCsvOther = importedOther;
            if (rows.length > 0) {
                // 自動匯入，不需要按確認鍵
                confirmCsvImport();
            } else {
                renderCsvPreview(rows, errors);
            }
        }"""

# Patch 3: confirmCsvImport 套用新區段
old3 = r"""        function confirmCsvImport() {
            if (pendingCsvRows.length === 0) return;
            saveHistory();
            const n = pendingCsvRows.length;
            holdings = pendingCsvRows;
            pendingCsvRows = [];
            // 還原已實現損益
            const tn = pendingCsvTrades.length;
            if (tn > 0) { tradeHistory = pendingCsvTrades; saveTradeHistory(); }
            pendingCsvTrades = [];
            hideImportModal();"""
new3 = r"""        function confirmCsvImport() {
            if (pendingCsvRows.length === 0) return;
            saveHistory();
            const n = pendingCsvRows.length;
            holdings = pendingCsvRows;
            pendingCsvRows = [];
            // 還原已實現損益
            const tn = pendingCsvTrades.length;
            if (tn > 0) { tradeHistory = pendingCsvTrades; saveTradeHistory(); }
            pendingCsvTrades = [];
            // v15.077：還原存款（向下相容：CSV 沒 [Deposits] 區段就保留本機）
            const dn = (pendingCsvDeposits && pendingCsvDeposits.length) || 0;
            if (pendingCsvDeposits && pendingCsvDeposits.length > 0) {
                deposits = pendingCsvDeposits;
                saveDeposits();
            }
            pendingCsvDeposits = null;
            // v15.077：還原 OtherAssets（crypto / moxa / pie_cb / sheet_url / currency；缺值保留本機）
            if (pendingCsvOther) {
                const o = pendingCsvOther;
                const _setBool = (k, cbId, lsKey) => {
                    if (o[k] == null) return;
                    const b = (o[k] === 'true' || o[k] === '1');
                    localStorage.setItem(lsKey, b ? '1' : '0');
                    const cb = document.getElementById(cbId); if (cb) cb.checked = b;
                };
                const _setNum = (k, inputId, lsKey) => {
                    if (o[k] == null) return;
                    const v = parseFloat(o[k]) || 0;
                    if (v > 0) localStorage.setItem(lsKey, v); else localStorage.removeItem(lsKey);
                    const el = document.getElementById(inputId); if (el) el.value = v > 0 ? v : '';
                };
                _setBool('cash_pie_cb',   'cash-pie-cb',   PT_CASH_PIE_KEY);
                _setNum ('crypto_twd',    'crypto-twd-input', PT_CRYPTO_KEY);
                _setBool('crypto_pie_cb', 'crypto-pie-cb', PT_CRYPTO_PIE_KEY);
                _setNum ('moxa_twd',      'moxa-twd-input',   PT_MOXA_KEY);
                _setBool('moxa_pie_cb',   'moxa-pie-cb',      PT_MOXA_PIE_KEY);
                if (o.sheet_url != null) {
                    const sEl = document.getElementById('sheet-url');
                    if (sEl) { sEl.value = o.sheet_url; saveSheetUrlSetting(); }
                }
                if (o.currency && (o.currency === 'USD' || o.currency === 'TWD')) {
                    currency = o.currency;
                    setCurrency(currency);
                }
            }
            pendingCsvOther = null;
            hideImportModal();"""

err = []
for i, (o, n) in enumerate([(old1, new1), (old2, new2), (old3, new3)], 1):
    if o not in src:
        err.append('patch ' + str(i) + ' NOT FOUND')
    else:
        src = src.replace(o, n, 1)
        err.append('patch ' + str(i) + ' OK')

print('\n'.join(err))
if all('OK' in x for x in err):
    with open('portfolio-tracker-v15.html', 'w', encoding='utf-8') as f:
        f.write(src)
    print('written')
