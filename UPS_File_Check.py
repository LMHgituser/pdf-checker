import streamlit as st
from PyPDF2 import PdfReader
import fitz  # PyMuPDF
import io
from PIL import Image
import pikepdf

# === Printer Specs ===
PRINT_SIZES = [(4, 6), (5, 7), (8, 10)]  # inches
MIN_DPI = 300
SAFE_MARGIN = 0.125 * 72  # 1/8 inch in points
ACCEPTED_COLOR = ["DeviceCMYK", "DeviceRGB", "CMYK", "RGB"]

# === Branding Colors (UPS-style) ===
PRIMARY_COLOR = "#FFB500"
SECONDARY_COLOR = "#3C3C3C"
SUCCESS_COLOR = "#66FF66"
WARNING_COLOR = "#FFA500"
ERROR_COLOR = "#FF5555"

# === Page Setup ===
st.set_page_config(page_title="UPS Store Print File Checker", layout="wide")
st.markdown(
    f"""
    <style>
    .stApp {{
        background-color: #f7f7f7;
    }}
    .header {{
        color: {PRIMARY_COLOR};
        font-size: 2.5rem;
        font-weight: bold;
    }}
    .instructions {{
        background-color: #FFF3CD;
        padding: 10px;
        border-radius: 8px;
        margin-bottom: 20px;
    }}
    .success-box {{
        background-color: #D4EDDA;
        padding: 8px;
        border-radius: 5px;
        margin-bottom: 5px;
    }}
    .warning-box {{
        background-color: #FFF3CD;
        padding: 8px;
        border-radius: 5px;
        margin-bottom: 5px;
    }}
    .error-box {{
        background-color: #F8D7DA;
        padding: 8px;
        border-radius: 5px;
        margin-bottom: 5px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# === Logo (optional) ===
st.image("UPS_Logo.png", width=150)
st.markdown('<div class="header">UPS Store Print File Checker 🖨️</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="instructions">'
    '📥 **Upload your PDF, PNG, or JPEG files.**<br>'
    'Print specifications:<br>'
    '- Accepted sizes: 4×6, 5×7, or 8×10 inches<br>'
    '- Safe margin: 1/8" from all edges<br>'
    '- Minimum 300 DPI<br>'
    '- Color mode: CMYK or RGB'
    '</div>',
    unsafe_allow_html=True
)

uploaded_files = st.file_uploader(
    "Upload file(s)", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True
)

def color_box(message, type="success"):
    if type == "success":
        st.markdown(f'<div class="success-box">{message}</div>', unsafe_allow_html=True)
    elif type == "warning":
        st.markdown(f'<div class="warning-box">{message}</div>', unsafe_allow_html=True)
    elif type == "error":
        st.markdown(f'<div class="error-box">{message}</div>', unsafe_allow_html=True)

# --- Margin check for PDFs ---
def check_margin(page, page_number):
    issues = []
    for block in page.get_text("blocks"):
        x0, y0, x1, y1, text = block[:5]
        if x0 < SAFE_MARGIN or y0 < SAFE_MARGIN or x1 > page.rect.width - SAFE_MARGIN or y1 > page.rect.height - SAFE_MARGIN:
            issues.append(f"Text too close to edge on page {page_number}: '{text[:30]}...'")
    for img in page.get_images(full=True):
        xref = img[0]
        for rect in page.get_image_rects(xref):
            if rect.x0 < SAFE_MARGIN or rect.y0 < SAFE_MARGIN or rect.x1 > page.rect.width - SAFE_MARGIN or rect.y1 > page.rect.height - SAFE_MARGIN:
                issues.append(f"Image too close to edge on page {page_number}")
    return issues

# --- Analyze PDFs ---
def analyze_pdf(file):
    st.markdown(f"---\n### 📄 File: {file.name}")
    pdf_data = file.read()
    pdf_stream = io.BytesIO(pdf_data)
    reader = PdfReader(pdf_stream)
    doc = fitz.open(stream=pdf_data, filetype="pdf")

    first_page = reader.pages[0]
    width_in = float(first_page.mediabox.width) / 72
    height_in = float(first_page.mediabox.height) / 72
    st.write(f"**Page size:** {width_in:.2f} × {height_in:.2f} inches")

    # --- Size check ---
    if any(abs(width_in - w) < 0.05 and abs(height_in - h) < 0.05 for w, h in PRINT_SIZES):
        color_box("✅ Page size matches accepted print sizes.", "success")
    else:
        color_box("⚠️ Page size does not match 4×6, 5×7, or 8×10.", "warning")

    # --- Image DPI ---
    low_res = []
    all_dpi = []
    for i, page in enumerate(doc):
        for img in page.get_images(full=True):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image = Image.open(io.BytesIO(base_image["image"]))
            dpi = image.info.get("dpi", (72, 72))
            all_dpi.append(dpi[0])
            if dpi[0] < MIN_DPI or dpi[1] < MIN_DPI:
                low_res.append((i + 1, dpi))
    st.subheader("🖼️ Image Resolution Check")
    if low_res:
        for p, d in low_res:
            color_box(f"⚠️ Page {p}: {d[0]}×{d[1]} DPI (below 300)", "warning")
    else:
        color_box("✅ All images meet the 300 DPI minimum.", "success")

    # --- Color check ---
    st.subheader("🎨 Color Mode Check")
    try:
        pdf = pikepdf.open(io.BytesIO(pdf_data))
        color_spaces = set()
        for page in pdf.pages:
            res = page.get("/Resources", {})
            xobj = res.get("/XObject", {})
            for obj in xobj:
                cs = xobj[obj].get("/ColorSpace")
                if cs and isinstance(cs, pikepdf.Name):
                    color_spaces.add(str(cs))
        if color_spaces:
            invalid = [c for c in color_spaces if c not in ACCEPTED_COLOR]
            if invalid:
                color_box(f"⚠️ Unsupported color space(s): {', '.join(invalid)}. Accepted colors are CMYK & RGB.", "warning")
            else:
                color_box("✅ All colors are CMYK or RGB.", "success")
        else:
            st.info("ℹ️ No color info found (possibly grayscale/text-only).")
    except Exception as e:
        color_box(f"Error checking color: {e}", "error")

    # --- Margin check ---
    st.subheader("📐 Safe Zone Check (1/8\")")
    margin_issues = []
    for i, page in enumerate(doc, start=1):
        margin_issues.extend(check_margin(page, i))
    if margin_issues:
        for issue in margin_issues:
            color_box(f"⚠️ {issue}", "warning")
    else:
        color_box("✅ No text or images within 1/8\" of page edge.", "success")

# --- Analyze Images (PNG/JPEG) ---
def analyze_image(file):
    st.markdown(f"---\n### 🖼️ File: {file.name}")
    img = Image.open(file)
    dpi = img.info.get("dpi", (72, 72))
    width_px, height_px = img.size
    width_in = width_px / dpi[0]
    height_in = height_px / dpi[1]
    color_box(f"Image size: {width_in:.2f} × {height_in:.2f} inches at {dpi[0]} DPI", "success")

    # --- Size check ---
    if any(abs(width_in - w) < 0.1 and abs(height_in - h) < 0.1 for w, h in PRINT_SIZES):
        color_box("✅ Matches accepted print size.", "success")
    else:
        color_box("⚠️ Size not 4×6, 5×7, or 8×10.", "warning")

    # --- DPI check ---
    if dpi[0] < MIN_DPI or dpi[1] < MIN_DPI:
        color_box("⚠️ Low image resolution (<300 DPI).", "warning")
    else:
        color_box("✅ DPI meets minimum requirement.", "success")

    # --- Color mode check ---
    if img.mode in ["RGB", "CMYK"]:
        color_box(f"✅ Color mode: {img.mode}", "success")
    else:
        color_box(f"⚠️ Unusual color mode: {img.mode}", "warning")

# --- Run analysis ---
if uploaded_files:
    for f in uploaded_files:
        if f.name.lower().endswith(".pdf"):
            analyze_pdf(f)
        else:
            analyze_image(f)
