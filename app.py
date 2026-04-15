import os
import tempfile
import subprocess
from pathlib import Path

import streamlit as st

MAX_MB = 25
MAX_BYTES = MAX_MB * 1024 * 1024


def file_size_mb(path):
    return os.path.getsize(path) / (1024 * 1024)


def run_cmd(cmd):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr if result.stderr else "Error ejecutando comando")
    return result.stdout


def apply_ocr(input_path, output_path, language="spa", force_ocr=False):
    cmd = [
        "ocrmypdf",
        "-l", language,
        "--optimize", "3",
        "--rotate-pages",
        "--deskew",
        "--clean-final",
    ]

    if force_ocr:
        cmd.append("--force-ocr")
    else:
        cmd.append("--skip-text")

    cmd.extend([input_path, output_path])
    run_cmd(cmd)


def compress_pdf_gs(input_path, output_path, pdf_setting="/ebook"):
    cmd = [
        "gs",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={pdf_setting}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        f"-sOutputFile={output_path}",
        input_path,
    ]
    run_cmd(cmd)


def process_pdf(uploaded_file, language="spa", force_ocr=False):
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, uploaded_file.name)

        with open(input_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        base = Path(uploaded_file.name).stem
        ocr_path = os.path.join(tmpdir, f"{base}_ocr.pdf")

        apply_ocr(input_path, ocr_path, language=language, force_ocr=force_ocr)

        final_path = ocr_path

        if os.path.getsize(ocr_path) > MAX_BYTES:
            ebook_path = os.path.join(tmpdir, f"{base}_ocr_ebook.pdf")
            screen_path = os.path.join(tmpdir, f"{base}_ocr_screen.pdf")

            compress_pdf_gs(ocr_path, ebook_path, "/ebook")
            compress_pdf_gs(ocr_path, screen_path, "/screen")

            candidates = [ocr_path, ebook_path, screen_path]
            final_path = min(candidates, key=os.path.getsize)

        with open(final_path, "rb") as f:
            output_bytes = f.read()

        return output_bytes, os.path.basename(final_path), len(output_bytes)


st.set_page_config(page_title="PDF OCR a 25 MB", page_icon="📄", layout="centered")

st.title("📄 PDF a PDF OCR")
st.write("Sube un PDF, se le aplicará OCR y se intentará dejar bajo 25 MB.")

uploaded_file = st.file_uploader("Sube tu PDF", type=["pdf"])

language = st.selectbox(
    "Idioma OCR",
    ["spa", "spa+eng", "eng"],
    index=0
)

force_ocr = st.checkbox("Forzar OCR aunque el PDF ya tenga texto", value=False)

if uploaded_file is not None:
    input_size_mb = uploaded_file.size / (1024 * 1024)
    st.info(f"Tamaño archivo original: {input_size_mb:.2f} MB")

    if st.button("Procesar PDF"):
        with st.spinner("Aplicando OCR y optimizando tamaño..."):
            try:
                output_bytes, output_name, output_size = process_pdf(
                    uploaded_file,
                    language=language,
                    force_ocr=force_ocr
                )

                output_size_mb = output_size / (1024 * 1024)

                if output_size <= MAX_BYTES:
                    st.success(f"Archivo listo. Tamaño final: {output_size_mb:.2f} MB")
                else:
                    st.warning(
                        f"Se generó el PDF OCR, pero no se pudo bajar de {MAX_MB} MB "
                        f"sin perder más calidad. Tamaño final: {output_size_mb:.2f} MB"
                    )

                st.download_button(
                    label="Descargar PDF OCR",
                    data=output_bytes,
                    file_name=output_name,
                    mime="application/pdf"
                )

            except Exception as e:
                st.error(f"Error: {e}")
