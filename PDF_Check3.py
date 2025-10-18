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

st.set_page_config(page_title="PDF Print Checker", layout="wide")
st.title("🖨️ PDF Print Specification Checker")
st.markdown("""
**Drag and drop one or more PDF files below**, or click “Browse files” to select them.

Print specifications:

- Page size: 8.5 × 11 inches (Letter)  
- Color mode: CMYK or RGB  
- Image resolution: minimum 300 DPI
""")

uploaded_files = st.file_uploader(
    "Upload PDF(s)", type=["pdf"], accept_multiple_files=True
)

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
        st.success(f"✅ Page size matches {PRINTER_WIDTH}×{PRINTER_HEIGHT} inches (Letter).")
    else:
        st.warning(f"⚠️ Page size does not match Letter size ({PRINTER_WIDTH}×{PRINTER_HEIGHT}).")

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
        st.warning("⚠️ Low-resolution images found:")
        for img_info in low_res_images:
            st.write(f" - Page {img_info[0]}: {img_info[1]}×{img_info[2]} DPI")
    else:
        if all_dpi:
            st.success(f"✅ All images meet the minimum {MIN_DPI} DPI requirement.")
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
                st.warning(f"⚠️ Unsupported color modes detected: {', '.join(invalid_colors)}")
            else:
                st.success("✅ All color modes are valid (CMYK or RGB).")
        else:
            st.info("ℹ️ No color space info found (PDF may be text-only or grayscale).")
    except Exception as e:
        st.error(f"Error checking color: {e}")

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
        st.success("✅ PDF meets all printer specifications.")
    else:
        st.error("⚠️ PDF does NOT meet one or more printer specifications.")

# Analyze all uploaded files
if uploaded_files:
    for pdf_file in uploaded_files:
        analyze_pdf(pdf_file)
