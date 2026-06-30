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

    # --- BRANDING COLORS (From Schalk template analysis) ---
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
    
    # Large Blue Title
    title = slide.shapes.add_textbox(Inches(0.5), Inches(2), Inches(12), Inches(1.5))
    tf = title.text_frame
    p = tf.add_paragraph()
    p.text = "BigQuery Housekeeping"
    apply_style(tf, font_name=HEADER_FONT, size=Pt(60), color=THG_BLUE, bold=True)
    
    # Subtitle
    subtitle = slide.shapes.add_textbox(Inches(0.5), Inches(3.2), Inches(12), Inches(1))
    tf = subtitle.text_frame
    p = tf.add_paragraph()
    p.text = "Data Estate Decommissioning & Scream Test Framework"
    apply_style(tf, font_name=BODY_FONT, size=Pt(28), color=THG_GREY)
    
    # Context line
    context = slide.shapes.add_textbox(Inches(0.5), Inches(6.5), Inches(12), Inches(0.5))
    tf = context.text_frame
    p = tf.add_paragraph()
    p.text = "EXECUTIVE REVIEW  ·  CLOUD FINOPS  ·  JUNE 2026"
    apply_style(tf, font_name=HEADER_FONT, size=Pt(14), color=THG_BLUE, bold=True)

    # --- Slide 2: The Decommissioning Strategy ---
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(slide, "Where we stand")
    
    summary = slide.shapes.add_textbox(Inches(0.5), Inches(1.2), Inches(12), Inches(1))
    tf = summary.text_frame
    p = tf.add_paragraph()
    p.text = "A multi-stage process to eliminate 'Zombie Data' with zero risk to production operations."
    apply_style(tf, font_name=BODY_FONT, size=Pt(22), color=THG_DARK)

    # KPI Boxes
    labels = [
        ("Audit", "Deep history scan (180d+)", THG_GREY),
        ("Scream Test", "Access revocation monitoring", THG_BLUE),
        ("Recoverable", "7-day post-deletion window", THG_GREEN)
    ]
    
    for i, (head, desc, color) in enumerate(labels):
        left = Inches(0.5 + (i * 4.3))
        # Value
        box = slide.shapes.add_textbox(left, Inches(2.5), Inches(4), Inches(1))
        tf = box.text_frame
        p = tf.add_paragraph()
        p.text = head
        apply_style(tf, font_name=HEADER_FONT, size=Pt(44), color=color, bold=True)
        # Label
        lbox = slide.shapes.add_textbox(left, Inches(3.3), Inches(4), Inches(0.5))
        tf = lbox.text_frame
        p = tf.add_paragraph()
        p.text = desc
        apply_style(tf, font_name=BODY_FONT, size=Pt(18), color=THG_DARK)

    # --- Slide 3: Emergency Recovery & Restoration ---
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(slide, "How to recover (Emergency Protocol)")
    
    # Subtitle for recovery
    desc = slide.shapes.add_textbox(Inches(0.5), Inches(1.2), Inches(12), Inches(1))
    tf = desc.text_frame
    p = tf.add_paragraph()
    p.text = "In the event of a 'Scream', access can be restored to any dataset in seconds."
    apply_style(tf, font_name=BODY_FONT, size=Pt(22), color=THG_GREY)

    # Process levers
    levers = [
        ("1. Automated Restore", "Use the `bq_restore_access.py` tool. It automatically pulls the metadata backup from GCS and reapplies it."),
        ("2. Metadata Backups", "All dataset policies are versioned in `gs://bq-admin-backup/backups/` before any change is made."),
        ("3. Org-Level Access", "Org Admins retain persistence via Org-level IAM. You are never locked out of managing the resource.")
    ]
    
    for i, (title, text) in enumerate(levers):
        top = Inches(2.5 + (i * 1.5))
        # Title
        tbox = slide.shapes.add_textbox(Inches(0.5), top, Inches(12), Inches(0.5))
        tf = tbox.text_frame
        p = tf.add_paragraph()
        p.text = title
        apply_style(tf, font_name=HEADER_FONT, size=Pt(24), color=THG_BLUE, bold=True)
        # Text
        mbox = slide.shapes.add_textbox(Inches(0.5), top + Inches(0.4), Inches(12), Inches(0.8))
        tf = mbox.text_frame
        p = tf.add_paragraph()
        p.text = text
        apply_style(tf, font_name=BODY_FONT, size=Pt(18), color=THG_DARK)

    # --- Slide 4: Recovery Command Reference ---
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(slide, "Operational Recovery Guide")
    
    # Code Box
    left, top, width, height = Inches(1), Inches(1.8), Inches(11.3), Inches(4.5)
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = THG_DARK
    shape.line.color.rgb = THG_BLUE
    
    tf = shape.text_frame
    tf.text = (
        "# Restore a specific dataset\n"
        "python3 bq_restore_access.py --dataset project:dataset\n\n"
        "# Restore an entire tranche (e.g., if a whole team 'screams')\n"
        "python3 bq_restore_access.py --tranche 1.1\n\n"
        "# Emergency 'Undo' for all active scream tests\n"
        "python3 bq_restore_access.py --all\n\n"
        "# Verify backup presence before restoration\n"
        "gsutil ls gs://bq-admin-backup/backups/"
    )
    apply_style(tf, font_name="Courier New", size=Pt(20), color=WHITE)

    # --- Slide 5: The Numbers ---
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_header(slide, "Targeted Savings & Repository")
    
    infobox = slide.shapes.add_textbox(Inches(0.5), Inches(2), Inches(12), Inches(3.5))
    tf = infobox.text_frame
    p = tf.add_paragraph()
    p.text = "Audit complete across 50+ projects."
    p2 = tf.add_paragraph()
    p2.text = "Identified 120+ Stale/Abandoned datasets (Tranche 1-3)."
    p3 = tf.add_paragraph()
    p3.text = "Estimated annual savings: $28,400+ (Stale Data Storage Only)."
    p4 = tf.add_paragraph()
    p4.text = "\nCode & Documentation Repository:"
    p5 = tf.add_paragraph()
    p5.text = "https://github.com/alandoddthg/bq-housekeeping"
    
    apply_style(tf, font_name=BODY_FONT, size=Pt(32), color=THG_DARK)
    # Highlight the URL
    tf.paragraphs[4].runs[0].font.size = Pt(24)
    tf.paragraphs[4].runs[0].font.color.rgb = THG_BLUE
    tf.paragraphs[4].runs[0].font.bold = True

    prs.save("BigQuery_Housekeeping_Process.pptx")

if __name__ == "__main__":
    create_presentation()
