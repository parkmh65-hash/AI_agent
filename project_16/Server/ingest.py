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

def get_image_embeddings_batch(pil_images):
    """Generate normalized 512-dimension CLIP embedding vectors for a batch of images."""
    inputs = processor(images=pil_images, return_tensors="pt").to(device)
    with torch.no_grad():
        image_features = model.get_image_features(**inputs)
    # Extract pooler_output (which is the projected 512-dim features tensor in transformers v5)
    features_tensor = image_features.pooler_output
    # L2 normalize
    features_tensor = features_tensor / features_tensor.norm(dim=-1, keepdim=True)
    return features_tensor.cpu().numpy().tolist()

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
    current_images = []
    current_filenames = []
    current_base64s = []
    
    start_time = time.time()
    
    for idx, img_path in enumerate(image_files):
        filename = os.path.basename(img_path)
        try:
            # 1. Preprocess and get Base64 data
            pil_img, base64_data = preprocess_image(img_path)
            current_images.append(pil_img)
            current_filenames.append(filename)
            current_base64s.append(base64_data)
            
            # 2. Process and upload batch if full or at end
            if len(current_images) >= batch_size or (idx + 1) == total_images:
                batch_count = len(current_images)
                print(f"Processing and uploading batch of {batch_count} items (idx {idx+1-batch_count} to {idx})...", flush=True)
                
                # Get embeddings in a single forward pass
                embeddings = get_image_embeddings_batch(current_images)
                
                # Insert into local ChromaDB in batch
                collection.add(
                    ids=current_filenames,
                    embeddings=embeddings,
                    metadatas=[{"image_name": name, "base64_data": b64} for name, b64 in zip(current_filenames, current_base64s)]
                )
                
                # Insert into Supabase in batch
                supabase_batch = [{
                    "image_name": name,
                    "base64_data": b64,
                    "embedding": emb
                } for name, b64, emb in zip(current_filenames, current_base64s, embeddings)]
                
                supabase.table("fashion").insert(supabase_batch).execute()
                
                # Calculate progress and speed
                elapsed = time.time() - start_time
                speed = (idx + 1) / elapsed
                remaining = (total_images - (idx + 1)) / speed if speed > 0 else 0
                print(f"Progress: {idx + 1}/{total_images} ({(idx + 1)/total_images*100:.1f}%) | Speed: {speed:.2f} img/s | Remaining: {remaining:.1f}s", flush=True)
                
                # Reset batch lists
                current_images = []
                current_filenames = []
                current_base64s = []
                
        except Exception as e:
            print(f"Error processing {filename}: {e}", flush=True)
            # Reset batch lists to prevent poisoning subsequent batches
            current_images = []
            current_filenames = []
            current_base64s = []

    total_time = time.time() - start_time
    print(f"Finished ingesting {total_images} images in {total_time:.2f} seconds!", flush=True)

if __name__ == "__main__":
    main()
