"""
SQL Dependency Visualizer
Phân tích các file .sql để vẽ sơ đồ mạng nhện:
- Node xanh dương = file SQL
- Node cam = tên bảng
- Cạnh xanh lá = CREATE (file tạo ra bảng)
- Cạnh đỏ = USE (file sử dụng bảng)
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from collections import defaultdict

# Fix Windows console encoding
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from pyvis.network import Network
except ImportError:
    print("Thiếu thư viện. Chạy: pip install pyvis networkx")
    exit(1)


# ── 1. PARSE SQL ──────────────────────────────────────────────────────────────

# Patterns để bắt tên bảng (có thể có schema: dbo.TableName hoặc [dbo].[TableName])
_TABLE_PATTERN = r"(?:\[?[\w]+\]?\.)?\[?([\w]+)\]?"

CREATE_RE = re.compile(
    rf"CREATE\s+(?:TABLE|VIEW)\s+{_TABLE_PATTERN}",
    re.IGNORECASE,
)
FROM_RE = re.compile(
    rf"FROM\s+{_TABLE_PATTERN}",
    re.IGNORECASE,
)
JOIN_RE = re.compile(
    rf"JOIN\s+{_TABLE_PATTERN}",
    re.IGNORECASE,
)
INSERT_RE = re.compile(
    rf"INSERT\s+INTO\s+{_TABLE_PATTERN}",
    re.IGNORECASE,
)
UPDATE_RE = re.compile(
    rf"UPDATE\s+{_TABLE_PATTERN}",
    re.IGNORECASE,
)
EXEC_RE = re.compile(
    rf"(?:EXEC|EXECUTE)\s+{_TABLE_PATTERN}",
    re.IGNORECASE,
)

# Các từ khóa SQL / system table cần bỏ qua
IGNORE_NAMES = {
    "SELECT", "WHERE", "SET", "AS", "ON", "AND", "OR", "NOT", "IN",
    "EXISTS", "CASE", "WHEN", "THEN", "ELSE", "END", "NULL", "IS",
    "DISTINCT", "TOP", "WITH", "BY", "HAVING", "UNION", "ALL",
    "sys", "INFORMATION_SCHEMA", "dbo", "OPENQUERY", "OPENJSON",
    "STRING_SPLIT", "CHANGETABLE", "DELETED", "INSERTED",
}


def strip_comments(sql: str) -> str:
    """Xóa comment -- và /* */ khỏi SQL."""
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return sql


def parse_sql_file(filepath: Path) -> dict:
    """Trả về dict {creates: set, uses: set} cho một file SQL."""
    text = strip_comments(filepath.read_text(encoding="utf-8", errors="ignore"))
    creates = {m.group(1) for m in CREATE_RE.finditer(text)
               if m.group(1).upper() not in IGNORE_NAMES}
    uses = set()
    for pattern in (FROM_RE, JOIN_RE, INSERT_RE, UPDATE_RE):
        for m in pattern.finditer(text):
            name = m.group(1)
            if name.upper() not in IGNORE_NAMES and name not in creates:
                uses.add(name)
    return {"creates": creates, "uses": uses}


# ── 2. BUILD GRAPH DATA ───────────────────────────────────────────────────────

def build_graph(sql_dir: str) -> dict:
    sql_dir = Path(sql_dir)
    files = list(sql_dir.rglob("*.sql"))
    if not files:
        print(f"Không tìm thấy file .sql nào trong: {sql_dir}")
        return {}

    file_data = {}
    all_tables: dict[str, dict] = defaultdict(lambda: {"created_by": [], "used_by": []})

    for f in files:
        rel = f.relative_to(sql_dir).as_posix()
        parsed = parse_sql_file(f)
        file_data[rel] = parsed
        for tbl in parsed["creates"]:
            all_tables[tbl]["created_by"].append(rel)
        for tbl in parsed["uses"]:
            all_tables[tbl]["used_by"].append(rel)

    return {"files": file_data, "tables": dict(all_tables)}


# ── 3. RENDER HTML ────────────────────────────────────────────────────────────

def render_html(graph_data: dict, output_path: str):
    net = Network(
        height="95vh",
        width="100%",
        bgcolor="#1a1a2e",
        font_color="#e0e0e0",
        directed=True,
    )
    net.set_options(json.dumps({
        "physics": {
            "enabled": True,
            "barnesHut": {
                "gravitationalConstant": -8000,
                "centralGravity": 0.3,
                "springLength": 150,
            }
        },
        "edges": {
            "smooth": {"type": "curvedCW", "roundness": 0.2},
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.8}},
        },
        "interaction": {
            "hover": True,
            "tooltipDelay": 100,
            "navigationButtons": True,
            "keyboard": True,
        }
    }))

    files = graph_data.get("files", {})
    tables = graph_data.get("tables", {})

    # Node: file SQL (xanh dương)
    for fname in files:
        creates_count = len(files[fname]["creates"])
        uses_count = len(files[fname]["uses"])
        tooltip = (
            f"<b>{fname}</b><br>"
            f"Tạo {creates_count} bảng, dùng {uses_count} bảng"
        )
        net.add_node(
            f"file::{fname}",
            label=Path(fname).name,
            title=tooltip,
            color={"background": "#4f8ef7", "border": "#2563eb"},
            shape="box",
            size=20,
            font={"size": 13, "color": "#ffffff"},
        )

    # Node: table (cam)
    for tbl, info in tables.items():
        created_by = ", ".join(info["created_by"]) or "(không rõ)"
        used_by = ", ".join(info["used_by"]) or "(không ai dùng)"
        tooltip = (
            f"<b>Table: {tbl}</b><br>"
            f"Tạo bởi: {created_by}<br>"
            f"Dùng bởi: {used_by}"
        )
        net.add_node(
            f"table::{tbl}",
            label=tbl,
            title=tooltip,
            color={"background": "#f97316", "border": "#c2410c"},
            shape="ellipse",
            size=16,
            font={"size": 12, "color": "#ffffff"},
        )

    # Edge: CREATE (xanh lá)
    for fname, parsed in files.items():
        for tbl in parsed["creates"]:
            net.add_edge(
                f"file::{fname}",
                f"table::{tbl}",
                color="#22c55e",
                title="CREATE",
                width=2,
                label="CREATE",
                font={"size": 9, "color": "#22c55e"},
            )

    # Edge: USE (đỏ, từ bảng → file để phân biệt chiều)
    for fname, parsed in files.items():
        for tbl in parsed["uses"]:
            if f"table::{tbl}" in [n["id"] for n in net.nodes]:
                net.add_edge(
                    f"table::{tbl}",
                    f"file::{fname}",
                    color="#f43f5e",
                    title="USED BY",
                    width=1.5,
                    dashes=True,
                    label="USE",
                    font={"size": 9, "color": "#f43f5e"},
                )

    net.write_html(output_path)
    _inject_click_highlight(output_path)
    print(f"\n✓ Đã xuất: {output_path}")


# ── 4. CLICK-HIGHLIGHT INJECTION ─────────────────────────────────────────────

CLICK_HIGHLIGHT_JS = """
<style>
  /* ── Search box ── */
  #search-wrap {
    position: fixed; top: 14px; left: 50%; transform: translateX(-50%);
    z-index: 999; display: flex; align-items: center; gap: 6px;
  }
  #search-input {
    width: 280px; padding: 8px 14px;
    background: rgba(20,20,40,0.95); border: 1px solid #4f8ef7;
    border-radius: 20px; color: #fff; font: 14px sans-serif;
    outline: none; transition: border-color 0.2s, box-shadow 0.2s;
  }
  #search-input::placeholder { color: #556; }
  #search-input:focus { border-color: #7eb3ff; box-shadow: 0 0 0 3px rgba(79,142,247,0.25); }
  #search-clear {
    background: #334; border: none; border-radius: 50%; color: #aaa;
    width: 28px; height: 28px; cursor: pointer; font-size: 16px;
    display: none; align-items: center; justify-content: center;
  }
  #search-clear:hover { background: #445; color: #fff; }
  #search-count {
    font: 12px sans-serif; color: #7eb3ff; white-space: nowrap;
    min-width: 80px; text-align: left; display: none;
  }

  /* ── Legend ── */
  #legend {
    position: fixed; top: 14px; right: 14px; z-index: 999;
    background: rgba(20,20,40,0.92); border: 1px solid #334;
    border-radius: 8px; padding: 12px 16px; color: #ccc; font: 13px sans-serif;
  }
  #legend b { color: #fff; display: block; margin-bottom: 6px; font-size: 14px; }
  #legend .row { display: flex; align-items: center; margin: 4px 0; gap: 8px; }
  #legend .dot { width: 14px; height: 14px; border-radius: 3px; flex-shrink: 0; }

  /* ── Hint ── */
  #hint {
    position: fixed; bottom: 14px; left: 50%; transform: translateX(-50%);
    background: rgba(20,20,40,0.85); border: 1px solid #334;
    border-radius: 20px; padding: 6px 18px; color: #aaa; font: 12px sans-serif;
    pointer-events: none; transition: opacity 0.3s;
  }
</style>

<!-- Search -->
<div id="search-wrap">
  <input id="search-input" type="text" placeholder="🔍  Tìm tên bảng hoặc file SQL..." spellcheck="false" />
  <button id="search-clear" title="Xóa">✕</button>
  <span id="search-count"></span>
</div>

<!-- Legend -->
<div id="legend">
  <b>SQL Dependency Map</b>
  <div class="row"><div class="dot" style="background:#4f8ef7;border:2px solid #2563eb"></div> File SQL</div>
  <div class="row"><div class="dot" style="background:#f97316;border-radius:50%;border:2px solid #c2410c"></div> Table / View</div>
  <div class="row"><div style="width:28px;height:2px;background:#22c55e"></div> CREATE</div>
  <div class="row"><div style="width:28px;height:2px;background:#f43f5e;border-top:2px dashed #f43f5e"></div> USED BY</div>
</div>

<div id="hint">Click node để highlight liên kết &nbsp;·&nbsp; Click nền để reset</div>

<script>
window.addEventListener('load', function () {
  setTimeout(function () {
    if (typeof network === 'undefined' || typeof nodes === 'undefined') return;

    // ── lưu màu gốc ──────────────────────────────────────────────
    var origNode = {};
    nodes.forEach(function (n) {
      origNode[n.id] = {
        color: JSON.parse(JSON.stringify(n.color || {})),
        font:  JSON.parse(JSON.stringify(n.font  || {})),
      };
    });
    var origEdge = {};
    edges.forEach(function (e) {
      origEdge[e.id] = {
        color: typeof e.color === 'string'
          ? e.color : JSON.parse(JSON.stringify(e.color || {})),
        font:  JSON.parse(JSON.stringify(e.font || {})),
        width: e.width || 1,
        dashes: e.dashes || false,
      };
    });

    var DIM_NODE  = { color: { background: '#252535', border: '#353550' }, font: { color: '#44445a' } };
    var DIM_EDGE  = { color: { color: '#2a2a40', opacity: 0.2 }, font: { color: '#2a2a40' }, width: 0.5, dashes: false };
    var RING_NODE = { color: { background: '#fef08a', border: '#facc15' }, font: { color: '#1a1a2e' } }; // vàng: kết quả search

    var mode = 'none'; // 'none' | 'click' | 'search'

    // ── helpers ──────────────────────────────────────────────────
    function dimAll() {
      nodes.update(nodes.getIds().map(function(id){ return Object.assign({id:id}, DIM_NODE); }));
      edges.update(edges.getIds().map(function(id){ return Object.assign({id:id}, DIM_EDGE); }));
    }

    function restoreAll() {
      nodes.update(nodes.getIds().map(function(id){ return Object.assign({id:id}, origNode[id]); }));
      edges.update(edges.getIds().map(function(id){ return Object.assign({id:id}, origEdge[id]); }));
    }

    function highlightGroup(centerIds) {
      // centerIds: array of node ids cần highlight cùng với neighbors
      var keepNodes = new Set();
      var keepEdges = new Set();
      centerIds.forEach(function(nodeId) {
        keepNodes.add(nodeId);
        network.getConnectedNodes(nodeId).forEach(function(n){ keepNodes.add(n); });
        network.getConnectedEdges(nodeId).forEach(function(e){ keepEdges.add(e); });
      });

      nodes.update(nodes.getIds().map(function(id) {
        if (!keepNodes.has(id)) return Object.assign({id:id}, DIM_NODE);
        return { id:id, color: origNode[id].color, font: origNode[id].font };
      }));
      edges.update(edges.getIds().map(function(id) {
        if (!keepEdges.has(id)) return Object.assign({id:id}, DIM_EDGE);
        return { id:id, color: origEdge[id].color, font: origEdge[id].font,
                 width: origEdge[id].width, dashes: origEdge[id].dashes };
      }));

      // thêm vòng vàng cho chính các node match
      centerIds.forEach(function(id) {
        nodes.update([Object.assign({id:id}, RING_NODE)]);
      });
    }

    // ── CLICK ────────────────────────────────────────────────────
    network.on('click', function (params) {
      if (mode === 'search') return; // search đang active → click không override
      if (params.nodes.length > 0) {
        highlightGroup([params.nodes[0]]);
        mode = 'click';
        document.getElementById('hint').style.opacity = '0.4';
      } else if (mode === 'click') {
        restoreAll();
        mode = 'none';
        document.getElementById('hint').style.opacity = '1';
      }
    });

    // ── SEARCH ───────────────────────────────────────────────────
    var searchInput = document.getElementById('search-input');
    var searchClear = document.getElementById('search-clear');
    var searchCount = document.getElementById('search-count');

    function doSearch(query) {
      query = query.trim().toLowerCase();
      if (!query) {
        restoreAll();
        mode = 'none';
        searchClear.style.display = 'none';
        searchCount.style.display = 'none';
        document.getElementById('hint').style.opacity = '1';
        return;
      }

      searchClear.style.display = 'flex';
      mode = 'search';
      document.getElementById('hint').style.opacity = '0.3';

      // tìm node có label chứa query
      var matched = [];
      nodes.forEach(function(n) {
        var label = (n.label || '').toLowerCase();
        if (label.includes(query)) matched.push(n.id);
      });

      if (matched.length === 0) {
        dimAll();
        searchCount.style.display = 'inline';
        searchCount.textContent = 'Không tìm thấy';
        searchCount.style.color = '#f87171';
        return;
      }

      searchCount.style.display = 'inline';
      searchCount.textContent = matched.length + ' kết quả';
      searchCount.style.color = '#7eb3ff';

      highlightGroup(matched);

      // fit view vào các node match
      network.fit({ nodes: matched, animation: { duration: 500, easingFunction: 'easeInOutQuad' } });
    }

    searchInput.addEventListener('input', function() { doSearch(this.value); });

    searchInput.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') { clearSearch(); }
    });

    searchClear.addEventListener('click', clearSearch);

    function clearSearch() {
      searchInput.value = '';
      doSearch('');
      searchInput.focus();
    }

    // Ctrl+F / Cmd+F → focus search
    document.addEventListener('keydown', function(e) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        e.preventDefault();
        searchInput.focus();
        searchInput.select();
      }
    });

  }, 400);
});
</script>
"""


def _inject_click_highlight(html_path: str):
    """Đọc file HTML pyvis và nhúng JS click-highlight vào trước </body>."""
    content = Path(html_path).read_text(encoding="utf-8")
    if "</body>" not in content:
        return
    content = content.replace("</body>", CLICK_HIGHLIGHT_JS + "\n</body>", 1)
    Path(html_path).write_text(content, encoding="utf-8")


# ── 5. REPORT TEXT ────────────────────────────────────────────────────────────

def print_report(graph_data: dict):
    tables = graph_data.get("tables", {})
    files = graph_data.get("files", {})

    print(f"\n{'='*60}")
    print(f"  Tổng: {len(files)} file SQL | {len(tables)} bảng")
    print(f"{'='*60}")

    for tbl, info in sorted(tables.items()):
        print(f"\n[TABLE] {tbl}")
        if info["created_by"]:
            print(f"  CREATE : {', '.join(info['created_by'])}")
        else:
            print(f"  CREATE : (không tìm thấy)")
        if info["used_by"]:
            print(f"  USED BY: {', '.join(info['used_by'])}")

    orphan_files = [f for f, d in files.items() if not d["creates"] and not d["uses"]]
    if orphan_files:
        print(f"\n[!] File không detect được bảng nào: {', '.join(orphan_files)}")


# ── 6. MAIN ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SQL Dependency Visualizer")
    parser.add_argument(
        "sql_dir",
        nargs="?",
        default=".",
        help="Thư mục chứa file .sql (mặc định: thư mục hiện tại)",
    )
    parser.add_argument(
        "--output",
        default="sql_diagram.html",
        help="Tên file HTML output (mặc định: sql_diagram.html)",
    )
    args = parser.parse_args()

    print(f"Đang quét: {Path(args.sql_dir).resolve()}")
    graph_data = build_graph(args.sql_dir)

    if graph_data:
        print_report(graph_data)
        render_html(graph_data, args.output)
        print(f"\nMở file '{args.output}' bằng browser để xem sơ đồ.")
