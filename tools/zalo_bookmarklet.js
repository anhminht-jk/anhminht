// Nút "Zalo → Trợ lý": chạy trên chat.zalo.me, gom chữ của nhóm chat đang mở.
// Lần đầu: cuộn lên lấy tối đa 20 lượt. Các lần sau: chỉ lấy tin MỚI kể từ lần Sao chép/Tải trước
// (nút nhớ vài dòng cuối của mỗi nhóm trong trình duyệt). Không gửi dữ liệu đi đâu.
(async () => {
  // khung xanh hiện ngay khi bấm, để biết nút đã chạy (không dùng alert/prompt vì trang có thể chặn)
  const st = document.createElement('div');
  st.style.cssText = 'position:fixed;top:8px;right:8px;z-index:2147483647;background:#0068ff;color:#fff;padding:10px 14px;border-radius:6px;font:15px sans-serif;max-width:360px';
  st.textContent = 'Zalo → Trợ lý: đang tìm khung chat…';
  document.body.append(st);
  const say = (m, ms) => { st.textContent = m; if (ms) setTimeout(() => st.remove(), ms); };
  try {
    const W = innerWidth, sleep = ms => new Promise(r => setTimeout(r, ms));
    const rect = e => e.getBoundingClientRect();
    // khung chat = vùng cuộn rộng nhất, nằm qua nửa phải màn hình (danh sách hội thoại thì hẹp)
    const box = [...document.querySelectorAll('div')].filter(e => {
      const r = rect(e);
      return r.width > 300 && r.height > 200 && r.right > W * 0.5 &&
        /(auto|scroll)/.test(getComputedStyle(e).overflowY) && e.scrollHeight > e.clientHeight + 20;
    }).sort((a, b) => rect(b).width - rect(a).width || b.innerText.length - a.innerText.length)[0];
    if (!box) return say('Không thấy khung chat. Hãy mở chat.zalo.me trên Chrome, bấm vào một nhóm rồi bấm lại nút.', 8000);
    // tên nhóm = chữ to nhất phía trên khung chat
    const b0 = rect(box);
    const head = [...document.querySelectorAll('div,span,h1,h2,h3')].filter(e => {
      const r = rect(e);
      return e.children.length === 0 && e.textContent.trim() && r.bottom <= b0.top + 5 && r.top > b0.top - 200 &&
        r.left >= b0.left - 20 && r.left < b0.left + b0.width / 2;
    }).sort((a, b) => parseFloat(getComputedStyle(b).fontSize) - parseFloat(getComputedStyle(a).fontSize))[0];
    const name = (head ? head.textContent : document.title).trim();
    const key = 'zalo-tro-ly:' + name;
    let tail = null;
    try { tail = JSON.parse(localStorage.getItem(key) || 'null'); } catch (e) {}
    const NOISE = /^(\/-\w+|:[>o]|:-\(\(|:-h|\d{1,3}|\+\d+|Tải về để xem lâu dài)$/;
    const lines = () => box.innerText.split('\n').map(s => s.trim()).filter(s => s && !NOISE.test(s));
    const J = a => '\n' + a.join('\n') + '\n';
    // ghép: phần cuối của "older" trùng phần đầu của "newer" thì nối không lặp
    const merge = (older, newer) => {
      if (J(newer).includes(J(older))) return newer;
      if (J(older).includes(J(newer))) return older;
      for (let k = Math.min(older.length, newer.length); k >= 3; k--) {
        let ok = true;
        for (let i = 0; i < k && ok; i++) ok = older[older.length - k + i] === newer[i];
        if (ok) return older.concat(newer.slice(k));
      }
      return older.concat(['…'], newer);
    };
    const found = a => tail && J(a).lastIndexOf(J(tail)) >= 0;
    let all = lines(), stall = 0;
    for (let i = 0; i < 20 && !found(all); i++) {
      say(`Zalo → Trợ lý: đang lấy tin… lượt ${i + 1}/20 (${all.length} dòng)`);
      box.scrollTop = -1e9;
      box.dispatchEvent(new WheelEvent('wheel', { deltaY: -3000, bubbles: true }));
      await sleep(1500);
      const m = merge(lines(), all);
      if (m.length === all.length) { if (++stall >= 2) break; } else stall = 0;
      all = m;
    }
    st.remove();
    let out = all, note = tail ? 'Không thấy điểm lần trước, lấy toàn bộ phần tải được.' : 'Lần đầu với nhóm này.';
    if (found(all)) {
      const A = J(all), T = J(tail);
      out = A.slice(A.lastIndexOf(T) + T.length).split('\n').filter(Boolean);
      note = 'Chỉ tin mới từ lần trước.';
    }
    // đổi "Hôm nay/Hôm qua" thành ngày cụ thể
    const day = n => { const d = new Date(Date.now() - n * 864e5); return d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' }); };
    out = out.map(s => s.replace(/Hôm nay$/, day(0)).replace(/Hôm qua$/, day(1)));
    const txt = `\n===== ${name} | lấy lúc ${new Date().toLocaleString('vi-VN')} | ${note} =====\n${out.join('\n')}\n`;
    const save = () => { try { localStorage.setItem(key, JSON.stringify(all.slice(-12))); } catch (e) {} };
    const d = document.createElement('div');
    d.style.cssText = 'position:fixed;top:10vh;bottom:10vh;left:15vw;right:15vw;z-index:2147483647;background:#fff;border:2px solid #0068ff;border-radius:8px;padding:12px;display:flex;flex-direction:column;gap:8px;font:14px sans-serif;box-shadow:0 8px 30px #0005';
    const h = document.createElement('b');
    h.textContent = out.length ? `${name}: ${out.length} dòng. ${note} Bấm Sao chép rồi dán vào CUỐI file của nhóm trên Drive.` : `${name}: không có tin mới từ lần trước.`;
    const t = document.createElement('textarea');
    t.value = txt; t.style.cssText = 'flex:1;font:12px monospace';
    const row = document.createElement('div');
    const btn = (label, fn) => { const b = document.createElement('button'); b.textContent = label; b.style.cssText = 'margin-right:8px;padding:6px 14px;font:14px sans-serif;cursor:pointer'; b.onclick = () => fn(b); row.append(b); };
    btn('Sao chép', b => { t.select(); save(); const ok = () => b.textContent = 'Đã sao chép ✓'; navigator.clipboard.writeText(txt).then(ok, () => { document.execCommand('copy'); ok(); }); });
    btn('Tải file .txt', () => { save(); const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([txt], { type: 'text/plain' })); a.download = `${name} ${new Date().toISOString().slice(0, 10)}.txt`; a.click(); });
    btn('Lấy lại từ đầu', () => { try { localStorage.removeItem(key); } catch (e) {} d.remove(); say('Đã quên mốc cũ. Bấm nút lần nữa để lấy toàn bộ.', 5000); document.body.append(st); });
    btn('Đóng', () => d.remove());
    d.append(h, t, row);
    document.body.append(d);
  } catch (e) {
    say('Zalo → Trợ lý lỗi: ' + e.message + ' — chụp màn hình gửi trợ lý.', 15000);
  }
})();
