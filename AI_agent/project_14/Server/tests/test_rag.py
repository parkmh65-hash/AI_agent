import os
import sys
import logging
from dotenv import load_dotenv

# Ensure app directory is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("test_rag")

def create_test_pdf(filename: str):
    """
    Creates a simple PDF file with text, a draw element (acting as image), and a layout.
    """
    import fitz
    
    logger.info(f"Creating test PDF: {filename}...")
    doc = fitz.open()
    
    # Page 1: Text and a table structure
    page1 = doc.new_page()
    page1.insert_text((50, 50), "Company Performance Report - Q3 2026", fontsize=16, color=(0, 0, 0))
    page1.insert_text((50, 80), "This report outlines the financial and operational performance of project_14 in Q3 2026. Overall revenue grew by 15% compared to Q2.", fontsize=11, color=(0.2, 0.2, 0.2))
    
    # We will simulate a table layout using fitz drawing functions
    # (So page.find_tables() has lines to detect)
    # Draw horizontal lines for table
    page1.draw_line((50, 150), (450, 150), color=(0,0,0), width=1)
    page1.draw_line((50, 180), (450, 180), color=(0,0,0), width=1)
    page1.draw_line((50, 210), (450, 210), color=(0,0,0), width=1)
    # Draw vertical lines for table columns
    page1.draw_line((50, 150), (50, 210), color=(0,0,0), width=1)
    page1.draw_line((200, 150), (200, 210), color=(0,0,0), width=1)
    page1.draw_line((450, 150), (450, 210), color=(0,0,0), width=1)
    
    # Add table cell text
    page1.insert_text((60, 170), "Quarter", fontsize=10)
    page1.insert_text((210, 170), "Revenue Growth", fontsize=10)
    page1.insert_text((60, 200), "Q3 2026", fontsize=10)
    page1.insert_text((210, 200), "+15%", fontsize=10)
    
    # Page 2: Text and an image draw
    page2 = doc.new_page()
    page2.insert_text((50, 50), "System Architecture Details", fontsize=16)
    page2.insert_text((50, 80), "Below is the architectural diagram of our multimodal processing engine.", fontsize=11)
    
    # Let's draw a nice blue rectangle to act as an image block
    page2.draw_rect((50, 120, 250, 270), color=(0, 0, 1), fill=(0.8, 0.9, 1.0), width=2)
    page2.insert_text((60, 140), "Multimodal RAG Block Diagram", fontsize=10, color=(0,0,0))
    page2.insert_text((60, 170), "[Parser] -> [Vector Store] -> [GPT-4o-mini]", fontsize=9, color=(0.1, 0.5, 0.1))
    
    # Save document
    doc.save(filename)
    doc.close()
    logger.info(f"Test PDF created successfully.")

def run_test():
    # Load environment
    load_dotenv()
    
    from app.config import config
    
    # 0. Validate Config / API key
    if not config.OPENAI_API_KEY:
        logger.error("Error: OPENAI_API_KEY environment variable is not set. Please set it before running this test.")
        return
        
    pdf_filename = "test_sample.pdf"
    
    # 1. Create a sample PDF for parsing test
    create_test_pdf(pdf_filename)
    
    # Import services
    from app.services.parser import parse_pdf
    from app.services.storage import storage_service
    from app.services.vectorstore import vector_store_service
    from app.services.retriever import retriever_service
    from app.services.generator import generator_service
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    
    # Reset vector DB first
    logger.info("Resetting ChromaDB...")
    vector_store_service.reset_db()
    
    # 2. Parse PDF
    logger.info(f"Parsing {pdf_filename}...")
    parsed_doc = parse_pdf(pdf_filename)
    
    logger.info(f"Parsed summary:")
    logger.info(f"  - Extracted Text Pages: {len(parsed_doc.texts)}")
    logger.info(f"  - Extracted Tables: {len(parsed_doc.tables)}")
    logger.info(f"  - Extracted Images: {len(parsed_doc.images)}")
    
    # 3. Process and Index
    chunks_to_add = []
    
    # Standard Text
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    for text_item in parsed_doc.texts:
        splits = text_splitter.split_text(text_item["text"])
        for sp in splits:
            chunks_to_add.append({
                "content": sp,
                "metadata": {
                    "source": parsed_doc.filename,
                    "page": text_item["page"],
                    "type": "text",
                    "original_path": "",
                    "caption": ""
                }
            })
            
    # Tables (Mock summarization if API fails or run LLM summary)
    for table_item in parsed_doc.tables:
        markdown = table_item["markdown"]
        logger.info(f"Processing table on page {table_item['page']}:\n{markdown}")
        summary = generator_service.generate_table_description(markdown)
        chunks_to_add.append({
            "content": f"Table Markdown:\n{markdown}\nTable Summary:\n{summary}",
            "metadata": {
                "source": parsed_doc.filename,
                "page": table_item["page"],
                "type": "table",
                "original_path": "",
                "caption": summary
            }
        })
        
    # Images (For testing, if PyMuPDF extracted drawing object image/bytes)
    for img_item in parsed_doc.images:
        name = img_item["name"]
        page = img_item["page"]
        img_bytes = img_item["bytes"]
        ext = img_item["ext"]
        
        # Upload
        original_path = storage_service.upload_image(img_bytes, name)
        # Summary
        description = generator_service.generate_image_description(img_bytes, ext)
        
        chunks_to_add.append({
            "content": description,
            "metadata": {
                "source": parsed_doc.filename,
                "page": page,
                "type": "image",
                "original_path": original_path,
                "caption": description
            }
        })
        
    # Index
    if chunks_to_add:
        logger.info(f"Indexing {len(chunks_to_add)} chunks into ChromaDB...")
        vector_store_service.add_documents(chunks_to_add)
    else:
        logger.warning("No chunks to index.")
        
    # 4. Search and Retrieve Test
    query = "What is the revenue growth in Q3 2026?"
    logger.info(f"Testing retrieval for query: '{query}'")
    retrieved = retriever_service.retrieve(query, top_k=3, use_multiquery=True)
    
    logger.info("Retrieved Results:")
    for idx, doc in enumerate(retrieved):
        logger.info(f"  [{idx+1}] Type: {doc['metadata']['type']}, Page: {doc['metadata']['page']}, RRF Score: {doc.get('rrf_score', 0.0):.6f}")
        logger.info(f"      Snippet: {doc['content'][:150]}...")
        
    # 5. Generate Answer Test
    logger.info("Generating answer...")
    answer = generator_service.generate_answer(query, retrieved)
    logger.info(f"Final Answer:\n{answer}")
    
    # Cleanup generated PDF
    if os.path.exists(pdf_filename):
        os.remove(pdf_filename)
        logger.info(f"Cleaned up {pdf_filename}.")

if __name__ == "__main__":
    run_test()
