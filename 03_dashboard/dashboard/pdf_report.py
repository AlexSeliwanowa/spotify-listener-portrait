"""PDF-отчёт для Personal-режима дашборда.
Собирает Overview/Personal в чистый PDF (не скриншот).
Зависимости: reportlab, kaleido.
"""
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import date

import plotly.graph_objects as go
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors as rl_colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT


def _fmt(value, unit):
    if pd.isna(value):
        return '—'
    if unit == 'percent':  return f'{value * 100:.0f}%'
    if unit == 'index':    return f'{value:.2f}'
    if unit == 'hours':    return f'{value:,.0f}h'
    if unit == 'days':     return f'{value:,.0f}d'
    if unit == 'count':    return f'{value:,.1f}'
    return f'{value:.2f}'


def _level(value, thresholds):
    if pd.isna(value) or not thresholds or len(thresholds) != 2:
        return None
    low, high = thresholds
    if value < low:   return 'low'
    if value <= high: return 'medium'
    return 'high'


def _compass_png(portrait_idx, axes, user_levels, level_colors, level_radius,
                 profile_color_hex, bg_color='#0F0C1B', text_color='#E0E0FF'):
    angle_map = {'Discovery': 90, 'Variability': 0, 'Retention': 270, 'Burnout': 180}
    theta = [angle_map[a] for a in axes]
    r = [level_radius[l.lower()] for l in user_levels]
    cols = [level_colors[l.lower()] for l in user_levels]

    fig = go.Figure()
    fig.add_trace(go.Barpolar(
        r=[1.10] * 4, theta=[45, 135, 225, 315], width=[90] * 4,
        marker_color='#E0E0FF', marker_line_width=0,
        hoverinfo='skip', showlegend=False,
    ))
    fig.add_trace(go.Barpolar(
        r=r, theta=theta, width=[80] * 4,
        marker_color=cols, hoverinfo='skip', showlegend=False,
    ))
    circle_theta = np.linspace(0, 360, 200).tolist()
    fig.add_trace(go.Scatterpolar(
        r=[1.28] * 200, theta=circle_theta, mode='lines',
        line=dict(color=profile_color_hex, width=2),
        hoverinfo='skip', showlegend=False,
    ))
    fig.update_layout(
        height=400, margin=dict(t=20, b=20, l=20, r=20),
        paper_bgcolor=bg_color,
        polar=dict(
            bgcolor=bg_color,
            radialaxis=dict(visible=False, range=[0, 1.4]),
            angularaxis=dict(
                tickvals=theta, ticktext=axes,
                showgrid=False, showline=False,
                tickfont=dict(color=text_color, size=13),
            ),
        ),
        showlegend=False,
    )
    return fig.to_image(format='png', width=700, height=500, scale=2)


def build_overview_personal_pdf(
    *,
    stage_label, period_min, period_max,
    profile, profile_color,
    portrait_idx, axes, user_levels,
    level_colors, level_radius,
    kpi_df, indices_display, selected_stage,
    obsessions_df, signals, app_title,
    bg_color='#0F0C1B',
    text_color='#E0E0FF',
    sidebar_bg='#1D1833',
):
    """Возвращает bytes PDF."""
    buf = BytesIO()

    def _paint_bg(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(rl_colors.HexColor(bg_color))
        canvas.rect(0, 0, A4[0], A4[1], stroke=0, fill=1)
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title='Listener Portrait — Personal Report',
    )

    s_title   = ParagraphStyle('t',  fontName='Helvetica-Bold',     fontSize=22, leading=26, textColor=rl_colors.HexColor(text_color))
    s_sub     = ParagraphStyle('s',  fontName='Helvetica',          fontSize=11, leading=15, textColor=rl_colors.HexColor(text_color))
    s_section = ParagraphStyle('sc', fontName='Helvetica-Bold',     fontSize=14, leading=18, textColor=rl_colors.HexColor(text_color), spaceBefore=14, spaceAfter=6)
    s_arch    = ParagraphStyle('a',  fontName='Helvetica-Bold',     fontSize=20, leading=24, textColor=rl_colors.HexColor(profile_color or text_color))
    s_phrase  = ParagraphStyle('p',  fontName='Helvetica-Oblique',  fontSize=13, leading=17, textColor=rl_colors.HexColor(profile_color or text_color), spaceAfter=10)
    s_body    = ParagraphStyle('b',  fontName='Helvetica',          fontSize=11, leading=15, textColor=rl_colors.HexColor(text_color))
    s_caption = ParagraphStyle('c',  fontName='Helvetica',          fontSize=9,  leading=12, textColor=rl_colors.HexColor(text_color))
    s_footer  = ParagraphStyle('f',  fontName='Helvetica',          fontSize=8,  leading=10, textColor=rl_colors.HexColor(text_color), alignment=TA_LEFT)

    els = []

    # Шапка
    els.append(Paragraph(app_title, s_title))
    els.append(Spacer(1, 4))
    els.append(Paragraph(f'{stage_label} · {period_min} → {period_max}', s_sub))
    els.append(Spacer(1, 18))

    # Архетип
    els.append(Paragraph('Your archetype', s_section))
    if profile:
        els.append(Paragraph(profile.get('name_en', '—'), s_arch))
        phrase = profile.get('personal_phrase_en', '')
        if phrase:
            els.append(Paragraph(phrase, s_phrase))
    else:
        els.append(Paragraph('Profile requires at least 12 months of data.', s_body))

    # Компас
    if portrait_idx is not None and profile:
        try:
            png = _compass_png(portrait_idx, axes, user_levels,
                               level_colors, level_radius, profile_color,
                               bg_color=bg_color, text_color=text_color)
            els.append(Spacer(1, 8))
            els.append(Image(BytesIO(png), width=12 * cm, height=8.5 * cm))
        except Exception as e:
            els.append(Paragraph(f'[compass unavailable: {e}]', s_caption))

    # 4 сигнала
    els.append(Paragraph('Your signals at a glance', s_section))
    rows = [['Index', 'Value', 'What it means']]
    for idx_name in signals:
        sub = kpi_df[(kpi_df['index_name'] == idx_name) & (kpi_df['stage'] == selected_stage)]
        if sub.empty:
            continue
        value = sub.iloc[0]['value']
        unit = sub.iloc[0]['unit']
        info = indices_display.get(idx_name, {})
        lvl = _level(value, info.get('thresholds'))
        msg = info.get('personal_messages', {}).get(lvl or 'default', '') if lvl else ''
        if msg and '{value' in msg:
            try:
                msg = msg.format(value=value)
            except Exception:
                pass
        rows.append([idx_name, _fmt(value, unit), msg])

    table = Table(rows, colWidths=[4.5 * cm, 2 * cm, 10.5 * cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), rl_colors.HexColor(sidebar_bg)),
        ('BACKGROUND', (0, 1), (-1, -1), rl_colors.HexColor(bg_color)),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('TEXTCOLOR', (0, 0), (-1, -1), rl_colors.HexColor(text_color)),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.4, rl_colors.HexColor(sidebar_bg)),
    ]))
    els.append(table)

    # Топ-обсессия
    if obsessions_df is not None and not obsessions_df.empty:
        top = obsessions_df.nlargest(1, 'repeats').iloc[0]
        els.append(Paragraph('Your most intense obsession', s_section))
        els.append(Paragraph(f"<b>{top['track_name']}</b> — {top['artist_name']}", s_body))
        els.append(Paragraph(
            f"{int(top['repeats'])} repeats in a row · {top['hours']:.1f} hours",
            s_caption
        ))

    # Футер
    els.append(Spacer(1, 24))
    els.append(Paragraph(f'Generated {date.today().isoformat()} · Spotify Listener Portrait', s_footer))

    doc.build(els, onFirstPage=_paint_bg, onLaterPages=_paint_bg)
    return buf.getvalue()