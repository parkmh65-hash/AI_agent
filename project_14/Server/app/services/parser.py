import os
import fitz  # PyMuPDF
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class ParsedDocument:
    def __init__(self, filename: str):
        self.filename = filename
        self.texts: List[Dict[str, Any]] = []    # List of {"text": str, "page": int}
        self.tables: List[Dict[str, Any]] = []   # List of {"markdown": str, "page": int, "bbox": Tuple}
        self.images: List[Dict[str, Any]] = []   # List of {"bytes": bytes, "ext": str, "page": int, "name": str}

def extract_tables_from_page(page) -> List[Tuple[str, Tuple[float, float, float, float]]]:
    """
    Extracts tables from a PyMuPDF page and returns them as Markdown strings along with their bounding boxes.
    """
    extracted_tables = []
    try:
        tables = page.find_tables()
        for idx, table in enumerate(tables):
            bbox = table.bbox  # (x0, y0, x1, y1)
            data = table.extract()
            if not data or len(data) == 0:
                continue
            
            # Formulate markdown table
            markdown_lines = []
            header = data[0]
            markdown_lines.append("| " + " | ".join([str(cell or '').replace('\n', ' ').strip() for cell in header]) + " |")
            markdown_lines.append("| " + " | ".join(["---" for _ in header]) + " |")
            for row in data[1:]:
                markdown_lines.append("| " + " | ".join([str(cell or '').replace('\n', ' ').strip() for cell in row]) + " |")
            
            markdown_table = "\n".join(markdown_lines)
            extracted_tables.append((markdown_table, bbox))
    except Exception as e:
        logger.error(f"Error extracting tables: {str(e)}")
    return extracted_tables

def parse_pdf(pdf_path: str) -> ParsedDocument:
    """
    Parses a PDF file to extract text, tables, and images.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    filename = os.path.basename(pdf_path)
    parsed_doc = ParsedDocument(filename)
    
    doc = fitz.open(pdf_path)
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        page_idx = page_num + 1
        
        # 1. Extract Tables first to identify their bounding boxes
        tables_in_page = extract_tables_from_page(page)
        table_bboxes = []
        for markdown_table, bbox in tables_in_page:
            parsed_doc.tables.append({
                "markdown": markdown_table,
                "page": page_idx,
                "bbox": bbox
            })
            table_bboxes.append(bbox)
        
        # 2. Extract Text
        # We can extract text block by block and filter out blocks that overlap with tables to avoid duplicate indexing
        blocks = page.get_text("blocks")
        page_texts = []
        for block in blocks:
            x0, y0, x1, y1, text, block_no, block_type = block
            
            # Check if this text block overlaps significantly with any table bounding box
            is_table_text = False
            for t_bbox in table_bboxes:
                tx0, ty0, tx1, ty1 = t_bbox
                # Simple overlap check: check if center of text block is within table bbox
                cx = (x0 + x1) / 2
                cy = (y0 + y1) / 2
                if tx0 <= cx <= tx1 and ty0 <= cy <= ty1:
                    is_table_text = True
                    break
            
            if not is_table_text and text.strip():
                page_texts.append(text.strip())
        
        if page_texts:
            full_page_text = "\n\n".join(page_texts)
            parsed_doc.texts.append({
                "text": full_page_text,
                "page": page_idx
            })
            
        # 3. Extract Images
        image_list = page.get_images(full=True)
        for img_idx, img in enumerate(image_list):
            xref = img[0]
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                image_name = f"{filename}_page{page_idx}_img{img_idx}.{image_ext}"
                
                parsed_doc.images.append({
                    "bytes": image_bytes,
                    "ext": image_ext,
                    "page": page_idx,
                    "name": image_name
                })
            except Exception as e:
                logger.error(f"Error extracting image index {img_idx} on page {page_idx}: {str(e)}")
                
    doc.close()
    return parsed_doc
