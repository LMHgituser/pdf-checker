import streamlit as st
from PyPDF2 import PdfReader
import fitz  # PyMuPDF
import io
from PIL import Image
import pikepdf

# === Printer Specs ===
PRINTER_WIDTH = 8.5       # inches
PRINTER_HEIGHT = 11       # inches
MIN_DPI = 300             # minimum image DPI
ACCEPTED_COLOR = ["DeviceCMYK", "DeviceRGB"]  # allowed color modes

# === Branding Colors (UPS-style) ===
PRIMARY_COLOR = "#FFB500"   # UPS Gold
SECONDARY_COLOR = "#3C3C3C" # Dark Gray
SUCCESS_COLOR = "#66FF66"
WARNING_COLOR = "#FFA500"
ERROR_COLOR = "#FF5555"

# === Page Setup ===
st.set_page_config(page_title="UPS Store PDF Checker", layout="wide")
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
    .subheader {{
        color: {SECONDARY_COLOR};
        font-size: 1.3rem;
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

# === Logo (optional: replace with your URL or local path) ===
st.image("UPS_Logo.png", width=150)

st.markdown('<div class="header">UPS Store PDF Print Checker 🖨️</div>', unsafe_allow_html=True)

st.markdown(
    '<div class="instructions">'
    '📥 **Drag and drop your PDF(s) here or click "Browse files".**<br>'
    f'Print specs:<br>'
    f'- Page size: {PRINTER_WIDTH} × {PRINTER_HEIGHT} inches (Letter)<br>'
    f'- Color mode: CMYK or RGB<br>'
    f'- Image resolution: minimum {MIN_DPI} DPI'
    '</div>', unsafe_allow_html=True
)

# === File uploader (drag & drop) ===
uploaded_files = st.file_uploader(
    "Upload PDF(s)", type=["pdf"], accept_multiple_files=True
)

def color_box(message, type="success"):
    if type == "success":
        st.markdown(f'<div class="success-box">{message}</div>', unsafe_allow_html=True)
    elif type == "warning":
        st.markdown(f'<div class="warning-box">{message}</div>', unsafe_allow_html=True)
    elif type == "error":
        st.markdown(f'<div class="error-box">{message}</div>', unsafe_allow_html=True)

def analyze_pdf(pdf_file):
    st.markdown(f"---\n### 📄 File: {pdf_file.name}")
    pdf_data = pdf_file.read()
    pdf_stream = io.BytesIO(pdf_data)

    # --- Basic PDF info ---
    reader = PdfReader(pdf_stream)
    num_pages = len(reader.pages)
    st.write(f"**Number of pages:** {num_pages}")
    
    first_page = reader.pages[0]
    width = float(first_page.mediabox.width) / 72
    height = float(first_page.mediabox.height) / 72
    st.write(f"**Page size:** {width:.2f}\" × {height:.2f}\"")

    # --- Page size validation ---
    if abs(width - PRINTER_WIDTH) < 0.01 and abs(height - PRINTER_HEIGHT) < 0.01:
        color_box(f"✅ Page size matches {PRINTER_WIDTH}×{PRINTER_HEIGHT} inches (Letter).", "success")
    else:
        color_box(f"⚠️ Page size does not match Letter size ({PRINTER_WIDTH}×{PRINTER_HEIGHT}).", "warning")

    # --- Image DPI check ---
    doc = fitz.open(stream=pdf_data, filetype="pdf")
    low_res_images = []
    all_dpi = []

    for page_index in range(len(doc)):
        for img in doc.get_page_images(page_index):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image = Image.open(io.BytesIO(image_bytes))
            dpi = image.info.get("dpi", (72, 72))
            all_dpi.append(dpi[0])
            if dpi[0] < MIN_DPI or dpi[1] < MIN_DPI:
                low_res_images.append((page_index+1, dpi[0], dpi[1]))

    st.subheader("🖼️ Image Resolution Check")
    if low_res_images:
        for img_info in low_res_images:
            color_box(f"⚠️ Page {img_info[0]}: {img_info[1]}×{img_info[2]} DPI", "warning")
    else:
        if all_dpi:
            color_box(f"✅ All images meet the minimum {MIN_DPI} DPI requirement.", "success")
        else:
            st.info("ℹ️ No images found in this PDF.")

    # --- Color mode check ---
    st.subheader("🎨 Color Mode Validation")
    try:
        pdf = pikepdf.open(io.BytesIO(pdf_data))
        color_spaces = set()
        for page in pdf.pages:
            resources = page.get("/Resources", {})
            xobjects = resources.get("/XObject", {})
            for obj_name in xobjects:
                obj = xobjects[obj_name]
                try:
                    cs = obj["/ColorSpace"]
                    if isinstance(cs, pikepdf.Name):
                        color_spaces.add(str(cs))
                except Exception:
                    pass

        if color_spaces:
            st.write("Detected color spaces:", ", ".join(color_spaces))
            invalid_colors = [c for c in color_spaces if c not in ACCEPTED_COLOR]
            if invalid_colors:
                for c in invalid_colors:
                    color_box(f"⚠️ Unsupported color mode detected: {c}", "warning")
            else:
                color_box("✅ All color modes are valid (CMYK or RGB).", "success")
        else:
            st.info("ℹ️ No color space info found (PDF may be text-only or grayscale).")
    except Exception as e:
        color_box(f"Error checking color: {e}", "error")

    # --- Overall validation summary ---
    st.subheader("📋 Overall Validation Summary")
    passed = True
    if not (abs(width - PRINTER_WIDTH) < 0.01 and abs(height - PRINTER_HEIGHT) < 0.01):
        passed = False
    if low_res_images:
        passed = False
    if color_spaces:
        if any(c not in ACCEPTED_COLOR for c in color_spaces):
            passed = False

    if passed:
        color_box("✅ PDF meets all printer specifications.", "success")
    else:
        color_box("⚠️ PDF does NOT meet one or more printer specifications.", "error")

# Analyze all uploaded files
if uploaded_files:
    for pdf_file in uploaded_files:
        analyze_pdf(pdf_file)

