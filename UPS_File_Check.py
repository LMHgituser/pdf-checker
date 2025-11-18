import streamlit as st
from PyPDF2 import PdfReader
import fitz  # PyMuPDF
import io
from PIL import Image
import pikepdf

# ===============================================================
# SIZE MATCHING
# ===============================================================
def size_matches(actual_w, actual_h, accepted_sizes, tolerance=0.05):
    """Check if (w, h) matches any accepted size in any orientation."""
    for (aw, ah) in accepted_sizes:
        # Normal orientation
        if abs(actual_w - aw) <= tolerance and abs(actual_h - ah) <= tolerance:
            return True
        # Rotated orientation
        if abs(actual_w - ah) <= tolerance and abs(actual_h - aw) <= tolerance:
            return True
    return False

ACCEPTED_SIZES = [
    (4.00, 6.00),
    (5.00, 7.00),
    (8.00, 10.00),
]

MIN_DPI = 300
SAFE_MARGIN_INCH = 1.0 # 1/8 inch
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

# === Logo ===
st.image("UPS_Logo.png", width=150)
st.markdown('<div class="header">UPS Store Print File Checker 🖨️</div>', unsafe_allow_html=True)

st.markdown(
    '<div class="instructions">'
    '📥 **Upload your PDF, PNG, or JPEG files.**<br>'
    'Print specifications:<br>'
    '- Accepted sizes: 4×6, 5×7, or 8×10 inches (any orientation)<br>'
    '- Safe margin: 1/8" from all edges<br>'
    '- Minimum 300 DPI<br>'
    '- Color mode: CMYK or RGB'
    '</div>',
    unsafe_allow_html=True
)

uploaded_files = st.file_uploader(
    "Upload file(s)", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True
)

# =====================================================================
# COLOR DETECTION HELPERS
# =====================================================================

def detect_default_color_space(pdf):
    try:
        root = pdf.root
        if "/DefaultRGB" in root:
            return "RGB"
        if "/DefaultCMYK" in root:
            return "CMYK"
    except:
        pass
    return None


def detect_color_from_streams(doc):
    try:
        for page in doc:
            text = page.get_text("text")
            if " rg" in text or " RG" in text:
                return "RGB"
            if " k" in text or " K" in text:
                return "CMYK"
    except:
        pass
    return None


def detect_color_from_images(doc):
    modes = set()
    try:
        for page in doc:
            for img in page.get_images(full=True):
                xref = img[0]
                base = doc.extract_image(xref)
                pil_img = Image.open(io.BytesIO(base["image"]))
                modes.add(pil_img.mode)
    except:
        pass
    return modes


# =====================================================================
# DISPLAY COLOR BOXES
# =====================================================================

def color_box(message, type="success"):
    if type == "success":
        st.markdown(f'<div class="success-box">{message}</div>', unsafe_allow_html=True)
    elif type == "warning":
        st.markdown(f'<div class="warning-box">{message}</div>', unsafe_allow_html=True)
    elif type == "error":
        st.markdown(f'<div class="error-box">{message}</div>', unsafe_allow_html=True)


# =====================================================================
# GEOMETRIC SAFE ZONE CHECK (TEXT ONLY)
# =====================================================================

def check_margin_content_only(page):
    """Check if any text crosses 1/8 inch margin from page edge."""
    issues = []
    margin_pts = SAFE_MARGIN_INCH * 72
    safe_rect = fitz.Rect(
        margin_pts,
        margin_pts,
        page.rect.width - margin_pts,
        page.rect.height - margin_pts,
    )

    # Only check text blocks
    for block in page.get_text("blocks"):
        x0, y0, x1, y1, text = block[:5]
        block_rect = fitz.Rect(x0, y0, x1, y1)
        if not safe_rect.contains(block_rect):
            issues.append(f"Text too close to edge: '{text[:30]}...'")

    return issues


# =====================================================================
# PDF ANALYSIS
# =====================================================================

def analyze_pdf(file):
    st.markdown(f"---\n### 📄 File: {file.name}")

    pdf_data = file.read()
    pdf_stream = io.BytesIO(pdf_data)
    reader = PdfReader(pdf_stream)
    doc = fitz.open(stream=pdf_data, filetype="pdf")

    # Page size
    first_page = reader.pages[0]
    width_in = float(first_page.mediabox.width) / 72
    height_in = float(first_page.mediabox.height) / 72
    st.write(f"**Page size:** {width_in:.2f} × {height_in:.2f} inches")

    if size_matches(width_in, height_in, ACCEPTED_SIZES):
        color_box("✅ Page size matches accepted print sizes.", "success")
    else:
        color_box("⚠️ Page size does not match 4×6, 5×7, or 8×10.", "warning")

    # Image DPI
    st.subheader("🖼️ Image Resolution Check")
    low_res = []
    for i, page in enumerate(doc):
        for img in page.get_images(full=True):
            xref = img[0]
            base = doc.extract_image(xref)
            pil_img = Image.open(io.BytesIO(base["image"]))
            dpi = pil_img.info.get("dpi", (72, 72))
            if dpi[0] < MIN_DPI or dpi[1] < MIN_DPI:
                low_res.append((i + 1, dpi))

    if low_res:
        for page_num, dpi in low_res:
            color_box(f"⚠️ Page {page_num}: {dpi[0]}×{dpi[1]} DPI (below 300)", "warning")
    else:
        color_box("✅ All images meet the 300 DPI minimum.", "success")

    # Color mode check
    st.subheader("🎨 Color Mode Check")
    try:
        pdf = pikepdf.open(io.BytesIO(pdf_data))
        color_spaces = set()

        for page in pdf.pages:
            res = page.get("/Resources", {})
            xobjs = res.get("/XObject", {})
            for obj in xobjs:
                cs = xobjs[obj].get("/ColorSpace")
                if cs and isinstance(cs, pikepdf.Name):
                    color_spaces.add(str(cs))

        default_cs = detect_default_color_space(pdf)
        if default_cs:
            color_spaces.add(default_cs)

        stream_cs = detect_color_from_streams(doc)
        if stream_cs:
            color_spaces.add(stream_cs)

        img_modes = detect_color_from_images(doc)
        if img_modes:
            color_spaces.update(img_modes)

        if color_spaces:
            invalid = [c for c in color_spaces if c not in ACCEPTED_COLOR]
            if invalid:
                color_box(f"⚠️ Unsupported color space(s): {', '.join(invalid)}", "warning")
            else:
                color_box("✅ All colors are CMYK or RGB.", "success")
        else:
            color_box("ℹ️ No detectable color information (likely grayscale).", "warning")
    except Exception as e:
        color_box(f"Error checking color: {e}", "error")

    # Safe zone check (text only)
    st.subheader("📐 Safe Zone Check (1/8\")")
    issues = []
    for i, page in enumerate(doc, start=1):
        issues.extend(check_margin_content_only(page))
    
    if issues:
        for issue in issues:
            color_box(f"⚠️ {issue}", "warning")
    else:
        color_box("✅ No text within 1/8\" of page edge.", "success")



# =====================================================================
# IMAGE ANALYSIS
# =====================================================================

def analyze_image(file):
    st.markdown(f"---\n### 🖼️ File: {file.name}")

    img = Image.open(file)
    dpi = img.info.get("dpi", (72, 72))
    width_px, height_px = img.size
    width_in = width_px / dpi[0]
    height_in = height_px / dpi[1]

    color_box(f"Image size: {width_in:.2f} × {height_in:.2f} inches at {dpi[0]} DPI", "success")

    if size_matches(width_in, height_in, ACCEPTED_SIZES):
        color_box("✅ Matches accepted print size.", "success")
    else:
        color_box("⚠️ Size not 4×6, 5×7, or 8×10.", "warning")

    if dpi[0] < MIN_DPI or dpi[1] < MIN_DPI:
        color_box("⚠️ Low image resolution (<300 DPI).", "warning")
    else:
        color_box("✅ DPI meets minimum requirement.", "success")

    if img.mode in ["RGB", "CMYK"]:
        color_box(f"✅ Color mode: {img.mode}", "success")
    else:
        color_box(f"⚠️ Unusual color mode: {img.mode}", "warning")


# =====================================================================
# PROCESS FILES
# =====================================================================

if uploaded_files:
    for f in uploaded_files:
        if f.name.lower().endswith(".pdf"):
            analyze_pdf(f)
        else:
            analyze_image(f)
