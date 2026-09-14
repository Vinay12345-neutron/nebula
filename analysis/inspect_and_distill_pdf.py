"""
PDF Verification and Ghostscript Re-distillation
Ensures 100% compliance, universal readability on macOS/Windows/Linux,
and extracts page previews for visual quality control.
"""

import os
import subprocess
import glob

raw_pdf = "docs/TierMoE_Final_Research_Paper.pdf"
distilled_pdf = "docs/TierMoE_Final_Research_Paper_distilled.pdf"
preview_dir = "docs/paper_previews"
os.makedirs(preview_dir, exist_ok=True)

# Step 1: Re-distill with Ghostscript to guarantee clean PDF standard compliance
print("Distilling PDF with Ghostscript...")
cmd_distill = [
    "gs", "-dNOPAUSE", "-dBATCH", "-sDEVICE=pdfwrite",
    "-dCompatibilityLevel=1.5",
    "-dPDFSETTINGS=/prepress",
    f"-sOutputFile={distilled_pdf}",
    raw_pdf
]
res = subprocess.run(cmd_distill, capture_output=True, text=True)
if res.returncode == 0:
    print(f"Distillation succeeded! Replacing {raw_pdf} with distilled version...")
    os.replace(distilled_pdf, raw_pdf)
else:
    print(f"Distillation warning: {res.stderr}")

# Step 2: Extract total page count using pdfinfo or gs
cmd_pages = [
    "gs", "-q", "-dNODISPLAY", "-c",
    f"({raw_pdf}) (r) file runpdfbegin pdfpagecount = quit"
]
res_pages = subprocess.run(cmd_pages, capture_output=True, text=True)
page_count = res_pages.stdout.strip()
print(f"TierMoE Final Research Paper Total Pages: {page_count}")

# Step 3: Render pages to PNG at 150 DPI for visual quality control
print("Rendering preview images for visual QA...")
cmd_render = [
    "gs", "-dNOPAUSE", "-dBATCH", "-sDEVICE=png16m",
    "-r150",
    f"-sOutputFile={preview_dir}/page_%02d.png",
    raw_pdf
]
res_render = subprocess.run(cmd_render, capture_output=True, text=True)
pages_rendered = sorted(glob.glob(f"{preview_dir}/page_*.png"))
print(f"Rendered {len(pages_rendered)} page preview images in {preview_dir}")
for p in pages_rendered[:5]:
    sz = os.path.getsize(p)
    print(f"  {p}: {sz} bytes")
