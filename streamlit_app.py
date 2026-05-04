"""
BRD Agent — Local Test Interface
Drop this file in your project root (same level as main.py).
Run: streamlit run streamlit_app.py
"""

import base64
import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BRD Agent",
    page_icon="📄",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
}

/* Dark industrial background */
.stApp {
    background-color: #0e0e0e;
    color: #e8e8e8;
}

/* Hide default header */
header[data-testid="stHeader"] { display: none; }

/* Custom title block */
.brd-title {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    color: #666;
    margin-bottom: 4px;
}
.brd-heading {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 28px;
    font-weight: 600;
    color: #f0f0f0;
    margin-bottom: 2px;
    letter-spacing: -0.02em;
}
.brd-sub {
    font-size: 13px;
    color: #555;
    margin-bottom: 32px;
    font-family: 'IBM Plex Sans', sans-serif;
}

/* Divider */
.brd-divider {
    border: none;
    border-top: 1px solid #1e1e1e;
    margin: 24px 0;
}

/* Status pills */
.pill {
    display: inline-block;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    padding: 3px 10px;
    border-radius: 2px;
    font-weight: 600;
    letter-spacing: 0.05em;
}
.pill-ok   { background: #0d2b1a; color: #2ecc71; border: 1px solid #1a4a2a; }
.pill-err  { background: #2b0d0d; color: #e74c3c; border: 1px solid #4a1a1a; }
.pill-warn { background: #2b220d; color: #f39c12; border: 1px solid #4a380a; }
.pill-info { background: #0d1a2b; color: #3498db; border: 1px solid #0a2a4a; }

/* Metadata grid */
.meta-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin: 16px 0;
}
.meta-cell {
    background: #141414;
    border: 1px solid #1e1e1e;
    border-radius: 4px;
    padding: 12px 16px;
}
.meta-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    color: #444;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    margin-bottom: 4px;
}
.meta-value {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 14px;
    color: #e0e0e0;
    font-weight: 600;
}

/* Section counts */
.section-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid #1a1a1a;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
}
.section-name { color: #888; }
.section-count { color: #2ecc71; font-weight: 600; }

/* Log box */
.log-box {
    background: #0a0a0a;
    border: 1px solid #1a1a1a;
    border-radius: 4px;
    padding: 14px 16px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: #555;
    white-space: pre;
    overflow-x: auto;
}

/* Upload zone override */
[data-testid="stFileUploader"] {
    background: #111 !important;
    border: 1px dashed #2a2a2a !important;
    border-radius: 4px !important;
}

/* Input fields */
[data-testid="stTextInput"] input {
    background: #111 !important;
    border: 1px solid #222 !important;
    color: #e0e0e0 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 13px !important;
    border-radius: 3px !important;
}

/* Primary button */
.stButton > button {
    background: #1a1a1a !important;
    color: #e0e0e0 !important;
    border: 1px solid #333 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    border-radius: 3px !important;
    padding: 10px 24px !important;
    transition: all 0.15s !important;
}
.stButton > button:hover {
    background: #252525 !important;
    border-color: #444 !important;
}

/* Download button */
[data-testid="stDownloadButton"] > button {
    background: #0d2b1a !important;
    color: #2ecc71 !important;
    border: 1px solid #1a4a2a !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    border-radius: 3px !important;
    padding: 10px 24px !important;
    width: 100% !important;
}
[data-testid="stDownloadButton"] > button:hover {
    background: #0f3d22 !important;
}

/* Expander */
[data-testid="stExpander"] {
    background: #0f0f0f !important;
    border: 1px solid #1a1a1a !important;
    border-radius: 4px !important;
}
</style>
""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="brd-title">Polycab · Internal Tool</div>', unsafe_allow_html=True)
st.markdown('<div class="brd-heading">BRD Agent</div>', unsafe_allow_html=True)
st.markdown('<div class="brd-sub">Upload a meeting transcript → receive a filled Business Requirements Document</div>', unsafe_allow_html=True)
st.markdown('<hr class="brd-divider">', unsafe_allow_html=True)


# ── Sidebar: Config ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Configuration")
    
    backend_url = st.text_input(
        "Backend URL",
        value=os.getenv("BRD_BACKEND_URL", "http://localhost:8000"),
        help="FastAPI server URL"
    )
    api_key = st.text_input(
        "API Secret Key",
        value=os.getenv("API_SECRET_KEY", ""),
        type="password",
        help="X-API-Key header value — matches API_SECRET_KEY in your .env"
    )
    timeout = st.slider("Request timeout (s)", min_value=30, max_value=120, value=90, step=10)

    st.markdown("---")
    st.markdown("**Health check**")
    if st.button("Ping /health"):
        try:
            r = requests.get(f"{backend_url}/health", timeout=5)
            if r.status_code == 200:
                data = r.json()
                st.markdown(f'<span class="pill pill-ok">● ONLINE</span>', unsafe_allow_html=True)
                st.caption(f"env: {data.get('env', '?')}")
            else:
                st.markdown(f'<span class="pill pill-err">● {r.status_code}</span>', unsafe_allow_html=True)
        except Exception as e:
            st.markdown('<span class="pill pill-err">● OFFLINE</span>', unsafe_allow_html=True)
            st.caption(str(e))

    st.markdown("---")
    st.caption("**Endpoint:** `POST /api/v1/generate-brd`")
    st.caption("**Auth:** `X-API-Key` header")
    st.caption("**Accepts:** `.docx`, `.vtt`")
    st.caption("**Returns:** base64 `.docx`")


# ── Main: Upload ──────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "Drop transcript file here",
    type=["docx", "vtt"],
    help="Supported: .docx (Word transcript), .vtt (WebVTT caption file)",
    label_visibility="visible",
)

if uploaded_file:
    file_size_kb = len(uploaded_file.getvalue()) / 1024
    ext = Path(uploaded_file.name).suffix.lower()
    st.markdown(f"""
    <div style="display:flex; gap:10px; margin:12px 0; align-items:center;">
        <span class="pill pill-info">{ext.upper()}</span>
        <span style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:#888;">
            {uploaded_file.name} &nbsp;·&nbsp; {file_size_kb:.1f} KB
        </span>
    </div>
    """, unsafe_allow_html=True)

st.markdown('<hr class="brd-divider">', unsafe_allow_html=True)

# ── Main: Generate ────────────────────────────────────────────────────────────
col1, col2 = st.columns([3, 1])
with col1:
    generate_btn = st.button(
        "→ Generate BRD",
        disabled=(uploaded_file is None or not api_key),
        use_container_width=True,
    )
with col2:
    if not api_key:
        st.markdown('<span class="pill pill-warn">No API key</span>', unsafe_allow_html=True)
    elif uploaded_file is None:
        st.markdown('<span class="pill pill-warn">No file</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="pill pill-ok">Ready</span>', unsafe_allow_html=True)


# ── Main: Process ─────────────────────────────────────────────────────────────
if generate_btn and uploaded_file and api_key:

    endpoint = f"{backend_url.rstrip('/')}/api/v1/generate-brd"
    log_lines = []
    log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] POST {endpoint}")
    log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] File: {uploaded_file.name} ({file_size_kb:.1f} KB)")

    progress = st.progress(0, text="Sending to backend...")
    start_time = time.time()

    try:
        progress.progress(15, text="Uploading file...")
        log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] Uploading...")

        file_bytes = uploaded_file.getvalue()
        response = requests.post(
            endpoint,
            headers={"X-API-Key": api_key},
            files={"file": (uploaded_file.name, file_bytes, "application/octet-stream")},
            timeout=timeout,
        )

        elapsed = time.time() - start_time
        log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] Response: HTTP {response.status_code} ({elapsed:.1f}s)")

        progress.progress(80, text="Processing response...")

        # ── Error handling ────────────────────────────────────────────────────
        if response.status_code != 200:
            progress.progress(100, text="Failed.")
            st.markdown(f'<span class="pill pill-err">● HTTP {response.status_code}</span>', unsafe_allow_html=True)

            error_map = {
                400: "Bad request — invalid file type, empty file, or extraction failed.",
                401: "Unauthorised — check your API Secret Key in the sidebar.",
                413: "File too large — exceeds MAX_FILE_SIZE_MB set in backend .env.",
                422: "AI returned unparseable JSON — try again or check Azure model.",
                502: "Azure AI Foundry unreachable — check endpoint/key in backend .env.",
                500: "Internal server error — check backend logs.",
            }
            friendly = error_map.get(response.status_code, "Unexpected error.")
            st.error(friendly)

            with st.expander("Raw error response"):
                try:
                    st.json(response.json())
                except Exception:
                    st.code(response.text)

            log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {friendly}")
            st.markdown(f'<div class="log-box">{"<br>".join(log_lines)}</div>', unsafe_allow_html=True)
            st.stop()

        # ── Success ───────────────────────────────────────────────────────────
        data = response.json()
        progress.progress(95, text="Decoding document...")

        if not data.get("success"):
            st.error("Backend returned success=false. Check logs.")
            st.json(data)
            st.stop()

        # Decode base64 → bytes
        docx_bytes = base64.b64decode(data["docx_base64"])
        filename = data.get("filename", "brd_output.docx")
        project_name = data.get("project_name", "—")
        job_id = data.get("job_id", "—")
        sections = data.get("sections_extracted", {})

        progress.progress(100, text="Done.")
        log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] Success — {len(docx_bytes):,} bytes decoded")
        log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] Job ID: {job_id}")

        st.markdown('<hr class="brd-divider">', unsafe_allow_html=True)
        st.markdown('<span class="pill pill-ok">● BRD Generated</span>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        # Metadata grid
        st.markdown(f"""
        <div class="meta-grid">
            <div class="meta-cell">
                <div class="meta-label">Project</div>
                <div class="meta-value">{project_name}</div>
            </div>
            <div class="meta-cell">
                <div class="meta-label">Output file</div>
                <div class="meta-value">{filename}</div>
            </div>
            <div class="meta-cell">
                <div class="meta-label">Elapsed</div>
                <div class="meta-value">{elapsed:.1f}s</div>
            </div>
            <div class="meta-cell">
                <div class="meta-label">Document size</div>
                <div class="meta-value">{len(docx_bytes)/1024:.1f} KB</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Sections extracted
        if sections:
            st.markdown("**Sections extracted**")
            section_labels = {
                "business_objectives": "Business Objectives",
                "in_scope": "In Scope",
                "out_of_scope": "Out of Scope",
                "functional_requirements": "Functional Requirements",
                "non_functional_requirements": "Non-Functional Requirements",
                "assumptions": "Assumptions",
                "constraints": "Constraints",
                "risks": "Risks",
            }
            rows_html = ""
            for key, label in section_labels.items():
                count = sections.get(key, 0)
                color = "#2ecc71" if count > 0 else "#555"
                rows_html += f"""
                <div class="section-row">
                    <span class="section-name">{label}</span>
                    <span class="section-count" style="color:{color};">{count}</span>
                </div>"""
            st.markdown(f'<div style="margin:12px 0;">{rows_html}</div>', unsafe_allow_html=True)

        st.markdown('<hr class="brd-divider">', unsafe_allow_html=True)

        # Download button
        st.download_button(
            label="↓ Download BRD",
            data=docx_bytes,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

        # Full JSON response (debug)
        with st.expander("Full API response (debug)"):
            debug_data = {k: v for k, v in data.items() if k != "docx_base64"}
            st.json(debug_data)

        # Request log
        with st.expander("Request log"):
            st.markdown(f'<div class="log-box">{"<br>".join(log_lines)}</div>', unsafe_allow_html=True)

    except requests.exceptions.ConnectionError:
        progress.progress(100, text="Failed.")
        st.markdown('<span class="pill pill-err">● Connection refused</span>', unsafe_allow_html=True)
        st.error(f"Cannot reach backend at `{backend_url}`. Is `uvicorn` running?")
        log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] ConnectionError — backend not running")
        with st.expander("Request log"):
            st.markdown(f'<div class="log-box">{"<br>".join(log_lines)}</div>', unsafe_allow_html=True)

    except requests.exceptions.Timeout:
        progress.progress(100, text="Timed out.")
        st.markdown('<span class="pill pill-warn">● Timeout</span>', unsafe_allow_html=True)
        st.error(f"Request exceeded {timeout}s. Increase timeout in sidebar or check Azure connectivity.")

    except Exception as e:
        progress.progress(100, text="Unexpected error.")
        st.markdown('<span class="pill pill-err">● Error</span>', unsafe_allow_html=True)
        st.exception(e)
