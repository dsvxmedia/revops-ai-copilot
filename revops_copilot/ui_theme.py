"""Shared visual theme for the Streamlit UI.

A restrained, editorial palette (warm tinted neutrals + one deep ink-teal accent)
in place of Streamlit's default look. No emoji anywhere -- status is communicated
with small text-labelled dots and muted, tinted badges instead. Motion is CSS-only
(opacity/transform, ease-out-quint, no bounce) and respects prefers-reduced-motion.
"""
from __future__ import annotations

BG = "#F6F3ED"
SURFACE = "#FDFBF8"
BORDER = "#E4DFD4"
TEXT = "#211F1A"
TEXT_MUTED = "#6B675D"
ACCENT = "#1C3D4A"
ACCENT_HOVER = "#14303B"
ACCENT_TINT = "#E7EEEE"

STATUS = {
    "ae": {"bg": "#E6EFE7", "fg": "#2F5233"},
    "sdr": {"bg": "#E5EEF0", "fg": "#1F4E5C"},
    "nurture": {"bg": "#F3ECDF", "fg": "#7A5A22"},
    "review": {"bg": "#F5E6E1", "fg": "#7A2E1F"},
    "neutral": {"bg": "#EDEAE3", "fg": "#4A473E"},
}

HEADING_FONT = (
    '"Iowan Old Style", "Palatino Linotype", Georgia, "Times New Roman", serif'
)
BODY_FONT = (
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
)


def inject() -> None:
    """Call once at the top of every page."""
    import streamlit as st

    st.markdown(
        f"""
        <style>
        @media (prefers-reduced-motion: no-preference) {{
          [data-testid="stStatusWidget"],
          [data-testid="stExpander"],
          div[data-testid="stVerticalBlockBorderWrapper"] {{
            animation: rc-rise 0.42s cubic-bezier(0.22, 1, 0.36, 1) both;
          }}
        }}
        @keyframes rc-rise {{
          from {{ opacity: 0; transform: translateY(7px); }}
          to   {{ opacity: 1; transform: translateY(0); }}
        }}

        html, body, [class*="css"] {{
          font-family: {BODY_FONT};
        }}
        .stApp {{
          background: {BG};
          color: {TEXT};
        }}
        [data-testid="stSidebar"] {{
          background: {SURFACE};
          border-right: 1px solid {BORDER};
        }}
        h1, h2, h3 {{
          font-family: {HEADING_FONT} !important;
          font-weight: 600 !important;
          letter-spacing: -0.01em;
          color: {TEXT} !important;
        }}
        h1 {{ font-size: 2.05rem !important; }}
        h2 {{ font-size: 1.35rem !important; }}
        h3 {{ font-size: 1.05rem !important; }}
        p, li, span, label, div {{
          color: {TEXT};
        }}
        [data-testid="stCaptionContainer"], .stCaption, small {{
          color: {TEXT_MUTED} !important;
        }}

        /* Buttons */
        .stButton > button, [data-testid^="stBaseButton"] {{
          background: {ACCENT} !important;
          color: {SURFACE} !important;
          border: 1px solid {ACCENT} !important;
          border-radius: 6px !important;
          font-weight: 600 !important;
          box-shadow: none !important;
          transition: background 0.18s ease-out;
        }}
        .stButton > button:hover, [data-testid^="stBaseButton"]:hover {{
          background: {ACCENT_HOVER} !important;
          border-color: {ACCENT_HOVER} !important;
        }}

        /* Inputs */
        [data-baseweb="select"] > div, .stTextInput input {{
          border-radius: 6px !important;
          border-color: {BORDER} !important;
        }}

        /* Status / expander containers */
        [data-testid="stStatusWidget"], [data-testid="stExpander"] {{
          background: {SURFACE} !important;
          border: 1px solid {BORDER} !important;
          border-radius: 8px !important;
          box-shadow: none !important;
        }}

        /* Metrics */
        [data-testid="stMetricValue"] {{
          font-family: {HEADING_FONT} !important;
          font-weight: 600 !important;
          color: {TEXT} !important;
        }}
        [data-testid="stMetricLabel"] {{
          color: {TEXT_MUTED} !important;
          font-size: 0.8rem !important;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }}

        /* Dataframe */
        [data-testid="stDataFrame"] {{
          border: 1px solid {BORDER} !important;
          border-radius: 8px !important;
        }}

        hr, [data-testid="stDivider"] {{
          border-color: {BORDER} !important;
        }}

        /* Info / warning / error boxes: full tint, no side-stripe accent */
        [data-testid="stAlertContentInfo"], .stAlert {{
          border-radius: 8px !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def status_dot(kind: str) -> str:
    color = STATUS.get(kind, STATUS["neutral"])["fg"]
    return (
        f"<span style='display:inline-block;width:7px;height:7px;border-radius:50%;"
        f"background:{color};margin-right:7px;vertical-align:middle'></span>"
    )


def badge(text: str, kind: str) -> str:
    c = STATUS.get(kind, STATUS["neutral"])
    return (
        f"<span style='background:{c['bg']};color:{c['fg']};padding:4px 12px;"
        f"border-radius:5px;font-weight:600;font-size:0.85rem;letter-spacing:0.01em'>"
        f"{status_dot(kind)}{text}</span>"
    )


def note(text: str, kind: str = "neutral") -> str:
    """A full-tint inline note block (no side-stripe border -- that pattern is banned)."""
    c = STATUS.get(kind, STATUS["neutral"])
    return (
        f"<div style='background:{c['bg']};color:{c['fg']};padding:10px 14px;"
        f"border-radius:6px;font-size:0.92rem;margin:6px 0'>{text}</div>"
    )
