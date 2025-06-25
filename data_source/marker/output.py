# output.py
import os

def save_markdown(output_path, fname, full_text, images, out_meta):
    print(f"[Stub] save_markdown called for {fname}")
    os.makedirs(output_path, exist_ok=True)
    output_file = os.path.join(output_path, fname.replace(".pdf", ".md"))
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(full_text)
    return output_path
