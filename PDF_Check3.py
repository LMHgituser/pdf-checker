import streamlit as st
from PyPDF2 import PdfReader
import fitz  # PyMuPDF
import io
from PIL import Image
import pikepdf

st.title("PDF Print Specification Checker 🖨️")

uploaded_file = st.file_uploader("Upload your PDF", type=["pdf"])

if uploaded_file is not None:
    pdf_data = uploaded_file.read()
    pdf_stream = io.BytesIO(pdf_data)

    reader = PdfReader(pdf_stream)
    num_pages = len(reader.pages)
    st.write(f"**Number of pages:** {num_pages}")

    # Get page size (first page)
    first_page = reader.pages[0]
    width = float(first_page.mediabox.width) / 72  # inches
    height = float(first_page.mediabox.height) / 72
    st.write(f"**Page size:** {width:.2f} × {height:.2f} inches")

    # Use PyMuPDF to extract images and DPI
    doc = fitz.open(stream=pdf_data, filetype="pdf")
    all_dpi = []
    for page_index in range(len(doc)):
        for img in doc.get_page_images(page_index):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image = Image.open(io.BytesIO(image_bytes))
            dpi = image.info.get("dpi", (72, 72))
            all_dpi.append(dpi[0])
    if all_dpi:
        avg_dpi = sum(all_dpi) / len(all_dpi)
        st.write(f"**Average Image DPI:** {avg_dpi:.0f}")
    else:
        st.write("**No images found.**")

    # Detect color mode (RGB/CMYK)
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
            st.write("**Detected color spaces:**", ", ".join(color_spaces))
        else:
            st.write("**No color space info found.**")
    except Exception as e:
        st.write("Color check error:", e)

    # Validation
    st.subheader("Validation Results")
    if (width, height) == (8.5, 11):
        st.success("✅ Page size is correct (Letter 8.5x11).")
    else:
        st.warning("⚠️ Page size does not match Letter 8.5x11.")

    if all_dpi and avg_dpi < 150:
        st.warning("⚠️ Low image resolution (<150 DPI).")
    else:
        st.success("✅ Image resolution acceptable.")
