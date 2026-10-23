"""On-demand PDF and CSV reports with institutional NISR & Analiza branding, dynamic maps, and latest findings.
Generated reports are kept in memory for a limited time.
"""

from collections import OrderedDict
import datetime
import io
from pathlib import Path
import time
import uuid

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
import numpy as np

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.data import store
from app.services import geography_service, insight_service, overview_service, priority_service

MAX_REPORTS = 50
TTL_SECONDS = 3600
_reports: "OrderedDict[str, dict]" = OrderedDict()

# Brand colors
PRIMARY_BLUE = colors.HexColor("#005baa")
FOREST_GREEN = colors.HexColor("#1f6f43")
ACCENT_GOLD = colors.HexColor("#f59e0b")
DARK_SLATE = colors.HexColor("#0f172a")
MUTED_SLATE = colors.HexColor("#475569")
LIGHT_BG = colors.HexColor("#f8fafc")
BORDER_COLOR = colors.HexColor("#cbd5e1")


def _num(v, digits=1) -> str:
    return "-" if v is None else f"{v:,.{digits}f}"


def _pct(v, digits=1) -> str:
    return "-" if v is None else f"{v:,.{digits}f}%"


def _get_asset_paths() -> tuple[Path | None, Path | None]:
    backend_assets = Path(__file__).resolve().parent.parent / "assets"
    frontend_public = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "public"

    nisr_path = backend_assets / "nisr-logo.png"
    if not nisr_path.is_file():
        nisr_path = frontend_public / "nisr-logo.png"

    logo_path = backend_assets / "logo.png"
    if not logo_path.is_file():
        logo_path = frontend_public / "logo.png"

    return (nisr_path if nisr_path.is_file() else None, logo_path if logo_path.is_file() else None)


def _generate_map_image(target_district: str | None = None) -> io.BytesIO:
    """Renders a geographic map of Rwanda with the selected district highlighted."""
    geo = store.districts_geojson()
    fig, ax = plt.subplots(figsize=(6.2, 4.0), dpi=180)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")

    target_name = (target_district or "").strip().lower()
    highlight_poly_center = None

    for feat in geo["features"]:
        name = feat["properties"]["shapeName"]
        is_target = bool(target_district and name.lower() == target_name)
        geom = feat["geometry"]
        gtype = geom["type"]
        coords_list = geom["coordinates"]

        if is_target:
            edge_color = "#003b73"
            face_color = "#005baa"
            linewidth = 1.8
            zorder = 5
        else:
            edge_color = "#94a3b8"
            face_color = "#e2e8f0" if target_district else "#dbeafe"
            linewidth = 0.5
            zorder = 2

        polys = [coords_list] if gtype == "Polygon" else coords_list

        for poly in polys:
            ext_ring = poly[0]
            pts = np.array(ext_ring)
            ax.add_patch(MplPolygon(pts, closed=True, facecolor=face_color, edgecolor=edge_color, linewidth=linewidth, zorder=zorder))
            if is_target and highlight_poly_center is None:
                highlight_poly_center = (float(np.mean(pts[:, 0])), float(np.mean(pts[:, 1])))

    ax.autoscale()
    ax.set_aspect("equal")
    ax.axis("off")

    if target_district and highlight_poly_center:
        cx, cy = highlight_poly_center
        ax.plot(cx, cy, marker="o", markersize=6, color="#f59e0b", markeredgecolor="#ffffff", markeredgewidth=1.2, zorder=10)
        ax.annotate(
            f"{target_district.title()}",
            xy=(cx, cy),
            xytext=(cx + 0.14, cy + 0.12),
            fontweight="bold",
            fontsize=9,
            color="#0f172a",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#ffffff", edgecolor="#005baa", linewidth=1.2, alpha=0.96),
            arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=-0.1", color="#005baa", lw=1.2),
            zorder=12,
        )

    title_text = f"Geographic Scope: {target_district.title()} District, Rwanda" if target_district else "Geographic Scope: Republic of Rwanda (30 Districts)"
    ax.set_title(title_text, fontsize=9.5, fontweight="bold", color="#1e293b", pad=6)

    buf = io.BytesIO()
    plt.tight_layout(pad=0.4)
    plt.savefig(buf, format="png", dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf


def _table(rows: list[list], widths: list[float] | None = None, header_bg: colors.Color = PRIMARY_BLUE) -> Table:
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("FONTSIZE", (0, 1), (-1, -1), 8.0),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _build_header(nisr_path: Path | None, logo_path: Path | None, styles: dict) -> Table:
    """Builds the official two-sided institutional header: NISR on the left, Analiza/FarmGap on the right."""
    # Left side: NISR logo and institutional hierarchy
    left_cells = []
    if nisr_path and nisr_path.is_file():
        left_cells.append(Image(str(nisr_path), width=3.8 * cm, height=1.6 * cm))
    left_cells.extend([
        Paragraph("<b>REPUBLIC OF RWANDA</b>", styles["NISR_Gov"]),
        Paragraph("<b>National Institute of Statistics of Rwanda (NISR)</b>", styles["NISR_Name"]),
        Paragraph("Agricultural &amp; Environmental Statistics &nbsp;|&nbsp; microdata.statistics.gov.rw", styles["NISR_Sub"]),
    ])

    sub_left = Table([[c] for c in left_cells], colWidths=[9.0 * cm])
    sub_left.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))

    # Right side: Analiza / FarmGap platform branding
    right_cells = []
    if logo_path and logo_path.is_file():
        right_cells.append(Image(str(logo_path), width=2.0 * cm, height=2.0 * cm))
    right_cells.extend([
        Paragraph("<b>FarmGap Rwanda</b>", styles["Brand_Name"]),
        Paragraph("Agricultural Intelligence &amp; Yield Gap Analytics", styles["Brand_Title"]),
        Paragraph("Developed by Team BitBender &nbsp;|&nbsp; NISR Big Data Hackathon 2026", styles["Brand_Sub"]),
    ])

    sub_right = Table([[c] for c in right_cells], colWidths=[9.0 * cm])
    sub_right.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))

    header_tbl = Table([[sub_left, sub_right]], colWidths=[9.0 * cm, 9.0 * cm])
    header_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return header_tbl


def _build_pdf(year: int, season: str, crop: str, district: str | None) -> bytes:
    styles = getSampleStyleSheet()

    # Custom styles
    styles.add(ParagraphStyle(
        "NISR_Gov", parent=styles["Normal"], fontSize=7.5, leading=9.5, textColor=PRIMARY_BLUE, fontName="Helvetica-Bold"
    ))
    styles.add(ParagraphStyle(
        "NISR_Name", parent=styles["Normal"], fontSize=8.5, leading=10.5, textColor=DARK_SLATE, fontName="Helvetica-Bold"
    ))
    styles.add(ParagraphStyle(
        "NISR_Sub", parent=styles["Normal"], fontSize=6.5, leading=8.5, textColor=MUTED_SLATE
    ))
    styles.add(ParagraphStyle(
        "Brand_Name", parent=styles["Normal"], fontSize=9.5, leading=11.5, alignment=TA_RIGHT, textColor=PRIMARY_BLUE, fontName="Helvetica-Bold"
    ))
    styles.add(ParagraphStyle(
        "Brand_Title", parent=styles["Normal"], fontSize=7.5, leading=9.5, alignment=TA_RIGHT, textColor=DARK_SLATE, fontName="Helvetica-Bold"
    ))
    styles.add(ParagraphStyle(
        "Brand_Sub", parent=styles["Normal"], fontSize=6.5, leading=8.5, alignment=TA_RIGHT, textColor=MUTED_SLATE
    ))

    styles.add(ParagraphStyle(
        "DocTitle", parent=styles["Normal"], fontSize=14, leading=18, textColor=PRIMARY_BLUE, fontName="Helvetica-Bold", alignment=TA_LEFT
    ))
    styles.add(ParagraphStyle(
        "DocMeta", parent=styles["Normal"], fontSize=8.5, leading=12, textColor=MUTED_SLATE, alignment=TA_LEFT
    ))
    styles.add(ParagraphStyle(
        "SectionHead", parent=styles["Normal"], fontSize=10.5, leading=14, textColor=PRIMARY_BLUE, fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=4
    ))
    styles.add(ParagraphStyle(
        "CardTitle", parent=styles["Normal"], fontSize=8.5, leading=11, fontName="Helvetica-Bold", textColor=DARK_SLATE
    ))
    styles.add(ParagraphStyle(
        "CardText", parent=styles["Normal"], fontSize=8.0, leading=11, textColor=MUTED_SLATE
    ))
    styles.add(ParagraphStyle(
        "FindingTitle", parent=styles["Normal"], fontSize=8.5, leading=11, fontName="Helvetica-Bold", textColor=PRIMARY_BLUE
    ))
    styles.add(ParagraphStyle(
        "FindingBody", parent=styles["Normal"], fontSize=8.0, leading=11, textColor=DARK_SLATE
    ))
    styles.add(ParagraphStyle(
        "FindingAction", parent=styles["Normal"], fontSize=7.5, leading=10.5, textColor=FOREST_GREEN, fontName="Helvetica-Oblique"
    ))
    styles.add(ParagraphStyle(
        "FooterNote", parent=styles["Normal"], fontSize=7.0, leading=9.5, textColor=MUTED_SLATE, alignment=TA_CENTER
    ))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
    )
    story = []

    # 1. Official Dual-Sided Header (NISR Left, Analiza Right)
    nisr_path, logo_path = _get_asset_paths()
    story.append(_build_header(nisr_path, logo_path, styles))
    story.append(Spacer(1, 4))

    # Dual-tone decorative accent bar (Blue & Gold)
    accent_bar = Table([[""]], colWidths=[18.0 * cm], rowHeights=[2.5])
    accent_bar.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PRIMARY_BLUE),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(accent_bar)
    story.append(Spacer(1, 8))

    # 2. Document Title Banner
    now_str = datetime.date.today().strftime("%B %d, %Y")
    if district:
        title_text = f"{district.upper()} DISTRICT AGRICULTURAL PERFORMANCE REPORT"
        sub_text = f"Evaluated for: <b>{year} Season {season}</b> &nbsp;|&nbsp; Focus Crop: <b>{crop}</b> &nbsp;|&nbsp; Published: <b>{now_str}</b>"
    else:
        title_text = "RWANDA NATIONAL AGRICULTURAL PERFORMANCE REPORT"
        sub_text = f"National Overview for: <b>{year} Season {season}</b> &nbsp;|&nbsp; Focus Crop: <b>{crop}</b> &nbsp;|&nbsp; Published: <b>{now_str}</b>"

    banner_table = Table([
        [Paragraph(title_text, styles["DocTitle"])],
        [Paragraph(sub_text, styles["DocMeta"])],
    ], colWidths=[18.0 * cm])
    banner_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(banner_table)
    story.append(Spacer(1, 10))

    # 3. Geographic Scope & Map + Findings
    map_buf = _generate_map_image(district)
    map_img = Image(map_buf, width=8.5 * cm, height=5.5 * cm)

    if district:
        profile = geography_service.profile(district, year, season)
        province = profile.get("province", "Rwanda")
        pr = priority_service.priorities(year, season, crop)
        d_match = next((d for d in pr["districts"] if d["district"].lower() == district.lower()), None)

        rank_val = d_match["rank"] if d_match else "-"
        score_val = _num(d_match["score"]) if d_match else "-"
        yield_val = _num(d_match["yield_kg_ha"], 0) if d_match else "-"
        gain_pct = _pct(d_match["potential_gain_pct"]) if d_match else "-"
        add_prod = _num(d_match["additional_production_t"], 0) if d_match else "-"
        seed_pct = _pct(d_match["improved_seed_pct"]) if d_match else "-"
        fert_pct = _pct(d_match["inorganic_fertilizer_pct"]) if d_match else "-"
        ext_pct = _pct(d_match["extension_access_pct"]) if d_match else "-"

        # Right side: District snapshot table
        stat_rows = [
            ["Metric / Indicator", "District Value", "Status / Target"],
            ["Administrative Scope", f"{district.title()} District", f"{province} Province"],
            [f"Priority Support Rank ({crop})", f"Rank #{rank_val} of 30", f"Priority Score: {score_val}/100"],
            [f"Current {crop} Yield", f"{yield_val} kg/ha", "SAS 2024-2025"],
            [f"Potential Yield Uplift", f"+{gain_pct}", f"+{add_prod} tonnes potential"],
            ["Improved Seed Adoption", seed_pct, "Universal target: 100%"],
            ["Inorganic Fertilizer Adoption", fert_pct, "Universal target: 100%"],
            ["Extension Service Access", ext_pct, "Household outreach"],
        ]
        stat_tbl = Table(stat_rows, colWidths=[4.2 * cm, 2.6 * cm, 2.7 * cm])
        stat_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))

        geo_table = Table([[map_img, stat_tbl]], colWidths=[8.5 * cm, 9.5 * cm])
        geo_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(geo_table)
        story.append(Spacer(1, 10))

        # 4. Latest Findings & Key Evidence for the District
        story.append(Paragraph(f"Latest Survey Findings & Agronomic Diagnosis for {district.title()}", styles["SectionHead"]))

        # Dynamic findings derived from data
        crop_top = sorted(profile["crop_yields"], key=lambda c: c["vs_national_pct"], reverse=True)
        top_crop_names = [f"{c['crop']} (+{c['vs_national_pct']}%)" for c in crop_top if c["vs_national_pct"] > 0][:3]
        top_crops_str = ", ".join(top_crop_names) if top_crop_names else "Stable across staple crops"

        findings = [
            (
                f"1. Crop Yield Gap Assessment ({crop})",
                f"In {district.title()}, average {crop.lower()} productivity is currently estimated at {yield_val} kg/ha. Closing the local yield gap through input bundling could increase production by +{gain_pct}, releasing an additional +{add_prod} tonnes into local food systems.",
                f"Recommended Action: Prioritize targeted input distribution voucher programs in lower-yield agro-ecological cells.",
            ),
            (
                "2. Input Adoption & Supply Chain Gaps",
                f"Improved seed is used on {seed_pct} of plots, while inorganic fertilizer adoption stands at {fert_pct}. Extension advisory services currently reach {ext_pct} of farming households in the district.",
                "Recommended Action: Strengthen farmer field schools (FFS) and couple fertilizer delivery directly with certified seed distribution.",
            ),
            (
                "3. Competitive Crop Advantages",
                f"Relative to Rwanda's national baseline, {district.title()} demonstrates strong performance in: {top_crops_str}.",
                "Recommended Action: Protect comparative advantages through targeted post-harvest facilities, drying grounds, and cooperative storage.",
            ),
        ]

        finding_rows = []
        for f_title, f_body, f_act in findings:
            cell_content = [
                Paragraph(f_title, styles["FindingTitle"]),
                Paragraph(f_body, styles["FindingBody"]),
                Paragraph(f"<b>Priority Action:</b> <i>{f_act}</i>", styles["FindingAction"]),
                Spacer(1, 3),
            ]
            finding_rows.append([cell_content])

        findings_table = Table(finding_rows, colWidths=[18.0 * cm])
        findings_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#e2e8f0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(findings_table)
        story.append(Spacer(1, 10))

        # 5. Key Indicators vs National Average Table
        story.append(Paragraph("Key Agricultural Indicators vs National Average (SAS 2024–2025)", styles["SectionHead"]))
        rows = [["Indicator", "Unit", district.title(), "Rwanda (Nat.)", "Difference", "Rank"]]
        for r in profile["indicators"]:
            name = r["name"] + (f" ({r['crop']})" if r["crop"] else "")
            diff_str = ("+" if r["difference"] > 0 else "") + _num(r["difference"])
            rank_str = f"#{r['rank']}/30" if "rank" in r else "-"
            rows.append([name, r["unit"], _num(r["value"]), _num(r["national_value"]), diff_str, rank_str])
        story.append(_table(rows, [6.0 * cm, 2.5 * cm, 2.4 * cm, 2.5 * cm, 2.4 * cm, 2.2 * cm]))
        story.append(Spacer(1, 10))

        # 6. Crop Yields in District Table
        story.append(Paragraph(f"Crop Yield Performance in {district.title()} (kg/ha)", styles["SectionHead"]))
        rows = [["Crop", f"{district.title()} (kg/ha)", "Rwanda Avg (kg/ha)", "vs National (%)", "Surveyed Plots (N)"]]
        for c in profile["crop_yields"]:
            vs_nat = ("+" if c["vs_national_pct"] > 0 else "") + _num(c["vs_national_pct"]) + "%"
            rows.append([c["crop"], _num(c["value"], 0), _num(c["national_value"], 0), vs_nat, str(c["n"])])
        story.append(_table(rows, [5.5 * cm, 3.2 * cm, 3.2 * cm, 3.2 * cm, 2.9 * cm]))
        story.append(Spacer(1, 10))

    else:
        # National Report
        ov = overview_service.overview(year, season)

        stat_rows = [
            ["Indicator", "National Value", "Previous Period", "Observation Period"],
        ]
        for k in ov["kpis"]:
            stat_rows.append([k["name"], f"{_num(k['value'])} {k['unit']}", _num(k["previous_value"]), k["period"]])
        stat_tbl = Table(stat_rows, colWidths=[4.2 * cm, 2.6 * cm, 2.7 * cm])
        stat_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))

        geo_table = Table([[map_img, stat_tbl]], colWidths=[8.5 * cm, 9.5 * cm])
        geo_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(geo_table)
        story.append(Spacer(1, 10))

        # Main Crops Table
        story.append(Paragraph("National Crop Yields & Production (SAS 2024–2025)", styles["SectionHead"]))
        rows = [["Crop", "Yield (kg/ha)", "Previous Year", "Change (%)", "Production (t)"]]
        for c in ov["crops"]:
            chg = ("+" if c["yield_change_pct"] > 0 else "") + _num(c["yield_change_pct"]) + "%"
            rows.append([c["crop"], _num(c["yield_kg_ha"], 0), _num(c["previous_yield_kg_ha"], 0), chg, _num(c["production_t"], 0)])
        story.append(_table(rows, [5.0 * cm, 3.2 * cm, 3.2 * cm, 3.2 * cm, 3.4 * cm]))
        story.append(Spacer(1, 10))

        # Priority districts
        pr = priority_service.priorities(year, season, crop)
        story.append(Paragraph(f"Top Priority Districts for {crop} Support", styles["SectionHead"]))
        p_rows = [["Rank", "District", "Priority Score", "Yield (kg/ha)", "Improved Seed %", "Fertilizer %", "Est. Gain %"]]
        for d in pr["districts"][:10]:
            p_rows.append([
                str(d["rank"]),
                d["district"],
                _num(d["score"]),
                _num(d["yield_kg_ha"], 0),
                _num(d["improved_seed_pct"]),
                _num(d["inorganic_fertilizer_pct"]),
                _num(d["potential_gain_pct"]),
            ])
        story.append(_table(p_rows, [1.8 * cm, 3.4 * cm, 2.6 * cm, 2.6 * cm, 2.6 * cm, 2.5 * cm, 2.5 * cm]))
        story.append(Spacer(1, 10))

        # Key Findings
        story.append(Paragraph("Key National Agricultural Findings & Policy Insights", styles["SectionHead"]))
        f_rows = []
        for ins in insight_service.all_insights()[:5]:
            cell_content = [
                Paragraph(ins["title"], styles["FindingTitle"]),
                Paragraph(ins["summary"], styles["FindingBody"]),
                Paragraph(f"<b>Suggested Action:</b> <i>{ins['action']}</i>", styles["FindingAction"]),
                Spacer(1, 3),
            ]
            f_rows.append([cell_content])
        f_tbl = Table(f_rows, colWidths=[18.0 * cm])
        f_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#e2e8f0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(f_tbl)
        story.append(Spacer(1, 10))

    # 7. Official Document Sign-off & Source Footer
    footer_text = (
        "<b>Data Attribution:</b> National Institute of Statistics of Rwanda (NISR), Seasonal Agricultural Survey (SAS) "
        "2024–2025 and Agriculture Household Survey (AHS) 2024 (microdata.statistics.gov.rw). "
        "Survey-weighted estimates and yield gap analytics computed by <b>FarmGap Rwanda (Team BitBender)</b> for the NISR Big Data Hackathon 2026. "
        "Aligned with Rwanda Strategic Plan for Agriculture Transformation (PSTA 5), NST2, and Vision 2050 goals."
    )
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_COLOR, spaceBefore=4, spaceAfter=6))
    story.append(Paragraph(footer_text, styles["FooterNote"]))

    doc.build(story)
    return buf.getvalue()


def _build_csv(year: int, season: str, crop: str, district: str | None) -> bytes:
    import pandas as pd

    pr = priority_service.priorities(year, season, crop)
    return pd.DataFrame(pr["districts"]).to_csv(index=False).encode("utf-8")


def _purge() -> None:
    now = time.time()
    for rid in [k for k, v in _reports.items() if now - v["created"] > TTL_SECONDS]:
        _reports.pop(rid, None)
    while len(_reports) > MAX_REPORTS:
        _reports.popitem(last=False)


def create(year: int, season: str, crop: str, district: str | None, fmt: str) -> dict:
    content = _build_pdf(year, season, crop, district) if fmt == "pdf" else _build_csv(year, season, crop, district)
    rid = uuid.uuid4().hex[:12]
    scope = district.lower() if district else "rwanda"
    _reports[rid] = {
        "created": time.time(),
        "content": content,
        "media_type": "application/pdf" if fmt == "pdf" else "text/csv",
        "filename": f"farmgap_{scope}_{year}{season}_{crop.replace(' ', '_').lower()}.{fmt}",
    }
    _purge()
    return {"report_id": rid, "filename": _reports[rid]["filename"], "size_bytes": len(content)}


def get(report_id: str) -> dict | None:
    _purge()
    return _reports.get(report_id)
