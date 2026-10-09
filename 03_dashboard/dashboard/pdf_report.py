"""PDF-отчёт для Personal-режима дашборда.
Собирает Overview/Personal в чистый PDF (не скриншот).
Зависимости: reportlab, matplotlib.
"""
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import date

import matplotlib
matplotlib.use('Agg')  # headless, для сервера без GUI
import matplotlib.pyplot as plt

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
    """Компас через matplotlib — без kaleido и Chrome."""
    angle_map = {'Discovery': 90, 'Variability': 0, 'Retention': 270, 'Burnout': 180}

    fig = plt.figure(figsize=(6, 6), dpi=150)
    fig.patch.set_facecolor(bg_color)
    ax = fig.add_subplot(111, projection='polar')
    ax.set_facecolor(bg_color)

    # Убираем стандартные сетки и рамки
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['polar'].set_visible(False)

    # Радиальные деления — тонкие круги
    for r in [0.70, 0.85, 1.00]:
        circle = np.linspace(0, 2 * np.pi, 200)
        ax.plot(circle, [r] * 200, color=text_color, alpha=0.08,
                linewidth=0.7, zorder=1)

    # Фоновые «секторы» — очень слабые
    for center_deg in [45, 135, 225, 315]:
        center = np.deg2rad(center_deg)
        ax.bar(center, 1.08, width=np.deg2rad(90), bottom=0,
               color='#E0E0FF', alpha=0.04, edgecolor='none', zorder=1)

    # Основные бары — с зазором и тенью
    half_width = np.deg2rad(36)   # 72° ширины, 18° зазор между секторами

    for axis_name in axes:
        angle = np.deg2rad(angle_map[axis_name])
        idx = axes.index(axis_name)
        lvl = user_levels[idx].lower()
        r = level_radius.get(lvl, 0.6)
        color = level_colors.get(lvl, '#666666')

        # Тень под баром (чуть глубже)
        ax.bar(angle, 1.06, width=2 * half_width, bottom=0,
               color='#000000', alpha=0.35, edgecolor='none', zorder=2)

        # Сам бар
        ax.bar(angle, r, width=2 * half_width, bottom=0,
               color=color, edgecolor='none', zorder=3)

    # Внешний круг — цвет профиля
    circle = np.linspace(0, 2 * np.pi, 300)
    ax.plot(circle, [1.28] * 300, color=profile_color_hex,
            linewidth=1.8, zorder=4)

    # Тонкая внутренняя окружность
    ax.plot(circle, [0.05] * 300, color=text_color,
            alpha=0.15, linewidth=0.7, zorder=4)

    # Настройки осей
    ax.set_ylim(0, 1.42)
    ax.set_xticks([np.deg2rad(angle_map[a]) for a in axes])
    ax.set_xticklabels(axes, color=text_color, fontsize=11)
    ax.tick_params(axis='x', pad=14)

    buf = BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format='png', facecolor=bg_color,
                bbox_inches='tight', dpi=150)
    plt.close(fig)
    return buf.getvalue()


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