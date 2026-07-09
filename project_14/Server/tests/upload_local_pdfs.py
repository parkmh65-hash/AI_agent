import os
import sys
import logging
from glob import glob
from dotenv import load_dotenv

# Add project Server root to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("upload_local_pdfs")

# Load environment configurations
load_dotenv()

def process_and_upload_pdfs():
    from app.config import config
    
    # 0. Check credentials
    if not config.OPENAI_API_KEY:
        logger.error("Error: OPENAI_API_KEY is not set in environment variables.")
        return

    # Check target folder
    target_dir = r"C:\Users\user\Downloads\pdf1"
    if not os.path.exists(target_dir):
        logger.info(f"Target folder '{target_dir}' does not exist. Creating it for testing...")
        os.makedirs(target_dir, exist_ok=True)
        logger.info(f"Please place your PDF files in '{target_dir}' and run this script again.")
        return

    # Find PDF files
    pdf_files = glob(os.path.join(target_dir, "*.pdf"))
    if not pdf_files:
        logger.warning(f"No PDF files (*.pdf) found in '{target_dir}'. Place PDFs in the folder and rerun.")
        return

    logger.info(f"Found {len(pdf_files)} PDF files in '{target_dir}'. Starting parsing and upload to Supabase DB (documents1)...")

    # Import RAG services inside function to ensure dotenv is fully loaded
    from app.services.parser import parse_pdf
    from app.services.storage import storage_service
    from app.services.vectorstore import vector_store_service
    from app.services.generator import generator_service
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        logger.info(f"--------------------------------------------------")
        logger.info(f"Processing document: '{filename}'...")
        
        try:
            # 1. Parse PDF (extract text, tables, images)
            parsed_doc = parse_pdf(pdf_path)
            logger.info(f"Parsed result: text pages={len(parsed_doc.texts)}, tables={len(parsed_doc.tables)}, images={len(parsed_doc.images)}")
            
            chunks_to_add = []

            # 2. Chunk and embed texts
            for text_item in parsed_doc.texts:
                page = text_item["page"]
                text_content = text_item["text"]
                splits = text_splitter.split_text(text_content)
                for sp in splits:
                    chunks_to_add.append({
                        "content": sp,
                        "metadata": {
                            "source": filename,
                            "page": page,
                            "type": "text",
                            "original_path": "",
                            "caption": ""
                        }
                    })

            # 3. Summarize and embed tables
            for idx, table_item in enumerate(parsed_doc.tables):
                page = table_item["page"]
                markdown = table_item["markdown"]
                
                logger.info(f"Generating summary for table {idx+1} on page {page}...")
                summary = generator_service.generate_table_description(markdown)
                
                chunks_to_add.append({
                    "content": f"Table Markdown:\n{markdown}\nTable Summary:\n{summary}",
                    "metadata": {
                        "source": filename,
                        "page": page,
                        "type": "table",
                        "original_path": "",
                        "caption": summary
                    }
                })

            # 4. Upload, summarize, and embed images
            for idx, img_item in enumerate(parsed_doc.images):
                page = img_item["page"]
                img_bytes = img_item["bytes"]
                ext = img_item["ext"]
                img_name = img_item["name"]

                logger.info(f"Uploading image {idx+1} on page {page} to storage...")
                original_path = storage_service.upload_image(img_bytes, img_name)

                logger.info(f"Generating analysis description for image {idx+1} on page {page}...")
                description = generator_service.generate_image_description(img_bytes, ext)

                chunks_to_add.append({
                    "content": description,
                    "metadata": {
                        "source": filename,
                        "page": page,
                        "type": "image",
                        "original_path": original_path,
                        "caption": description
                    }
                })

            # 5. Insert to Vector Store (Supabase documents1 / Chroma fallback)
            if chunks_to_add:
                logger.info(f"Indexing {len(chunks_to_add)} chunks into Vector DB...")
                vector_store_service.add_documents(chunks_to_add)
                logger.info(f"Successfully finished processing and indexing '{filename}'.")
            else:
                logger.warning(f"No chunks extracted from '{filename}'.")

        except Exception as e:
            logger.error(f"Error processing document '{filename}': {str(e)}", exc_info=True)

    logger.info(f"==================================================")
    logger.info(f"All PDF processing completed!")

if __name__ == "__main__":
    process_and_upload_pdfs()
