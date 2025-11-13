from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime, timezone

def extract_pdf(pdf_path: str, out_path: str) -> Path:
    from pdfminer.high_level import extract_text  # type: ignore
    text = extract_text(pdf_path)
    # Basic cleanup: collapse excessive blank lines
    lines = [ln.rstrip() for ln in text.splitlines()]
    cleaned = []
    last_blank = False
    for ln in lines:
        blank = (ln.strip() == '')
        if blank and last_blank:
            continue
        cleaned.append(ln)
        last_blank = blank
    ts = datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    header = f"# Extracted VPR Guide (source: {pdf_path})\n\n_Extracted at {ts}_\n\n"
    out_text = header + '\n'.join(cleaned)
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(out_text, encoding='utf-8')
    return out_file

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python extract_vpr_pdf.py <pdf_path> [out_path]')
        raise SystemExit(2)
    pdf_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else str(Path(pdf_path).with_name(Path(pdf_path).stem + '_extracted.md'))
    p = extract_pdf(pdf_path, out_path)
    print(f'Wrote extracted markdown to: {p}')
