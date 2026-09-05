"""Designed executive PDF export for SybilTrace."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Brand & Palette Colors
NAVY_PRIMARY = colors.HexColor("#1E3A8A")
NAVY_DARK = colors.HexColor("#0F172A")
BLUE_ACCENT = colors.HexColor("#2563EB")
BLUE_LIGHT = colors.HexColor("#EFF6FF")
SLATE_TEXT = colors.HexColor("#1E293B")
MUTED_TEXT = colors.HexColor("#64748B")
BORDER_COLOR = colors.HexColor("#CBD5E1")
BORDER_LIGHT = colors.HexColor("#E2E8F0")
SURFACE_BG = colors.HexColor("#F8FAFC")
SURFACE_ALT = colors.HexColor("#F1F5F9")
CALLOUT_BG = colors.HexColor("#F0F9FF")
CALLOUT_BORDER = colors.HexColor("#0284C7")

# Semantic severity colors
COLOR_HIGH = colors.HexColor("#DC2626")
COLOR_HIGH_BG = colors.HexColor("#FEE2E2")
COLOR_MED = colors.HexColor("#D97706")
COLOR_MED_BG = colors.HexColor("#FEF3C7")
COLOR_LOW = colors.HexColor("#16A34A")
COLOR_LOW_BG = colors.HexColor("#DCFCE7")
COLOR_DISMISSED = colors.HexColor("#64748B")
COLOR_DISMISSED_BG = colors.HexColor("#F1F5F9")


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and print total page counts."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(MUTED_TEXT)

        # Running Header on pages 2+
        if self._pageNumber > 1:
            self.drawString(
                40,
                758,
                "SybilTrace  •  Coordinated Promotional Abuse Analysis",
            )
            self.setStrokeColor(BORDER_LIGHT)
            self.setLineWidth(0.5)
            self.line(40, 752, 572, 752)

        # Running Footer on all pages
        self.setStrokeColor(BORDER_LIGHT)
        self.setLineWidth(0.5)
        self.line(40, 38, 572, 38)

        self.drawString(
            40,
            26,
            "CONFIDENTIAL  •  FRAUD INVESTIGATION & DECISION SUPPORT REPORT",
        )
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(572, 26, page_str)

        self.restoreState()


def _format_iso_date(dt_val: str | datetime | None) -> str:
    if not dt_val:
        return datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M UTC")
    if isinstance(dt_val, str):
        try:
            dt = datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
            return dt.strftime("%b %d, %Y %H:%M UTC")
        except Exception:
            return dt_val
    return dt_val.strftime("%b %d, %Y %H:%M UTC")


def chunk_appendix_rings(
    rings: list[dict[str, Any]],
    max_per_page: int = 28,
) -> list[list[dict[str, Any]]]:
    """Split rings into balanced, explicit page-sized chunks to avoid orphan rows and broken continuation tables."""
    total = len(rings)
    if total == 0:
        return []
    if total <= max_per_page:
        return [rings]

    import math
    num_pages = math.ceil(total / max_per_page)
    base_chunk = total // num_pages
    remainder = total % num_pages

    chunks: list[list[dict[str, Any]]] = []
    idx = 0
    for p in range(num_pages):
        chunk_len = base_chunk + (1 if p < remainder else 0)
        chunks.append(rings[idx : idx + chunk_len])
        idx += chunk_len
    return chunks


def build_pdf_report(
    summary_data: dict[str, Any],
    rings: list[dict[str, Any]],
    exported_at: str | None = None,
) -> bytes:
    """Generate a complete, professionally formatted executive PDF report in memory."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=46,
        bottomMargin=46,
    )

    printable_width = 572 - 40  # 532 pt

    # Base Styles
    styles = getSampleStyleSheet()
    normal_style = styles["Normal"]

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=normal_style,
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=NAVY_DARK,
    )

    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=normal_style,
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13,
        textColor=BLUE_ACCENT,
        textTransform="uppercase",
    )

    meta_label = ParagraphStyle(
        "MetaLabel",
        parent=normal_style,
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=MUTED_TEXT,
    )

    meta_val = ParagraphStyle(
        "MetaVal",
        parent=normal_style,
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=12,
        textColor=SLATE_TEXT,
    )

    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=normal_style,
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=NAVY_PRIMARY,
        spaceBefore=10,
        spaceAfter=5,
    )

    appendix_heading = ParagraphStyle(
        "AppendixHeading",
        parent=normal_style,
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=NAVY_PRIMARY,
        spaceBefore=0,
        spaceAfter=4,
    )

    body_style = ParagraphStyle(
        "BodyStyle",
        parent=normal_style,
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=SLATE_TEXT,
    )

    disclaimer_style = ParagraphStyle(
        "DisclaimerText",
        parent=normal_style,
        fontName="Helvetica-Oblique",
        fontSize=7.5,
        leading=10.5,
        textColor=colors.HexColor("#0369A1"),
    )

    bullet_style = ParagraphStyle(
        "BulletText",
        parent=normal_style,
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=SLATE_TEXT,
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=normal_style,
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=NAVY_DARK,
    )

    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=normal_style,
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=SLATE_TEXT,
    )

    table_cell_mono = ParagraphStyle(
        "TableCellMono",
        parent=normal_style,
        fontName="Courier-Bold",
        fontSize=7,
        leading=9,
        textColor=SLATE_TEXT,
    )

    story: list[Any] = []

    # 1. Header Banner & Metadata
    run_id = summary_data.get("run_id", "live")
    timestamp_str = _format_iso_date(exported_at)

    header_table_data = [
        [
            Paragraph("SYBILTRACE", subtitle_style),
            Paragraph(f"<b>Run ID:</b> {run_id}", meta_val),
        ],
        [
            Paragraph("Coordinated Promotional Abuse Analysis", title_style),
            Paragraph(f"<b>Exported:</b> {timestamp_str}", meta_label),
        ],
    ]

    header_table = Table(header_table_data, colWidths=[370, 162])
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 4))

    # Top accent rule
    story.append(
        HRFlowable(
            width="100%",
            thickness=1.5,
            color=BLUE_ACCENT,
            spaceBefore=0,
            spaceAfter=8,
        )
    )

    # 2. Decision Support Disclaimer Alert Box
    disclaimer_html = (
        "<b>Decision-Support Notice:</b> This report is an analytical decision-support tool "
        "designed to assist fraud analysts in investigation triage. Risk scores reflect "
        "structural and behavioural evidence rankings rather than automated blocking decisions. "
        "Human review is required before taking punitive or account-blocking actions."
    )
    disclaimer_table = Table(
        [[Paragraph(disclaimer_html, disclaimer_style)]],
        colWidths=[printable_width],
    )
    disclaimer_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CALLOUT_BG),
                ("BOX", (0, 0), (-1, -1), 0.75, CALLOUT_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(disclaimer_table)
    story.append(Spacer(1, 8))

    # 3. Executive KPI Cards (3 columns x 2 rows)
    account_count = summary_data.get("account_count", 0)
    transaction_count = summary_data.get("transaction_count", 0)
    flagged_account_count = summary_data.get("flagged_account_count", 0)
    ring_count = summary_data.get("ring_count", len(rings))
    score_dist = summary_data.get("score_distribution", {})
    high_risk_rings = score_dist.get("high", 0)
    status_totals = summary_data.get("review_status_totals", {})
    cases_awaiting_review = status_totals.get("new", 0)

    flagged_rate = (
        (flagged_account_count / account_count * 100) if account_count > 0 else 0.0
    )
    high_risk_share = (
        (high_risk_rings / ring_count * 100) if ring_count > 0 else 0.0
    )

    def _make_kpi_cell(value_str: str, label_str: str, sub_str: str = "") -> list[Paragraph]:
        v_p = Paragraph(
            f"<font size=13><b>{value_str}</b></font>",
            ParagraphStyle("KPIVal", parent=normal_style, fontName="Helvetica-Bold", leading=15, textColor=NAVY_PRIMARY),
        )
        l_p = Paragraph(
            label_str,
            ParagraphStyle("KPILbl", parent=normal_style, fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=MUTED_TEXT, textTransform="uppercase"),
        )
        items = [v_p, l_p]
        if sub_str:
            s_p = Paragraph(
                sub_str,
                ParagraphStyle("KPISub", parent=normal_style, fontName="Helvetica", fontSize=6.5, leading=8.5, textColor=BLUE_ACCENT),
            )
            items.append(s_p)
        return items

    kpi_data = [
        [
            _make_kpi_cell(f"{account_count:,}", "Accounts Analyzed"),
            _make_kpi_cell(f"{transaction_count:,}", "Transactions Analyzed"),
            _make_kpi_cell(f"{flagged_account_count:,}", "Accounts Flagged", f"{flagged_rate:.1f}% flagged rate"),
        ],
        [
            _make_kpi_cell(f"{ring_count:,}", "Rings Detected"),
            _make_kpi_cell(f"{high_risk_rings:,}", "High-Risk Rings", f"{high_risk_share:.1f}% of detected rings"),
            _make_kpi_cell(f"{cases_awaiting_review:,}", "Awaiting Review", "Status: New queue"),
        ],
    ]

    col_w = printable_width / 3.0
    kpi_table = Table(kpi_data, colWidths=[col_w, col_w, col_w])
    kpi_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE_BG),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(kpi_table)
    story.append(Spacer(1, 10))

    # 4. Deterministic Key Findings & Visual Distributions
    story.append(Paragraph("Executive Findings & Risk Distribution", section_heading))

    # Calculate deterministic insights
    entity_counts: dict[str, int] = {}
    critical_counts: dict[str, int] = {}
    resilience_counts = {"high": 0, "moderate": 0, "low": 0}
    resilience_assessed = any(r.get("detection_resilience") is not None for r in rings)

    for r in rings:
        res = r.get("detection_resilience")
        if res in resilience_counts:
            resilience_counts[res] += 1

        for e in r.get("entity_types", []):
            entity_counts[e] = entity_counts.get(e, 0) + 1
        for c in r.get("critical_entity_types", []):
            critical_counts[c] = critical_counts.get(c, 0) + 1

    top_critical_entity = (
        max(critical_counts.items(), key=lambda x: x[1])[0]
        if critical_counts
        else None
    )

    finding_1 = f"<b>High-Risk Concentration:</b> {high_risk_rings} of {ring_count} detected rings ({high_risk_share:.1f}%) exhibit high risk (score ≥ 0.80)."
    finding_2 = f"<b>Investigation Backlog:</b> {cases_awaiting_review} rings currently require analyst triage, including {sum(1 for r in rings if r.get('risk_level') == 'high' and r.get('review_status') == 'new')} high-risk cases."

    if not resilience_assessed:
        finding_3 = "<b>Critical Evidence Types:</b> Detection Resilience was not assessed for this run."
        finding_4 = "<b>Detection Resilience:</b> Detection Resilience was not assessed for this run."
    else:
        if top_critical_entity and critical_counts.get(top_critical_entity, 0) > 0:
            top_crit_name = top_critical_entity.replace("_", " ").title()
            top_crit_cnt = critical_counts[top_critical_entity]
            finding_3 = (
                f"<b>Critical Shared Signals:</b> '{top_crit_name}' is the most common critical shared signal, "
                f"appearing in minimum evidence-loss sets across {top_crit_cnt} rings."
            )
        else:
            finding_3 = "<b>Critical Evidence Types:</b> No single signal type appears in every minimum evidence-loss cut across assessed rings."

        # Majority vs plurality check
        dom_res, dom_cnt = max(resilience_counts.items(), key=lambda x: x[1])
        dom_pct = (dom_cnt / ring_count * 100) if ring_count > 0 else 0
        if dom_cnt > 0:
            if dom_pct > 50:
                finding_4 = f"<b>Detection Resilience:</b> The majority of detected rings ({dom_cnt} rings, {dom_pct:.0f}%) exhibit {dom_res.upper()} resilience."
            else:
                finding_4 = f"<b>Detection Resilience:</b> The largest resilience group is {dom_res.upper()} ({dom_cnt} rings, {dom_pct:.0f}% of detected rings)."
        else:
            finding_4 = "<b>Detection Resilience:</b> Detection Resilience was not assessed for this run."

    findings_paragraphs = [
        Paragraph(f"• {finding_1}", bullet_style),
        Paragraph(f"• {finding_2}", bullet_style),
        Paragraph(f"• {finding_3}", bullet_style),
        Paragraph(f"• {finding_4}", bullet_style),
    ]

    findings_cell = [
        Paragraph("<b>Key Analytical Findings</b>", ParagraphStyle("FindH", parent=normal_style, fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=NAVY_PRIMARY)),
        Spacer(1, 3),
        *findings_paragraphs,
    ]

    # Visual distribution representation
    med_risk_rings = score_dist.get("medium", 0)
    low_risk_rings = score_dist.get("low", 0)

    rev_new = status_totals.get("new", 0)
    rev_reviewing = status_totals.get("reviewing", 0)
    rev_confirmed = status_totals.get("confirmed", 0)
    rev_dismissed = status_totals.get("dismissed", 0)

    resilience_text = (
        f"• High: <b>{resilience_counts['high']}</b> | Moderate: <b>{resilience_counts['moderate']}</b> | Low: <b>{resilience_counts['low']}</b>"
        if resilience_assessed
        else "• Detection Resilience was not assessed for this run."
    )

    dist_html = f"""
    <b>Risk-Level Distribution:</b><br/>
    • High Risk (≥0.80): <b>{high_risk_rings}</b> ({high_risk_share:.1f}%)<br/>
    • Medium Risk (0.50–0.79): <b>{med_risk_rings}</b> ({(med_risk_rings/ring_count*100 if ring_count else 0):.1f}%)<br/>
    • Low Risk (&lt;0.50): <b>{low_risk_rings}</b> ({(low_risk_rings/ring_count*100 if ring_count else 0):.1f}%)<br/>
    <br/>
    <b>Review Status Breakdown:</b><br/>
    • New: <b>{rev_new}</b> | Reviewing: <b>{rev_reviewing}</b><br/>
    • Confirmed: <b>{rev_confirmed}</b> | Dismissed: <b>{rev_dismissed}</b><br/>
    <br/>
    <b>Detection Resilience:</b><br/>
    {resilience_text}
    """

    dist_cell = [
        Paragraph("<b>Distribution Summaries</b>", ParagraphStyle("DistH", parent=normal_style, fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=NAVY_PRIMARY)),
        Spacer(1, 3),
        Paragraph(dist_html, bullet_style),
    ]

    findings_table = Table(
        [[findings_cell, dist_cell]],
        colWidths=[printable_width * 0.55, printable_width * 0.45],
    )
    findings_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE_BG),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(findings_table)
    story.append(Spacer(1, 10))

    # 5. Critical Shared Signals Summary Table
    story.append(Paragraph("Shared Signal Footprint & Critical Evidence Types", section_heading))

    all_known_entities = sorted(
        list(set(list(entity_counts.keys()) + list(critical_counts.keys())))
    )
    signal_table_rows = [
        [
            Paragraph("Entity Type", table_header_style),
            Paragraph("Rings Sharing Signal", table_header_style),
            Paragraph("Critical in Minimum Loss Set", table_header_style),
            Paragraph("Structural Evidence Role", table_header_style),
        ]
    ]

    if not resilience_assessed:
        for ent in all_known_entities:
            ent_total = entity_counts.get(ent, 0)
            ent_label = ent.replace("_", " ").title()
            pct_total = (ent_total / ring_count * 100) if ring_count else 0
            signal_table_rows.append(
                [
                    Paragraph(f"<b>{ent_label}</b>", table_cell_style),
                    Paragraph(f"{ent_total} rings ({pct_total:.1f}%)", table_cell_style),
                    Paragraph("Unassessed", table_cell_style),
                    Paragraph("Detection Resilience was not assessed for this run.", table_cell_style),
                ]
            )
    else:
        for ent in all_known_entities:
            ent_total = entity_counts.get(ent, 0)
            ent_crit = critical_counts.get(ent, 0)
            ent_label = ent.replace("_", " ").title()
            pct_total = (ent_total / ring_count * 100) if ring_count else 0
            pct_crit = (ent_crit / ring_count * 100) if ring_count else 0

            desc = (
                f"Appears in minimum evidence-loss cuts for {ent_crit} rings ({pct_crit:.0f}%). Loss leaves fewer than half the accounts connected."
                if ent_crit > 0
                else f"Present across {ent_total} rings ({pct_total:.0f}%); not part of every minimum evidence-loss cut."
            )

            signal_table_rows.append(
                [
                    Paragraph(f"<b>{ent_label}</b>", table_cell_style),
                    Paragraph(f"{ent_total} rings ({pct_total:.1f}%)", table_cell_style),
                    Paragraph(f"{ent_crit} rings ({pct_crit:.1f}%)", table_cell_style),
                    Paragraph(desc, table_cell_style),
                ]
            )

    if len(signal_table_rows) == 1:
        signal_table_rows.append(
            [
                Paragraph("None detected", table_cell_style),
                Paragraph("-", table_cell_style),
                Paragraph("-", table_cell_style),
                Paragraph("No shared entity linkages present in active dataset.", table_cell_style),
            ]
        )

    signal_table = Table(
        signal_table_rows,
        colWidths=[110, 110, 130, printable_width - 350],
    )
    signal_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SURFACE_ALT),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(signal_table)

    # Page Break for Top-Priority Rings Table & Methodology
    story.append(PageBreak())

    # 6. Priority Cases (Top 15 Ranked Rings)
    story.append(Paragraph("Top-Priority Abuse Rings (Triage Queue)", section_heading))
    story.append(
        Paragraph(
            "Priority ordering is based on hybrid scoring combining member ML anomalies, "
            "temporal concentration, shared-entity strength, link density, and promotional focus.",
            body_style,
        )
    )
    story.append(Spacer(1, 4))

    top_rings = rings[:15]
    rings_table_data = [
        [
            Paragraph("Rank", table_header_style),
            Paragraph("Ring ID", table_header_style),
            Paragraph("Risk", table_header_style),
            Paragraph("Score", table_header_style),
            Paragraph("Status", table_header_style),
            Paragraph("Members", table_header_style),
            Paragraph("Shared Signals", table_header_style),
            Paragraph("Resilience", table_header_style),
            Paragraph("Critical Evidence Types", table_header_style),
        ]
    ]

    for r in top_rings:
        rank_val = r.get("rank", 0)
        ring_id_val = r.get("ring_id", "")
        risk_lvl = r.get("risk_level", "low").upper()
        score_val = f"{float(r.get('ring_score', 0)):.3f}"
        status_val = str(r.get("review_status", "new")).title()
        mem_cnt = str(r.get("member_count", 0))
        shared_cnt = str(r.get("shared_entity_count", 0))

        raw_resil = r.get("detection_resilience")
        if raw_resil:
            resil = raw_resil.title()
            if r.get("min_entity_removals") is not None:
                resil = f"{resil} ({r['min_entity_removals']})"
        elif resilience_assessed:
            resil = "Unassessed"
        else:
            resil = "Unassessed"

        crit_types_list = r.get("critical_entity_types") or []
        if crit_types_list:
            crit_types = ", ".join(crit_types_list).replace("_", " ").title()
        elif resilience_assessed:
            crit_types = "None"
        else:
            crit_types = "Unassessed"

        risk_color = (
            COLOR_HIGH if risk_lvl == "HIGH" else (COLOR_MED if risk_lvl == "MEDIUM" else COLOR_LOW)
        )
        risk_p = Paragraph(f"<font color='{risk_color.hexval()}'><b>{risk_lvl}</b></font>", table_cell_style)

        rings_table_data.append(
            [
                Paragraph(f"#{rank_val}", table_cell_style),
                Paragraph(ring_id_val, table_cell_mono),
                risk_p,
                Paragraph(score_val, table_cell_mono),
                Paragraph(status_val, table_cell_style),
                Paragraph(mem_cnt, table_cell_style),
                Paragraph(shared_cnt, table_cell_style),
                Paragraph(resil, table_cell_style),
                Paragraph(crit_types, table_cell_style),
            ]
        )

    rings_table = Table(
        rings_table_data,
        colWidths=[30, 95, 42, 40, 52, 45, 54, 64, printable_width - 422],
    )
    rings_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SURFACE_ALT),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SURFACE_BG]),
            ]
        )
    )
    story.append(rings_table)
    story.append(Spacer(1, 10))

    # 7. Methodology and Score Interpretation Section
    methodology_items = [
        Paragraph("Methodology & Investigative Principles", section_heading),
        Paragraph(
            "<b>1. Behavioural Feature Scoring:</b> Individual accounts are scored using a supervised classifier "
            "trained on account velocity, transaction cadence, promotion reuse frequency, and credential similarity. "
            "Higher scores indicate account behaviour associated with coordinated promotional abuse.",
            body_style,
        ),
        Spacer(1, 2.5),
        Paragraph(
            "<b>2. Relationship Graph Analysis:</b> Accounts are linked through shared payment instruments, device fingerprints, "
            "and IP addresses into a bipartite graph. Connected components represent coordinated clusters operating across shared infrastructure.",
            body_style,
        ),
        Spacer(1, 2.5),
        Paragraph(
            "<b>3. Hybrid Ring Ranking:</b> Ring risk scores synthesize six weighted dimensions defined in the detection model: "
            "(1) Mean member ML score (35%), (2) Maximum member ML score (15%), (3) Temporal concentration (15%), "
            "(4) Shared-entity strength (15%), (5) Graph density (10%), and (6) Promotion concentration (10%). "
            "This balances individual account anomalies with structural coordination strength.",
            body_style,
        ),
        Spacer(1, 2.5),
        Paragraph(
            "<b>4. Detection Resilience:</b> Evaluates structural stability by calculating the minimum accepted shared-entity "
            "losses required to leave fewer than half of the ring's accounts connected as one case. Critical evidence types "
            "are shared signal categories that appear in every minimum evidence-loss cut. Rings with low resilience depend on "
            "a small minimum evidence-loss set, whereas high-resilience rings maintain broad redundant connectivity.",
            body_style,
        ),
        Spacer(1, 2.5),
        Paragraph(
            "<b>5. Ranking Score vs. Probability:</b> The composite ring score is a normalized ordinal ranking score (0.00 to 1.00) "
            "designed to prioritize review queues. It is not an absolute Bayesian probability of fraud.",
            body_style,
        ),
        Spacer(1, 2.5),
        Paragraph(
            "<b>6. Decision-Support Governance:</b> Coordinated rings frequently encapsulate innocent bystanders (e.g. shared university Wi-Fi "
            "or family payment methods). Automated blocking creates severe false-positive customer friction; therefore, this platform "
            "acts strictly as decision-support for human analysts.",
            body_style,
        ),
    ]
    story.append(KeepTogether(methodology_items))

    # 8. Complete Appendix Table (if total rings > 15)
    # Balanced chunking guarantees every continuation page has full headers, borders, and no orphan rows.
    if len(rings) > 15:
        appendix_chunks = chunk_appendix_rings(rings, max_per_page=28)
        total_appendix_pages = len(appendix_chunks)

        for page_idx, chunk in enumerate(appendix_chunks):
            story.append(PageBreak())

            if page_idx == 0:
                story.append(
                    Paragraph(
                        "Appendix: Complete Ranked Ring Inventory",
                        section_heading,
                    )
                )
                story.append(
                    Paragraph(
                        f"Full catalog of all {len(rings)} detected abuse rings in run <b>{run_id}</b> "
                        f"(Page 1 of {total_appendix_pages} — Rings #{chunk[0]['rank']} to #{chunk[-1]['rank']}).",
                        body_style,
                    )
                )
                story.append(Spacer(1, 5))
            else:
                story.append(
                    Paragraph(
                        f"Appendix: Complete Ranked Ring Inventory (Continued — Page {page_idx + 1} of {total_appendix_pages})",
                        appendix_heading,
                    )
                )
                story.append(
                    Paragraph(
                        f"Run <b>{run_id}</b> — Rings #{chunk[0]['rank']} to #{chunk[-1]['rank']}.",
                        meta_label,
                    )
                )
                story.append(Spacer(1, 4))

            chunk_table_data = [
                [
                    Paragraph("Rank", table_header_style),
                    Paragraph("Ring ID", table_header_style),
                    Paragraph("Risk Level", table_header_style),
                    Paragraph("Score", table_header_style),
                    Paragraph("Status", table_header_style),
                    Paragraph("Members", table_header_style),
                    Paragraph("Shared Entities", table_header_style),
                    Paragraph("Resilience", table_header_style),
                ]
            ]

            for r in chunk:
                rank_val = r.get("rank", 0)
                ring_id_val = r.get("ring_id", "")
                risk_lvl = r.get("risk_level", "low").upper()
                score_val = f"{float(r.get('ring_score', 0)):.3f}"
                status_val = str(r.get("review_status", "new")).title()
                mem_cnt = str(r.get("member_count", 0))
                shared_cnt = str(r.get("shared_entity_count", 0))

                raw_res = r.get("detection_resilience")
                if raw_res:
                    resil_str = raw_res.title()
                    if r.get("min_entity_removals") is not None:
                        resil_str = f"{resil_str} ({r['min_entity_removals']})"
                elif resilience_assessed:
                    resil_str = "Unassessed"
                else:
                    resil_str = "Unassessed"

                chunk_table_data.append(
                    [
                        Paragraph(f"#{rank_val}", table_cell_style),
                        Paragraph(ring_id_val, table_cell_mono),
                        Paragraph(risk_lvl, table_cell_style),
                        Paragraph(score_val, table_cell_mono),
                        Paragraph(status_val, table_cell_style),
                        Paragraph(mem_cnt, table_cell_style),
                        Paragraph(shared_cnt, table_cell_style),
                        Paragraph(resil_str, table_cell_style),
                    ]
                )

            chunk_table = Table(
                chunk_table_data,
                colWidths=[36, 120, 56, 50, 65, 55, 75, printable_width - 457],
            )
            chunk_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), SURFACE_ALT),
                        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SURFACE_BG]),
                    ]
                )
            )
            story.append(chunk_table)

    # Build PDF completely in memory
    doc.build(story, canvasmaker=NumberedCanvas)
    return buffer.getvalue()
