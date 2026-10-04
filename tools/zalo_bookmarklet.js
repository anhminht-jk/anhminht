// Nút "Zalo → Trợ lý": chạy trên chat.zalo.me, gom chữ của nhóm chat đang mở.
// Tự cuộn lên để tải tin cũ, ghép các lần chụp (kể cả khi Zalo chỉ giữ một phần tin trên màn hình),
// rồi hiện khung để Sao chép / Tải file .txt. Không gửi dữ liệu đi đâu.
(async () => {
  // khung xanh hiện ngay khi bấm, để biết nút đã chạy (không dùng alert/prompt vì trang có thể chặn)
  const st = document.createElement('div');
  st.style.cssText = 'position:fixed;top:8px;right:8px;z-index:2147483647;background:#0068ff;color:#fff;padding:10px 14px;border-radius:6px;font:15px sans-serif;max-width:360px';
  st.textContent = 'Zalo → Trợ lý: đang tìm khung chat…';
  document.body.append(st);
  const say = (m, ms) => { st.textContent = m; if (ms) setTimeout(() => st.remove(), ms); };
  try {
    const W = innerWidth, sleep = ms => new Promise(r => setTimeout(r, ms));
    // khung chat = vùng cuộn rộng nhất, nằm qua nửa phải màn hình (danh sách hội thoại thì hẹp)
    const box = [...document.querySelectorAll('div')].filter(e => {
      const r = e.getBoundingClientRect();
      return r.width > 300 && r.height > 200 && r.right > W * 0.5 &&
        /(auto|scroll)/.test(getComputedStyle(e).overflowY) && e.scrollHeight > e.clientHeight + 20;
    }).sort((a, b) => b.getBoundingClientRect().width - a.getBoundingClientRect().width ||
      b.innerText.length - a.innerText.length)[0];
    if (!box) return say('Không thấy khung chat. Hãy mở chat.zalo.me trên Chrome, bấm vào một nhóm rồi bấm lại nút.', 8000);
    const n = 20;
    const lines = () => box.innerText.split('\n').map(s => s.trim()).filter(Boolean);
    // ghép: phần cuối của "older" trùng phần đầu của "newer" thì nối không lặp
    const merge = (older, newer) => {
      for (let k = Math.min(older.length, newer.length); k >= 3; k--) {
        let ok = true;
        for (let i = 0; i < k && ok; i++) ok = older[older.length - k + i] === newer[i];
        if (ok) return older.concat(newer.slice(k));
      }
      return older.concat(['…'], newer);
    };
    let all = lines(), stall = 0;
    for (let i = 0; i < n; i++) {
      say(`Zalo → Trợ lý: đang lấy tin… lượt ${i + 1}/${n} (${all.length} dòng)`);
      box.scrollTop = -1e9;
      box.dispatchEvent(new WheelEvent('wheel', { deltaY: -3000, bubbles: true }));
      await sleep(1500);
      const m = merge(lines(), all);
      if (m.length === all.length) { if (++stall >= 2) break; } else stall = 0;
      all = m;
    }
    st.remove();
    const name = (document.title || '').replace(/^Zalo\s*[-–]?\s*/, '');
    const txt = `Nhóm: ${name}\nLấy lúc: ${new Date().toLocaleString('vi-VN')}\n\n${all.join('\n')}`;
    const d = document.createElement('div');
    d.style.cssText = 'position:fixed;top:10vh;bottom:10vh;left:15vw;right:15vw;z-index:2147483647;background:#fff;border:2px solid #0068ff;border-radius:8px;padding:12px;display:flex;flex-direction:column;gap:8px;font:14px sans-serif;box-shadow:0 8px 30px #0005';
    const h = document.createElement('b');
    h.textContent = `Đã lấy ${all.length} dòng. Bấm Sao chép rồi dán vào file của nhóm trên Drive.`;
    const t = document.createElement('textarea');
    t.value = txt; t.style.cssText = 'flex:1;font:12px monospace';
    const row = document.createElement('div');
    const btn = (label, fn) => { const b = document.createElement('button'); b.textContent = label; b.style.cssText = 'margin-right:8px;padding:6px 14px;font:14px sans-serif;cursor:pointer'; b.onclick = () => fn(b); row.append(b); };
    btn('Sao chép', b => { t.select(); const ok = () => b.textContent = 'Đã sao chép ✓'; navigator.clipboard.writeText(txt).then(ok, () => { document.execCommand('copy'); ok(); }); });
    btn('Tải file .txt', () => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([txt], { type: 'text/plain' })); a.download = `zalo-${new Date().toISOString().slice(0, 10)}.txt`; a.click(); });
    btn('Đóng', () => d.remove());
    d.append(h, t, row);
    document.body.append(d);
  } catch (e) {
    say('Zalo → Trợ lý lỗi: ' + e.message + ' — chụp màn hình gửi trợ lý.', 15000);
  }
})();
