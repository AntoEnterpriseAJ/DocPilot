import fitz
import pdfplumber
import difflib
import io
import base64

class VisualDiffer:
    """Computes textual differences and generates annotated PDFs with bounding boxes."""
    
    def diff(self, file_old_bytes: bytes, file_new_bytes: bytes) -> dict:
        """
        Compare two PDFs and draw red/green bounding boxes over differences.
        Returns a dict with base64 encoded annotated PDFs.
        """
        old_pdf = pdfplumber.open(io.BytesIO(file_old_bytes))
        new_pdf = pdfplumber.open(io.BytesIO(file_new_bytes))
        
        old_fitz = fitz.open(stream=file_old_bytes, filetype="pdf")
        new_fitz = fitz.open(stream=file_new_bytes, filetype="pdf")
        
        max_pages = max(len(old_pdf.pages), len(new_pdf.pages))
        
        for i in range(max_pages):
            old_page = old_pdf.pages[i] if i < len(old_pdf.pages) else None
            new_page = new_pdf.pages[i] if i < len(new_pdf.pages) else None
            
            old_fpage = old_fitz[i] if i < len(old_fitz) else None
            new_fpage = new_fitz[i] if i < len(new_fitz) else None
            
            old_words = old_page.extract_words() if old_page else []
            new_words = new_page.extract_words() if new_page else []
            
            old_texts = [w['text'] for w in old_words]
            new_texts = [w['text'] for w in new_words]
            
            sm = difflib.SequenceMatcher(None, old_texts, new_texts)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag in ('delete', 'replace') and old_fpage:
                    for k in range(i1, i2):
                        w = old_words[k]
                        rect = fitz.Rect(w['x0'], w['top'], w['x1'], w['bottom'])
                        old_fpage.draw_rect(rect, color=(1, 0, 0), width=1.5, fill_opacity=0.2, fill=(1, 0, 0))
                
                if tag in ('insert', 'replace') and new_fpage:
                    for k in range(j1, j2):
                        w = new_words[k]
                        rect = fitz.Rect(w['x0'], w['top'], w['x1'], w['bottom'])
                        new_fpage.draw_rect(rect, color=(0, 0.8, 0), width=1.5, fill_opacity=0.2, fill=(0, 0.8, 0))
                        
        old_out = old_fitz.write()
        new_out = new_fitz.write()
        
        return {
            "annotated_old_pdf_base64": base64.b64encode(old_out).decode("utf-8"),
            "annotated_new_pdf_base64": base64.b64encode(new_out).decode("utf-8")
        }
