import os
import uuid
import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from langchain_openai import OpenAIEmbeddings
from app.config import config

logger = logging.getLogger(__name__)

class VectorStoreService:
    def __init__(self):
        # Initialize OpenAI embeddings
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=config.OPENAI_API_KEY
        )
        
        # Initialize ChromaDB
        # We use chromadb persistent client
        self.client = chromadb.PersistentClient(
            path=config.CHROMADB_DIR,
            settings=Settings(allow_reset=True)
        )
        
        # Create or get collection
        self.collection_name = "multimodal_rag"
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"} # cosine similarity
        )
        logger.info(f"ChromaDB collection '{self.collection_name}' initialized.")

    def add_documents(self, documents: List[Dict[str, Any]]):
        """
        Adds list of documents/chunks to ChromaDB.
        Each document is:
        {
            "content": str,            # The text, table markdown, or image description
            "metadata": {
                "source": str,
                "page": int,
                "type": str,          # "text" | "table" | "image"
                "original_path": str,  # File path or URL
                "caption": str        # Image summary or table description
            }
        }
        """
        if not documents:
            return
            
        ids = [str(uuid.uuid4()) for _ in documents]
        texts = [doc["content"] for doc in documents]
        metadatas = [doc["metadata"] for doc in documents]
        
        # Generate embeddings in batch using LangChain embeddings
        # since chroma's native embedding function can sometimes be finicky to configure with custom models
        embeddings = self.embeddings.embed_documents(texts)
        
        # Add to ChromaDB collection
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=texts
        )
        logger.info(f"Successfully added {len(documents)} chunks to ChromaDB.")

    def query(self, query_text: str, n_results: int = 5, filter_dict: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Queries ChromaDB for the closest vectors.
        """
        query_embedding = self.embeddings.embed_query(query_text)
        
        # Format filters for ChromaDB
        where = None
        if filter_dict:
            if len(filter_dict) == 1:
                where = filter_dict
            else:
                where = {"$and": [{k: v} for k, v in filter_dict.items()]}
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where
        )
        
        # Reformat results to a list of dicts
        formatted_results = []
        if results and results["documents"]:
            for i in range(len(results["documents"][0])):
                formatted_results.append({
                    "id": results["ids"][0][i],
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if results["distances"] else 0.0
                })
        return formatted_results

    def reset_db(self):
        """Resets the vector database."""
        try:
            self.client.reset()
            # Recreate collection after reset
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("ChromaDB reset successfully.")
        except Exception as e:
            logger.error(f"Failed to reset ChromaDB: {str(e)}")

vector_store_service = VectorStoreService()
