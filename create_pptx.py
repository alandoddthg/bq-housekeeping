from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

def create_presentation():
    prs = Presentation()
    
    # Set slide size to 13.333 x 7.5 inches (Widescreen)
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # --- BRANDING COLORS ---
    THG_BLUE = RGBColor(0x1A, 0x73, 0xE8)
    THG_DARK = RGBColor(0x16, 0x20, 0x2E)
    THG_GREY = RGBColor(0x5A, 0x66, 0x75)
    THG_GREEN = RGBColor(0x1E, 0x8E, 0x5A)
    WHITE = RGBColor(0xFF, 0xFF, 0xFF)

    # --- FONTS ---
    HEADER_FONT = "Montserrat"
    BODY_FONT = "Open Sans"

    def apply_style(text_frame, font_name=BODY_FONT, size=Pt(18), color=THG_DARK, bold=False, align=PP_ALIGN.LEFT):
        for paragraph in text_frame.paragraphs:
            paragraph.alignment = align
            for run in paragraph.runs:
                run.font.name = font_name
                run.font.size = size
                run.font.color.rgb = color
                run.font.bold = bold

    def add_header(slide, title_text):
        title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12), Inches(1))
        tf = title_box.text_frame
        p = tf.add_paragraph()
        p.text = title_text
        apply_style(tf, font_name=HEADER_FONT, size=Pt(40), color=THG_DARK, bold=True)

    # --- Slide 1: Title ---
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    title = slide.shapes.add_textbox(Inches(0.5), Inches(2), Inches(12), Inches(1.5))
    tf = title.text_frame
    p = tf.add_paragraph()
    p.text = "BigQuery Housekeeping"
    apply_style(tf, font_name=HEADER_FONT, size=Pt(60), color=THG_BLUE, bold=True)
    
    subtitle = slide.shapes.add_textbox(Inches(0.5), Inches(3.2), Inches(12), Inches(1))
    tf = subtitle.text_frame
    p = tf.add_paragraph()
    p.text = "Data Estate Decommissioning & Scream Test Framework"
    apply_style(tf, font_name=BODY_FONT, size=Pt(28), color=THG_GREY)
    
    context = slide.shapes.add_textbox(Inches(0.5), Inches(6.5), Inches(12), Inches(0.5))
    tf = context.text_frame
    p = tf.add_paragraph()
    p.text = "EXECUTIVE REVIEW  ·  CLOUD FINOPS  ·  JUNE 2026"
    apply_style(tf, font_name=HEADER_FONT, size=Pt(14), color=THG_BLUE, bold=True)

    # --- Slide 2: Recovery Protocol ---
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(slide, "How to recover (Emergency Protocol)")
    levers = [
        ("1. Automated Restore", "Use `bq_restore_access.py` to pull metadata from `gs://bq-admin-backup/` and reapply in seconds."),
        ("2. Metadata Integrity", "Full access policies are versioned to GCS *before* any modification."),
        ("3. Org-Level Access", "Org Admins retain management persistence via Org-level IAM; zero lockout risk.")
    ]
    for i, (title, text) in enumerate(levers):
        top = Inches(1.8 + (i * 1.5))
        tbox = slide.shapes.add_textbox(Inches(0.5), top, Inches(12), Inches(0.5))
        tf = tbox.text_frame
        p = tf.add_paragraph()
        p.text = title
        apply_style(tf, font_name=HEADER_FONT, size=Pt(24), color=THG_BLUE, bold=True)
        mbox = slide.shapes.add_textbox(Inches(0.5), top + Inches(0.4), Inches(12), Inches(0.8))
        tf = mbox.text_frame
        p = tf.add_paragraph()
        p.text = text
        apply_style(tf, font_name=BODY_FONT, size=Pt(18), color=THG_DARK)

    # --- Slide 3: Tranche Overview (Financials & Volumes) ---
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(slide, "Tranche Analysis: Stale & Abandoned Data")
    
    rows, cols = 8, 5
    table = slide.shapes.add_table(rows, cols, Inches(0.5), Inches(1.5), Inches(12), Inches(5)).table
    headers = ["Tranche", "Cost/Mo ($)", "Volume (GB)", "Datasets", "Projects"]
    for i, h in enumerate(headers):
        cell = table.cell(0, i)
        cell.text = h
        cell.fill.solid()
        cell.fill.fore_color.rgb = THG_DARK
        cell.text_frame.paragraphs[0].font.color.rgb = WHITE
        cell.text_frame.paragraphs[0].font.bold = True

    tranche_data = [
        ["T1: Abandoned Test", "549.90", "27,494", "37", "6"],
        ["T2: Abandoned Prod", "8,913.59", "445,681", "174", "11"],
        ["T3: Small Abandoned", "227.33", "11,372", "1,010", "15"],
        ["T4: Stale (180d)", "103.68", "5,182", "39", "9"],
        ["T5: Active Test", "581.07", "29,053", "49", "12"],
        ["Subtotal (Cleanup)", "10,375.57", "518,782", "1,309", "53"],
        ["Active (Prod)", "32,906.12", "1,645,314", "788", "28"]
    ]
    for r, row in enumerate(tranche_data):
        for c, val in enumerate(row):
            cell = table.cell(r + 1, c)
            cell.text = val
            cell.text_frame.paragraphs[0].font.size = Pt(16)
            if "Subtotal" in val:
                cell.fill.solid()
                cell.fill.fore_color.rgb = RGBColor(240, 240, 240)
                cell.text_frame.paragraphs[0].font.bold = True

    # --- Slide 4: Access Profiles & Risk ---
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(slide, "Access Profiles & Cleanup Risk")
    
    left_body = slide.shapes.add_textbox(Inches(0.5), Inches(1.5), Inches(6), Inches(5))
    tf = left_body.text_frame
    p = tf.add_paragraph()
    p.text = "Key Account Profiles Identified:"
    p.font.bold = True
    p.font.size = Pt(24)
    
    profiles = [
        "Service Accounts: finops-scheduler, quota-collector, argus-investigator",
        "WIF Principals: GitHub Actions (thg-finops-prod)",
        "User Groups: Data & AI (Looker), FinOps Team, Product Owners",
        "Orphaned: 1,300+ datasets have ZERO write activity in 180+ days"
    ]
    for pf in profiles:
        p = tf.add_paragraph()
        p.text = "· " + pf
        p.font.size = Pt(18)
        p.space_before = Pt(10)

    # Youngest Access (Most Recent)
    right_body = slide.shapes.add_textbox(Inches(7), Inches(1.5), Inches(5.5), Inches(5))
    tf = right_body.text_frame
    p = tf.add_paragraph()
    p.text = "Recent Activity (Last 24h):"
    p.font.bold = True
    p.font.size = Pt(24)
    p.font.color.rgb = THG_BLUE
    
    recent = [
        "thg-data-personify: Personify (Active)",
        "thg-ingenuity: analytics_376116958 (Active)",
        "thg-ml-dev: chatbot_conversations (Active)",
        "thg-cx-data: hermes_events (Active)"
    ]
    for r in recent:
        p = tf.add_paragraph()
        p.text = "· " + r
        p.font.size = Pt(18)
        p.space_before = Pt(10)

    # --- Slide 5: Execution & Repository ---
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(slide, "Execution Control")
    
    infobox = slide.shapes.add_textbox(Inches(0.5), Inches(2), Inches(12), Inches(4))
    tf = infobox.text_frame
    p = tf.add_paragraph()
    p.text = "Control File: 20260624_Data_Estate_Cleanup_Audit.xlsx"
    p.font.bold = True
    p2 = tf.add_paragraph()
    p2.text = "Targeting 1,300+ datasets with $10k+ monthly waste potential."
    p3 = tf.add_paragraph()
    p3.text = "\nCode & Full Audit Control Repository:"
    p4 = tf.add_paragraph()
    p4.text = "https://github.com/alandoddthg/bq-housekeeping"
    
    apply_style(tf, font_name=BODY_FONT, size=Pt(28), color=THG_DARK)
    tf.paragraphs[4].runs[0].font.size = Pt(24)
    tf.paragraphs[4].runs[0].font.color.rgb = THG_BLUE
    tf.paragraphs[4].runs[0].font.bold = True

    prs.save("BigQuery_Housekeeping_Process.pptx")

if __name__ == "__main__":
    create_presentation()
