import streamlit as st
from PyPDF2 import PdfReader
import fitz  # PyMuPDF
import io
from PIL import Image
import pikepdf

# ===============================================================
# SIZE MATCHING (YOUR NEW FUNCTION)
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
SAFE_MARGIN = 0.00001 * 72  # 1/8 inch in points
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
    """Check for Default CMYK/RGB declarations."""
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
    """Scan PDF content streams for R G B operators or CMYK operators."""
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
    """Inspect embedded image color spaces using PIL."""
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
# MARGIN CHECK
# =====================================================================

def check_margin(page, page_number):
    issues = []
    for block in page.get_text("blocks"):
        x0, y0, x1, y1, text = block[:5]
        if (
            x0 < SAFE_MARGIN or
            y0 < SAFE_MARGIN or
            x1 > page.rect.width - SAFE_MARGIN or
            y1 > page.rect.height - SAFE_MARGIN
        ):
            issues.append(f"Text too close to edge on page {page_number}: '{text[:30]}...'")

    for img in page.get_images(full=True):
        xref = img[0]
        for rect in page.get_image_rects(xref):
            if (
                rect.x0 < SAFE_MARGIN or
                rect.y0 < SAFE_MARGIN or
                rect.x1 > page.rect.width - SAFE_MARGIN or
                rect.y1 > page.rect.height - SAFE_MARGIN
            ):
                issues.append(f"Image too close to edge on page {page_number}")

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

    # --- Page size ---
    first_page = reader.pages[0]
    width_in = float(first_page.mediabox.width) / 72
    height_in = float(first_page.mediabox.height) / 72
    st.write(f"**Page size:** {width_in:.2f} × {height_in:.2f} inches")

    if size_matches(width_in, height_in, ACCEPTED_SIZES):
        color_box("✅ Page size matches accepted print sizes.", "success")
    else:
        color_box("⚠️ Page size does not match 4×6, 5×7, or 8×10.", "warning")

    # --- Image DPI ---
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
        for page, dpi in low_res:
            color_box(f"⚠️ Page {page}: {dpi[0]}×{dpi[1]} DPI (below 300)", "warning")
    else:
        color_box("✅ All images meet the 300 DPI minimum.", "success")

    # ============================================================
    #        COLOR MODE CHECK (ALL 4 METHODS)
    # ============================================================

    st.subheader("🎨 Color Mode Check")

    try:
        pdf = pikepdf.open(io.BytesIO(pdf_data))
        color_spaces = set()

        # Method 1 — Declared colors
        for page in pdf.pages:
            res = page.get("/Resources", {})
            xobjs = res.get("/XObject", {})
            for obj in xobjs:
                cs = xobjs[obj].get("/ColorSpace")
                if cs and isinstance(cs, pikepdf.Name):
                    color_spaces.add(str(cs))

        # Method 2 — Default color spaces
        default_cs = detect_default_color_space(pdf)
        if default_cs:
            color_spaces.add(default_cs)

        # Method 3 — Stream analysis
        stream_cs = detect_color_from_streams(doc)
        if stream_cs:
            color_spaces.add(stream_cs)

        # Method 4 — Image color modes
        img_modes = detect_color_from_images(doc)
        if img_modes:
            color_spaces.update(img_modes)

        # Evaluate
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

    # --- Margin check ---
    st.subheader("📐 Safe Zone Check (1/8\")")
    issues = []
    for i, page in enumerate(doc, start=1):
        issues.extend(check_margin(page, i))

    if issues:
        for issue in issues:
            color_box(f"⚠️ {issue}", "warning")
    else:
        color_box("✅ No text or images within 1/8\" of page edge.", "success")


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

    # Size check using your new function
    if size_matches(width_in, height_in, ACCEPTED_SIZES):
        color_box("✅ Matches accepted print size.", "success")
    else:
        color_box("⚠️ Size not 4×6, 5×7, or 8×10.", "warning")

    # DPI check
    if dpi[0] < MIN_DPI:
        color_box("⚠️ Low image resolution (<300 DPI).", "warning")
    else:
        color_box("✅ DPI meets minimum requirement.", "success")

    # Color mode
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
