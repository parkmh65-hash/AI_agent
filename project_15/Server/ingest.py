import os
import io
import base64
import glob
import time
from PIL import Image
import torch
from transformers import CLIPProcessor, CLIPModel
from dotenv import load_dotenv
from supabase import create_client
import chromadb

# Load environment variables
dotenv_path = r"C:\Anti-project\.env"
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    load_dotenv()

# Initialize clients
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL or SUPABASE_KEY is missing from C:\\Anti-project\\.env")

print("Initializing Supabase Client...")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("Initializing ChromaDB Persistent Client...")
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection("fashion_collection")

# Load CLIP Model
print("Loading CLIP ViT-B/32 model (using CPU)...")
device = "cpu"  # Keep it CPU for local compatibility
model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

def preprocess_image(image_path, max_size=(224, 224)):
    """Resize image to max_size, convert to JPEG format, and encode as Base64."""
    img = Image.open(image_path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    
    # Resize keeping aspect ratio
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    
    # Save to JPEG bytes buffer
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=75)
    img_bytes = buffer.getvalue()
    
    # Base64 encode
    base64_str = base64.b64encode(img_bytes).decode("utf-8")
    base64_data = f"data:image/jpeg;base64,{base64_str}"
    
    return img, base64_data

def get_image_embedding(pil_image):
    """Generate normalized 512-dimension CLIP embedding vector."""
    inputs = processor(images=pil_image, return_tensors="pt").to(device)
    with torch.no_grad():
        image_features = model.get_image_features(**inputs)
    # L2 normalize
    image_features = image_features / image_features.norm(dim=-1, keepdim=True)
    return image_features[0].cpu().numpy().tolist()

def main():
    image_dir = r"C:\Users\user\Downloads\image\fashion_dataset"
    if not os.path.exists(image_dir):
        print(f"Error: Directory {image_dir} does not exist!")
        return

    # Find all PNG/JPG files
    image_files = glob.glob(os.path.exists(image_dir) and os.path.join(image_dir, "*.png")) + \
                  glob.glob(os.path.exists(image_dir) and os.path.join(image_dir, "*.jpg")) + \
                  glob.glob(os.path.exists(image_dir) and os.path.join(image_dir, "*.jpeg"))
    
    total_images = len(image_files)
    print(f"Found {total_images} fashion images to process.")

    if total_images == 0:
        return

    batch_size = 50
    supabase_batch = []
    
    start_time = time.time()
    
    for idx, img_path in enumerate(image_files):
        filename = os.path.basename(img_path)
        try:
            # 1. Preprocess and get Base64 data
            pil_img, base64_data = preprocess_image(img_path)
            
            # 2. Get CLIP embedding
            embedding = get_image_embedding(pil_img)
            
            # 3. Add to local ChromaDB
            collection.add(
                ids=[filename],
                embeddings=[embedding],
                metadatas=[{"image_name": filename, "base64_data": base64_data}]
            )
            
            # 4. Add to Supabase batch list
            supabase_batch.append({
                "image_name": filename,
                "base64_data": base64_data,
                "embedding": embedding
            })
            
            # 5. Insert batch to Supabase
            if len(supabase_batch) >= batch_size:
                print(f"Uploading batch {idx + 1 - batch_size} to {idx} to Supabase...")
                supabase.table("fashion").insert(supabase_batch).execute()
                supabase_batch = []
                
            if (idx + 1) % 50 == 0 or (idx + 1) == total_images:
                elapsed = time.time() - start_time
                speed = (idx + 1) / elapsed
                remaining = (total_images - (idx + 1)) / speed if speed > 0 else 0
                print(f"Progress: {idx + 1}/{total_images} ({(idx + 1)/total_images*100:.1f}%) | Speed: {speed:.2f} img/s | Remaining: {remaining:.1f}s")
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")
            
    # Insert any remaining records in the last batch
    if len(supabase_batch) > 0:
        print(f"Uploading final batch of {len(supabase_batch)} items...")
        try:
            supabase.table("fashion").insert(supabase_batch).execute()
        except Exception as e:
            print(f"Error uploading final batch: {e}")

    total_time = time.time() - start_time
    print(f"Finished ingesting {total_images} images in {total_time:.2f} seconds!")

if __name__ == "__main__":
    main()
