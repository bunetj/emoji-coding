"""
emoji_coding.py — symbol tagger, browser UI, pure stdlib
Run:  python emoji_coding.py
Then open: http://127.0.0.1:41827
"""

import json, os, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "tables": {
        "reactions": {
            "symbols": {"🤮": "disgust", "▶": "quote", "§": "reference"},
            "order": ["🤮", "▶", "§"],
            "disabled": []
        },
        "themes": {
            "symbols": {"#": "tags", "!": "important"},
            "order": ["#", "!"],
            "disabled": []
        }
    }
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8">
<title>Symbol Tagger</title>
<style>
  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body { font-family: system-ui, sans-serif; margin: 0; padding: 10px; background:#1e1e1e; color:#ddd; display:flex; flex-direction:column; }
  .bar { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:8px; }
  select, button, input { font: inherit; padding:4px 8px; background:#2a2a2a; color:#ddd; border:1px solid #444; border-radius:4px; }
  button:hover { background:#333; cursor:pointer; }
  .grow { flex:1; }
  #chips { display:flex; gap:14px; align-items:center; flex-wrap:wrap; padding:6px 2px; margin-bottom:8px; border-bottom:1px solid #333; min-height:34px; }
  .chip { display:flex; gap:6px; align-items:center; }
  .chip .sym { font-size:16px; padding:2px 10px; }
  .chip .lbl { color:#888; font-size:12px; }

  #wrap { flex:1 1 auto; display:flex; flex-direction:row; min-height:0; }
  #left, #right { min-width:0; min-height:0; display:flex; flex-direction:column; }
  #left { flex:1 1 50%; }
  #right { flex:1 1 50%; }
  #splitter { flex:0 0 8px; cursor:col-resize; background:#2a2a2a; border-left:1px solid #333; border-right:1px solid #333; }
  #splitter:hover { background:#3a3a3a; }

  textarea { width:100%; height:100%; background:#252525; color:#eee; border:1px solid #444; border-radius:6px; padding:8px; font: 14px/1.4 ui-monospace, monospace; resize:none; }
  #out { overflow:auto; background:#252525; border:1px solid #444; border-radius:6px; padding:8px; height:100%; }
  table { border-collapse: collapse; width:100%; font-size:14px; }
  th, td { border:1px solid #3a3a3a; padding:6px 8px; text-align:left; vertical-align:top; white-space:pre-wrap; }
  th { background:#2f2f2f; position:sticky; top:0; }
  .modal { display:none; position:fixed; inset:0; background:rgba(0,0,0,.6); z-index:1000; align-items:center; justify-content:center; }
  .modal.open { display:flex; }
  .modal > div { background:#252525; border:1px solid #444; border-radius:8px; padding:16px; min-width:540px; max-height:80vh; overflow:auto; }
  .modal input { width:100%; }
  .modal td.acts { white-space: nowrap; width:1%; }
  .modal td.acts button { padding:0 6px; margin:0 1px; line-height:1.4; }
  .modal table td, .modal table th { padding:2px 6px; }
  .modal table input[type=checkbox] { margin:0; }
  .modal table input[type=text], .modal table input:not([type]) { padding:2px 6px; }
  .row { display:flex; gap:8px; align-items:center; }
</style></head>
<body>

<div class="bar">
  <span class="grow"></span>
  <span>themes:</span>
  <select id="tbl"></select>
  <button onclick="openEditor()">edit</button>
  <button onclick="copyOutput()">📋 copy</button>
</div>

<div id="chips"></div>

<div id="wrap">
  <div id="left"><textarea id="inp" placeholder="Paste raw notes here..."></textarea></div>
  <div id="splitter"></div>
  <div id="right"><div id="out"></div></div>
</div>

<div id="edModal" class="modal">
  <div>
    <h3 id="edTitle">Edit table</h3>
    <div style="margin:10px 0;">
      <label>Table name: <input id="edTableName"></label>
    </div>
    <table>
      <thead><tr><th>on</th><th>Symbol</th><th>Column name</th><th></th></tr></thead>
      <tbody id="edRows"></tbody>
    </table>
    <div class="row" style="margin-top:12px;">
      <button onclick="addRow()">+ add row</button>
      <span class="grow"></span>
      <button onclick="deleteCurrentTable()" style="color:#e88">delete table</button>
      <button onclick="saveEditor()">save</button>
      <button onclick="closeEditor()">cancel</button>
    </div>
  </div>
</div>

<script>
const API = '/api/config';
const LS_TEXT = 'tagger_text';
const LS_TABLE = 'tagger_table';
let CFG = { tables: {} };

/* ---------- modal helpers ---------- */
function closeModal(id) { const m = document.getElementById(id); if (m) m.classList.remove('open'); }
function openModal(id)  { const m = document.getElementById(id); if (m) m.classList.add('open'); }

/* ---------- auto-save ---------- */
function saveText() {
  try { localStorage.setItem(LS_TEXT, document.getElementById('inp').value); } catch(e){}
}
function saveTableName(name) {
  try { localStorage.setItem(LS_TABLE, name); } catch(e){}
}

/* ---------- boot ---------- */
async function boot() {
  CFG = await (await fetch(API)).json();
  if (!CFG.tables) CFG.tables = {};

  const savedTable = localStorage.getItem(LS_TABLE);
  buildTableDropdown(savedTable);

  const savedText = localStorage.getItem(LS_TEXT);
  if (savedText) document.getElementById('inp').value = savedText;

  document.getElementById('inp').addEventListener('input', () => {
    saveText();
    render();
  });
  render();
}

/* ---------- table dropdown ---------- */
function buildTableDropdown(selectName) {
  const sel = document.getElementById('tbl');
  sel.innerHTML = '';
  const names = Object.keys(CFG.tables);

  const plus = document.createElement('option');
  plus.value = '__new__'; plus.textContent = '+ create';
  sel.appendChild(plus);

  for (const n of names) {
    const o = document.createElement('option');
    o.value = n; o.textContent = n;
    sel.appendChild(o);
  }

  sel.onchange = e => {
    if (e.target.value === '__new__') {
      const name = prompt('New table name:');
      if (!name) { if (names.length) sel.value = names[0]; return; }
      if (CFG.tables[name]) { alert('Exists'); if (names.length) sel.value = names[0]; return; }
      CFG.tables[name] = { symbols:{}, order:[], disabled:[] };
      saveCfg().then(() => {
        buildTableDropdown(name);
        saveTableName(name);
        openEditor();
      });
    } else {
      saveTableName(e.target.value);
      render();
    }
  };

  if (selectName && CFG.tables[selectName]) sel.value = selectName;
  else if (names.length) sel.value = names[0];

  saveTableName(sel.value);
}

function currentTableName() { return document.getElementById('tbl').value; }
function currentTable() { return CFG.tables[currentTableName()] || { symbols:{}, order:[], disabled:[] }; }
function activeSymbols(t) {
  const dis = t.disabled || [];
  const out = {};
  Object.keys(t.symbols || {}).forEach(s => { if (dis.indexOf(s) === -1) out[s] = t.symbols[s]; });
  return out;
}
function activeOrder(t) {
  const dis = t.disabled || [];
  return (t.order || []).filter(s => dis.indexOf(s) === -1);
}

/* ---------- parse ---------- */
function parse(text, symbols) {
  const syms = Object.keys(symbols).sort((a, b) => b.length - a.length);
  if (!syms.length) return [];

  const rows = [];
  const blocks = text.split(/\n\s*\n/);

  for (const block of blocks) {
    const lines = block.split(/\r?\n/);
    if (!lines.length) continue;

    const cells = {};
    let curSym = null;

    for (const line of lines) {
      let startSym = null;
      for (const s of syms) {
        if (line.startsWith(s)) { startSym = s; break; }
      }

      if (startSym) {
        curSym = startSym;
        const rest = line.slice(startSym.length);
        cells[curSym] = cells[curSym] ? cells[curSym] + '\n' + rest : rest;
      } else if (curSym !== null) {
        cells[curSym] += '\n' + line;
      }
    }

    if (Object.keys(cells).length) {
      const row = {};
      for (const sym of Object.keys(cells)) {
        row[sym] = cells[sym].trim();
      }
      rows.push(row);
    }
  }
  return rows;
}

function toWide(rows, symbols, order) {
  const header = order.map(s => s + ' ' + (symbols[s] || s));
  const out = [header];
  for (const row of rows) {
    out.push(order.map(s => row[s] || ''));
  }
  return out;
}

/* ---------- render ---------- */
function render() {
  const t = currentTable();
  const chips = document.getElementById('chips');
  chips.innerHTML = '';
  activeOrder(t).forEach(sym => {
    const wrap = document.createElement('div');
    wrap.className = 'chip';
    const b = document.createElement('button');
    b.className = 'sym'; b.textContent = sym;
    b.title = 'Insert "' + sym + '"';
    b.onclick = () => insertAtCursor(sym);
    const lbl = document.createElement('span');
    lbl.className = 'lbl'; lbl.textContent = '→ ' + (t.symbols[sym] || '');
    wrap.appendChild(b); wrap.appendChild(lbl);
    chips.appendChild(wrap);
  });

  const text = document.getElementById('inp').value;
  const syms = activeSymbols(t);
  const order = activeOrder(t);
  const rows = parse(text, syms);
  const wide = toWide(rows, syms, order);
  const out = document.getElementById('out');
  if (!wide.length || !wide[0] || !wide[0].length) { out.innerHTML = '<i>No output</i>'; return; }
  let html = '<table><thead><tr>' + wide[0].map(h => '<th>'+esc(h)+'</th>').join('') + '</tr></thead><tbody>';
  for (let i=1;i<wide.length;i++) {
    html += '<tr>' + wide[i].map(c => '<td>'+esc(c)+'</td>').join('') + '</tr>';
  }
  html += '</tbody></table>';
  out.innerHTML = html;
}

function copyOutput() {
  const t = currentTable();
  const syms = activeSymbols(t);
  const order = activeOrder(t);
  const rows = parse(document.getElementById('inp').value, syms);
  const wide = toWide(rows, syms, order);
  if (!wide.length) return;
  const tsv = wide.map(r => r.map(c => String(c || '').replace(/\t/g, ' ').replace(/\n/g, ' ')).join('\t')).join('\n');
  navigator.clipboard.writeText(tsv);
}

function esc(s) { return (s||'').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
function escAttr(s) { return (s||'').replace(/"/g,'&quot;'); }

function insertAtCursor(s) {
  const ta = document.getElementById('inp');
  const start = ta.selectionStart ?? ta.value.length;
  const end = ta.selectionEnd ?? ta.value.length;

  const before = ta.value.slice(0, start);
  const needNL = before.length > 0 && !before.endsWith('\n');

  const ins = (needNL ? '\n' : '') + s;
  ta.value = ta.value.slice(0, start) + ins + ta.value.slice(end);
  const pos = start + ins.length;
  ta.setSelectionRange(pos, pos);
  ta.focus();
  saveText();
  render();
}

/* ---------- config ---------- */
function saveCfg() {
  return fetch(API, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(CFG)});
}

/* ---------- editor ---------- */
let ED = { table: null, draft: null };

function openEditor() {
  const name = currentTableName();
  if (!name || !CFG.tables[name]) { alert('No table'); return; }
  ED.table = name;
  ED.draft = JSON.parse(JSON.stringify(CFG.tables[name]));
  if (!ED.draft.symbols) ED.draft.symbols = {};
  if (!ED.draft.order) ED.draft.order = Object.keys(ED.draft.symbols);
  if (!ED.draft.disabled) ED.draft.disabled = [];
  document.getElementById('edTitle').textContent = 'Editing: ' + name;
  document.getElementById('edTableName').value = name;
  drawRows();
  openModal('edModal');
}
function closeEditor() { closeModal('edModal'); }

function drawRows() {
  const tb = document.getElementById('edRows');
  tb.innerHTML = '';
  ED.draft.order.forEach((sym, i) => {
    const enabled = (ED.draft.disabled || []).indexOf(sym) === -1;
    const symVal = sym.startsWith('__new') ? '' : sym;
    const nameVal = ED.draft.symbols[sym] || '';
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td style="width:28px; text-align:center"><input type="checkbox" data-i="${i}" data-k="on" ${enabled ? 'checked' : ''}></td>
      <td><input value="${escAttr(symVal)}" placeholder="symbol" data-i="${i}" data-k="sym"></td>
      <td><input value="${escAttr(nameVal)}" placeholder="column name" data-i="${i}" data-k="name"></td>
      <td class="acts">
        <button data-act="up" data-i="${i}">↑</button>
        <button data-act="down" data-i="${i}">↓</button>
        <button data-act="del" data-i="${i}">✕</button>
      </td>`;
    tb.appendChild(tr);
  });
  tb.querySelectorAll('input').forEach(inp => {
    inp.addEventListener('input', e => {
      const i = +e.target.dataset.i, k = e.target.dataset.k;
      if (k === 'on') {
        const sym = ED.draft.order[i];
        if (!ED.draft.disabled) ED.draft.disabled = [];
        const idx = ED.draft.disabled.indexOf(sym);
        if (e.target.checked) { if (idx !== -1) ED.draft.disabled.splice(idx, 1); }
        else { if (idx === -1) ED.draft.disabled.push(sym); }
      } else if (k === 'sym') {
        const old = ED.draft.order[i];
        const val = e.target.value;
        ED.draft.order[i] = val;
        ED.draft.symbols[val] = ED.draft.symbols[old] || '';
        delete ED.draft.symbols[old];
        if (ED.draft.disabled) {
          const j = ED.draft.disabled.indexOf(old);
          if (j !== -1) ED.draft.disabled[j] = val;
        }
      } else {
        const sym = ED.draft.order[i];
        ED.draft.symbols[sym] = e.target.value;
      }
    });
  });
  tb.querySelectorAll('button').forEach(b => {
    b.addEventListener('click', () => {
      const act = b.dataset.act, i = +b.dataset.i;
      if (act === 'up' && i > 0) {
        [ED.draft.order[i-1], ED.draft.order[i]] = [ED.draft.order[i], ED.draft.order[i-1]];
      } else if (act === 'down' && i < ED.draft.order.length-1) {
        [ED.draft.order[i+1], ED.draft.order[i]] = [ED.draft.order[i], ED.draft.order[i+1]];
      } else if (act === 'del') {
        const s = ED.draft.order[i];
        ED.draft.order.splice(i,1);
        delete ED.draft.symbols[s];
        if (ED.draft.disabled) {
          const j = ED.draft.disabled.indexOf(s);
          if (j !== -1) ED.draft.disabled.splice(j, 1);
        }
      }
      drawRows();
    });
  });
}

function addRow() {
  let n = 1; let key = '__new' + n;
  while (ED.draft.order.includes(key)) { n++; key = '__new' + n; }
  ED.draft.order.push(key);
  ED.draft.symbols[key] = '';
  drawRows();
  const inputs = document.querySelectorAll('#edRows input[data-k="sym"]');
  if (inputs.length) inputs[inputs.length - 1].focus();
}

function saveEditor() {
  const newName = document.getElementById('edTableName').value.trim();
  if (!newName) { alert('Table name required'); return; }

  const newTable = { symbols: {}, order: [], disabled: [] };

  for (const sym of ED.draft.order) {
    if (sym && !sym.startsWith('__new')) {
      newTable.order.push(sym);
      newTable.symbols[sym] = ED.draft.symbols[sym] || '';
    }
  }

  if (ED.draft.disabled) {
    for (const sym of ED.draft.disabled) {
      if (newTable.symbols[sym] !== undefined) {
        newTable.disabled.push(sym);
      }
    }
  }

  if (newName !== ED.table) {
    if (CFG.tables[newName]) { alert('A table with that name already exists'); return; }
    delete CFG.tables[ED.table];
  }

  CFG.tables[newName] = newTable;

  saveCfg().then(() => {
    buildTableDropdown(newName);
    saveTableName(newName);
    closeEditor();
    render();
  });
}

function deleteCurrentTable() {
  const name = ED.table;
  if (!name) return;
  if (!confirm('Delete table "' + name + '"?')) return;

  delete CFG.tables[name];
  saveCfg().then(() => {
    buildTableDropdown();
    closeEditor();
    render();
  });
}

/* ---------- splitter drag ---------- */
(function initSplitter() {
  const splitter = document.getElementById('splitter');
  const left = document.getElementById('left');
  const right = document.getElementById('right');
  const wrap = document.getElementById('wrap');
  let dragging = false;

  splitter.addEventListener('mousedown', e => {
    dragging = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });

  document.addEventListener('mousemove', e => {
    if (!dragging) return;
    const rect = wrap.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const pct = Math.max(10, Math.min(90, (x / rect.width) * 100));
    left.style.flex = '0 0 ' + pct + '%';
    right.style.flex = '1 1 auto';
  });

  document.addEventListener('mouseup', () => {
    dragging = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  });
})();

/* ---------- keyboard shortcuts ---------- */
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal.open').forEach(m => m.classList.remove('open'));
  }
});

/* ---------- go ---------- */
boot();
</script>
</body></html>
"""

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/plain; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            self._send(200, PAGE, "text/html; charset=utf-8")
        elif path == "/api/config":
            cfg = load_config()
            self._send(200, json.dumps(cfg, ensure_ascii=False), "application/json; charset=utf-8")
        else:
            self._send(404, "Not found")

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/config":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8")
            try:
                cfg = json.loads(raw)
                save_config(cfg)
                self._send(200, '{"ok":true}', "application/json; charset=utf-8")
            except Exception as e:
                self._send(400, json.dumps({"error": str(e)}), "application/json; charset=utf-8")
        else:
            self._send(404, "Not found")

    def log_message(self, fmt, *args):
        pass


def main():
    host = "127.0.0.1"
    port = 41827
    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    print(f"Symbol Tagger running at {url}")
    print("Press Ctrl+C to stop.")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()