import os
import logging
from typing import Optional
from supabase import create_client, Client
from app.config import config

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        self.supabase: Optional[Client] = None
        self.bucket_name = config.SUPABASE_BUCKET
        
        # Initialize Supabase client if credentials are provided
        if config.SUPABASE_URL and config.SUPABASE_KEY:
            try:
                self.supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
                logger.info("Supabase client initialized successfully.")
                
                # Check/create bucket (Note: might fail if policy doesn't allow)
                try:
                    buckets = self.supabase.storage.list_buckets()
                    bucket_exists = any(b.name == self.bucket_name for b in buckets)
                    if not bucket_exists:
                        self.supabase.storage.create_bucket(self.bucket_name, options={"public": True})
                        logger.info(f"Created public Supabase storage bucket: {self.bucket_name}")
                except Exception as e:
                    logger.warning(f"Could not verify/create Supabase bucket: {str(e)}. Assuming it exists or permissions are restricted.")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {str(e)}. Falling back to local storage.")
                self.supabase = None
        else:
            logger.info("Supabase credentials not provided. Using local file storage fallback.")

    def upload_image(self, image_bytes: bytes, filename: str) -> str:
        """
        Uploads image bytes to Supabase Storage or saves locally.
        Returns the public URL or relative file path.
        """
        if self.supabase:
            try:
                # Upload to Supabase Storage
                # content_type is determined by extension
                ext = filename.split('.')[-1].lower()
                content_type = f"image/{ext}"
                if ext == "jpg":
                    content_type = "image/jpeg"
                
                # Remove leading/trailing slashes in filename
                clean_filename = filename.strip('/')
                
                # Upload file (with upsert=True)
                self.supabase.storage.from_(self.bucket_name).upload(
                    path=clean_filename,
                    file=image_bytes,
                    file_options={"content-type": content_type, "x-upsert": "true"}
                )
                
                # Get public URL
                public_url = self.supabase.storage.from_(self.bucket_name).get_public_url(clean_filename)
                logger.info(f"Uploaded {filename} to Supabase: {public_url}")
                return public_url
            except Exception as e:
                logger.error(f"Failed to upload image {filename} to Supabase storage: {str(e)}. Falling back to local storage.")
                # Fallback to local storage on exception
        
        # Local storage fallback
        local_path = os.path.join(config.LOCAL_STORAGE_DIR, filename)
        # Ensure subdirectory for pdf source exists if nested
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        with open(local_path, "wb") as f:
            f.write(image_bytes)
        
        logger.info(f"Saved {filename} to local storage: {local_path}")
        # Return local static URL path that FastAPI can serve
        return f"/static/extracted/{filename}"

storage_service = StorageService()
