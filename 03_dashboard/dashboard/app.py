import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from config import load_config
from data.loaders import load_basic_info
from data.reference import build_reference_table
from ui import sound, time, behavior, collection, overview
from ui.pdf import get_overview_pdf

cfg = load_config()
DASH_CONFIG = cfg['dashboard']

st.set_page_config(
    page_title=DASH_CONFIG['app_title'],
    layout='wide'
)

basic_info = load_basic_info()

# ======================================================
# САЙДБАР
# ======================================================
with st.sidebar:
    st.header('Settings')

    mode = st.radio(
        'Mode',
        ['Personal', 'Professional'],
        horizontal=True,
        key='mode',
        help='Personal — for self-reflection; Professional — for analysts and business'
    )

    period = st.radio(
        'Period',
        ['Lifetime', 'Last 18 months', 'Last 90 days'],
        help='...',
        key='period_selector'
    )

    stage_map = {
        'Lifetime': 'global',
        'Last 18 months': 'recent_6q',
        'Last 90 days': 'last_90d'
    }
    selected_stage = stage_map[period]

    st.markdown("### About")
    st.metric("Tracks (valid)", f"{basic_info[selected_stage]['tracks']:,}")
    st.metric("Events (valid)", f"{basic_info[selected_stage]['events']:,}")
    st.metric("Period", f"{basic_info['min_date']} → {basic_info['max_date']}")

    with st.expander('What do these numbers mean?'):
        st.markdown(
            "**Tracks (valid)** — unique tracks with at least one valid play "
            "in the selected window.\n\n"
            "**Events (valid)** — play events meeting all valid criteria "
            "(≥30 sec, not skipped, played to at least 50%, not interrupted)."
        )

    if mode == 'Professional':
        ref_df = build_reference_table()
        csv = ref_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label='Download all indices CSV',
            data=csv,
            file_name='listener_portrait_indices.csv',
            mime='text/csv'
        )
    else:
        if selected_stage == 'global':
            pdf_bytes = get_overview_pdf(selected_stage, basic_info, cfg)
            if pdf_bytes:
                st.download_button(
                    label='Download PDF report (Lifetime)',
                    data=pdf_bytes,
                    file_name='listener_portrait_lifetime.pdf',
                    mime='application/pdf'
                )
            else:
                st.button(
                    'Download PDF report',
                    disabled=True,
                    help='Could not build the report.'
                )
        else:
            st.button(
                'Download PDF report',
                disabled=True,
                help='PDF report is available for Lifetime only. Switch the period.'
            )


# ======================================================
# ТЕМА
# ======================================================
theme = DASH_CONFIG['themes'][mode.lower()]
typography = DASH_CONFIG['typography'][mode.lower()]

if mode == 'Personal':
    interactive_accent = theme['accent_blue']
else:
    interactive_accent = theme['accent_pink']

period_accent_map = {
    'global':    theme.get('accent_blue',   theme['accent_blue']),
    'recent_6q': theme.get('accent_cyan',   theme['accent_blue']),
    'last_90d':  theme.get('accent_purple', theme['accent_blue']),
}
period_accent = period_accent_map.get(selected_stage, theme['accent_blue'])


# ======================================================
# CSS
# ======================================================
st.markdown(f"""
<style>
:root {{
    --accent-color: {interactive_accent};
}}

.stApp {{
    background-color: {theme['bg']};
    color: {theme['text']};
}}
section[data-testid="stSidebar"] {{
    background-color: {theme['sidebar_bg']};
    color: {theme['text']};
}}
header[data-testid="stHeader"],
[data-testid="stToolbar"] {{
    background-color: {theme['bg']} !important;
}}

h1, h2, h3, h4, h5, h6, p, span, div, label {{
    color: {theme['text']};
}}

.stTabs [data-selected] {{
    color: {interactive_accent} !important;
}}
.stTabs [data-selected] .react-aria-SelectionIndicator {{
    background-color: {interactive_accent} !important;
}}

/* === РАДИО-КНОПКИ === */
.stRadio [data-baseweb="radio"] > div:first-child {{
    width: 14px !important;
    height: 14px !important;
    border-radius: 50% !important;
    border: 2px solid {interactive_accent} !important;
    background-color: {theme['bg']} !important;
}}
.stRadio [data-baseweb="radio"] > div:first-child > div {{
    display: none !important;
}}

.stDownloadButton button {{
    background-color: {theme['sidebar_bg']} !important;
    color: {theme['text']} !important;
    border: 2px solid {interactive_accent} !important;
    border-radius: 8px;
}}
.stDownloadButton button:hover {{
    background-color: {interactive_accent} !important;
    color: {theme['bg']} !important;
}}

[data-testid="stMetric"] {{ padding: 0.25rem 0; }}
[data-testid="stMetricLabel"] {{ font-size: 0.8rem !important; }}
[data-testid="stMetricValue"] {{ font-size: 0.9rem !important; }}

[data-testid="stCaptionContainer"] p {{
    line-height: 1.7;
    margin: 0;
    margin-bottom: 4px;
}}
[data-testid="stCaptionContainer"] code {{
    background-color: transparent !important;
    color: inherit !important;
    padding: 0 !important;
    font-family: inherit !important;
    font-size: inherit !important;
}}

[data-testid="stTable"] table {{
    border-collapse: collapse;
    width: 100%;
    border: 1px solid #CCCCCC;
}}
[data-testid="stTable"] th,
[data-testid="stTable"] td {{
    border: 1px solid #CCCCCC;
    padding: 8px;
    text-align: left;
}}
[data-testid="stTable"] th {{
    background-color: #F0F0F0;
}}

div[data-testid="stPopover"] button {{
    background-color: transparent !important;
    border: none !important;
    padding: 0 !important;
    min-height: 0 !important;
    opacity: 0.6;
}}
div[data-testid="stPopover"] button:hover {{
    opacity: 1;
}}
div[data-testid="stPopover"] button svg {{
    fill: {theme['text']} !important;
    stroke: {theme['text']} !important;
    color: {theme['text']} !important;
}}
div[data-testid="stPopover"] button:hover svg {{
    fill: {interactive_accent} !important;
    stroke: {interactive_accent} !important;
    color: {interactive_accent} !important;
}}
div[data-testid="stPopoverBody"] {{
    background-color: {theme['sidebar_bg']} !important;
    color: {theme['text']} !important;
    border: 1px solid {interactive_accent} !important;
    border-radius: 8px;
}}
div[data-testid="stPopoverBody"] * {{
    color: {theme['text']} !important;
}}

[class*="st-key-pro-card"] {{
    border: 2px solid {period_accent} !important;
    border-radius: 10px !important;
    padding: 0.4rem !important;
    min-height: 310px !important;
}}

[data-testid="stVerticalBlockBorderWrapper"] > div {{
    padding-left: 0 !important;
    padding-right: 0 !important;
}}

[data-testid="stHorizontalBlock"] {{
    gap: 0.5rem !important;
}}

[data-testid="stExpander"] {{
    background-color: {theme['bg']} !important;
    border: 1px solid rgba(128,128,128,0.25) !important;
    border-radius: 8px !important;
}}
[data-testid="stExpander"] details {{
    background-color: {theme['bg']} !important;
}}
[data-testid="stExpander"] summary {{
    background-color: {theme['bg']} !important;
    color: {theme['text']} !important;
}}
[data-testid="stExpander"] summary:hover {{
    background-color: {theme['sidebar_bg']} !important;
    color: {theme['text']} !important;
}}
[data-testid="stExpander"] summary svg {{
    fill: {theme['text']} !important;
    color: {theme['text']} !important;
}}
[data-testid="stExpander"] p,
[data-testid="stExpander"] span,
[data-testid="stExpander"] div {{
    color: {theme['text']};
}}

div[data-testid="stTooltipContent"],
[role="tooltip"] {{
    background-color: {theme['sidebar_bg']} !important;
    color: {theme['text']} !important;
    border: 1px solid {interactive_accent} !important;
    border-radius: 6px !important;
}}
[role="tooltip"] * {{
    color: {theme['text']} !important;
}}

.stTooltipHoverTarget svg.icon {{
    stroke: {theme['text']} !important;
    stroke-width: 2.0 !important;
    opacity: 0.35 !important;
}}
.stTooltipHoverTarget:hover svg.icon {{
    stroke: {interactive_accent} !important;
    opacity: 0.9 !important;
}}

.ui-title {{ font-size: {typography['title']}; font-weight: 700; line-height: 1.2; margin-bottom: 6px; }}
.ui-subtitle {{ font-size: {typography['subtitle']}; line-height: 1.5; opacity: 0.75; margin-bottom: 18px; max-width: 900px; }}
.ui-section {{ font-size: {typography['section']}; font-weight: 600; line-height: 1.25; margin-top: 8px; margin-bottom: 10px; }}
.ui-label {{ font-size: {typography['label']}; font-weight: 600; line-height: 1.3; margin-bottom: 6px; }}
.ui-caption {{ font-size: {typography['caption']}; line-height: 1.5; opacity: 0.7; margin-top: 6px; margin-bottom: 6px; }}
</style>
""", unsafe_allow_html=True)


# ======================================================
# ЗАГОЛОВОК
# ======================================================
st.markdown('<div id="tabs-top"></div>', unsafe_allow_html=True)
st.title('🎧 ' + DASH_CONFIG['app_title'])


# ======================================================
# ВКЛАДКИ
# ======================================================
tabs = st.tabs(['Sound', 'Time', 'Behavior', 'Collection', 'Overview'])

with tabs[0]:
    sound.render(mode, selected_stage, cfg)

with tabs[1]:
    time.render(mode, selected_stage, cfg)

with tabs[2]:
    behavior.render(mode, selected_stage, cfg)

with tabs[3]:
    collection.render(mode, selected_stage, cfg)

with tabs[4]:
    overview.render(mode, selected_stage, cfg)