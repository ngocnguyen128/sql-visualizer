"""
app.py — SQL Dependency Visualizer (Streamlit)
Chạy: streamlit run app.py
"""

import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path

from sql_visualizer import build_graph, build_graph_from_contents, render_html_string

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SQL Dependency Visualizer",
    page_icon="🕸️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  /* ẩn footer mặc định của Streamlit */
  footer { visibility: hidden; }
  /* nút analyze full-width */
  div.stButton > button { width: 100%; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar: legend + stats ───────────────────────────────────────────────────
with st.sidebar:
    st.title("🕸️ SQL Visualizer")
    st.caption("Phân tích dependency giữa SQL files và bảng dữ liệu")
    st.divider()

    st.markdown("""
**Màu sắc node:**

🔵 &nbsp;File SQL
🟠 &nbsp;Table
🟣 &nbsp;Stored Procedure
🟢 &nbsp;View
🔵 &nbsp;Function (cyan)

**Cạnh nối:**
— xanh lá = **CREATE**
– – đỏ = **USED BY**
""")
    st.divider()

    if "stats" in st.session_state:
        s = st.session_state.stats
        st.metric("📄 Objects", s.get("files", 0))
        st.metric("🗃️ Tables / Objects", s.get("tables", 0))
        if s.get("source"):
            st.caption(f"Nguồn: {s['source']}")
    else:
        st.info("Chưa có dữ liệu. Chọn nguồn và nhấn **Analyze**.")

    st.divider()
    st.caption("**Phím tắt trong diagram:**  \nCtrl+F → search  \nEsc → reset")


# ── Main ──────────────────────────────────────────────────────────────────────
st.header("🕸️ SQL Dependency Visualizer")

tab_file, tab_db = st.tabs(["📁  Local SQL Files", "🗄️  SQL Server"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — LOCAL FILES
# ══════════════════════════════════════════════════════════════════════════════
with tab_file:
    col_opt, col_gap = st.columns([2, 3])
    with col_opt:
        source_type = st.radio(
            "Cách chọn file",
            ["📂 Đường dẫn folder", "⬆️ Upload file .sql"],
            horizontal=True,
        )

    if source_type == "⬆️ Upload file .sql":
        uploaded = st.file_uploader(
            "Kéo thả hoặc chọn nhiều file .sql",
            type=["sql"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
        ready = bool(uploaded)
        btn_label = f"🔍 Analyze {len(uploaded)} file(s)" if uploaded else "🔍 Analyze"

        if st.button(btn_label, disabled=not ready, key="btn_upload"):
            with st.spinner("Đang parse SQL..."):
                contents = {
                    f.name: f.read().decode("utf-8", errors="ignore")
                    for f in uploaded
                }
                graph_data = build_graph_from_contents(contents)

            if not graph_data or not graph_data.get("files"):
                st.warning("Không tìm thấy bảng nào trong các file đã upload.")
            else:
                st.session_state.graph_html = render_html_string(graph_data)
                st.session_state.stats = {
                    "files":  len(graph_data["files"]),
                    "tables": len(graph_data["tables"]),
                    "source": f"{len(uploaded)} file(s) uploaded",
                }
                st.rerun()

    else:  # folder path
        folder_path = st.text_input(
            "Đường dẫn folder chứa file .sql",
            placeholder=r"VD: C:\projects\my_sql  hoặc  E:\etl\scripts",
        )
        ready = bool(folder_path and Path(folder_path).is_dir())

        if folder_path and not Path(folder_path).is_dir():
            st.error("Đường dẫn không tồn tại hoặc không phải folder.")

        if st.button("🔍 Analyze folder", disabled=not ready, key="btn_folder"):
            with st.spinner(f"Đang quét {folder_path} ..."):
                sql_files = list(Path(folder_path).rglob("*.sql"))
                if not sql_files:
                    st.warning("Không tìm thấy file .sql nào trong folder này.")
                else:
                    graph_data = build_graph(folder_path)

            if graph_data and graph_data.get("files"):
                st.session_state.graph_html = render_html_string(graph_data)
                st.session_state.stats = {
                    "files":  len(graph_data["files"]),
                    "tables": len(graph_data["tables"]),
                    "source": folder_path,
                }
                st.rerun()

    # ── Hiển thị diagram ──
    if "graph_html" in st.session_state:
        st.divider()
        components.html(st.session_state.graph_html, height=680, scrolling=False)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — SQL SERVER
# ══════════════════════════════════════════════════════════════════════════════
with tab_db:
    try:
        from db_analyzer import list_databases, analyze_database
        _db_available = True
    except Exception as e:
        _db_available = False
        st.error(f"Không load được db_analyzer: {e}")

    if _db_available:
        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            server = st.text_input(
                "🖥️ Server",
                placeholder=r"localhost  hoặc  MYPC\SQLEXPRESS",
                key="db_server",
            )

        with col3:
            st.markdown("<br>", unsafe_allow_html=True)  # căn đều nút
            load_db_btn = st.button("Load DBs", key="btn_load_db",
                                    disabled=not bool(server))

        # Load danh sách database
        if load_db_btn and server:
            with st.spinner(f"Kết nối {server}..."):
                try:
                    dbs = list_databases(server)
                    st.session_state.db_list = dbs
                    st.session_state.db_server = server
                    if not dbs:
                        st.warning("Kết nối thành công nhưng không tìm thấy database nào.")
                except Exception as e:
                    st.error(f"Lỗi kết nối: {e}")

        with col2:
            db_options = st.session_state.get("db_list", [])
            selected_db = st.selectbox(
                "🗄️ Database",
                db_options,
                disabled=not db_options,
                key="db_selected",
            )

        # Thông tin kết nối hiện tại
        if db_options:
            st.success(
                f"✅ Đã kết nối **{st.session_state.get('db_server', server)}** "
                f"— {len(db_options)} database(s) khả dụng  |  Windows Auth"
            )

        analyze_disabled = not (db_options and selected_db)
        if st.button("🔍 Analyze Database", disabled=analyze_disabled, key="btn_analyze_db"):
            with st.spinner(f"Đang phân tích {selected_db}..."):
                try:
                    graph_data = analyze_database(
                        st.session_state.get("db_server", server),
                        selected_db,
                    )
                    if not graph_data or not graph_data.get("files"):
                        st.warning("Không tìm thấy stored procedure / view / function nào.")
                    else:
                        st.session_state.graph_html_db = render_html_string(graph_data)
                        st.session_state.stats = {
                            "files":  len(graph_data["files"]),
                            "tables": len(graph_data["tables"]),
                            "source": f"{server} › {selected_db}",
                        }
                        st.rerun()
                except Exception as e:
                    st.error(f"Lỗi phân tích: {e}")

        # ── Hiển thị diagram ──
        if "graph_html_db" in st.session_state:
            st.divider()
            components.html(st.session_state.graph_html_db, height=680, scrolling=False)
