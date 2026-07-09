import os
import uuid
import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from supabase import create_client, Client
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
        
        # Initialize Supabase client
        self.supabase: Optional[Client] = None
        self.table_name = "documents1"
        
        if config.SUPABASE_URL and config.SUPABASE_KEY:
            try:
                self.supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
                logger.info(f"Supabase Vector Store initialized. Target Table: '{self.table_name}'")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {str(e)}. Falling back to ChromaDB.")
                self.supabase = None
        
        # Initialize ChromaDB as fallback/local alternative
        self.chroma_client = chromadb.PersistentClient(
            path=config.CHROMADB_DIR,
            settings=Settings(allow_reset=True)
        )
        self.chroma_collection = self.chroma_client.get_or_create_collection(
            name="multimodal_rag",
            metadata={"hnsw:space": "cosine"}
        )
        if not self.supabase:
            logger.info("ChromaDB initialized as primary local vector store fallback.")

    def add_documents(self, documents: List[Dict[str, Any]]):
        """
        Adds list of documents/chunks to Supabase pgvector table (documents1) or fallback ChromaDB.
        """
        if not documents:
            return
            
        texts = [doc["content"] for doc in documents]
        metadatas = [doc["metadata"] for doc in documents]
        
        # Generate embeddings in batch
        embeddings = self.embeddings.embed_documents(texts)
        
        # 1. Use Supabase if configured
        if self.supabase:
            try:
                payload = []
                for i in range(len(documents)):
                    payload.append({
                        "content": texts[i],
                        "metadata": metadatas[i],
                        "embedding": embeddings[i]
                    })
                
                # Insert in batches of 100 to prevent payload limits
                batch_size = 100
                for start_idx in range(0, len(payload), batch_size):
                    batch = payload[start_idx : start_idx + batch_size]
                    self.supabase.table(self.table_name).insert(batch).execute()
                    
                logger.info(f"Successfully added {len(documents)} chunks to Supabase table '{self.table_name}'.")
                return
            except Exception as e:
                logger.error(f"Failed to insert documents into Supabase: {str(e)}. Attempting ChromaDB fallback.")
        
        # 2. ChromaDB Fallback
        ids = [str(uuid.uuid4()) for _ in documents]
        self.chroma_collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=texts
        )
        logger.info(f"Successfully added {len(documents)} chunks to ChromaDB (fallback).")

    def query(self, query_text: str, n_results: int = 5, filter_dict: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Queries Supabase match_documents1 RPC or ChromaDB fallback.
        """
        query_embedding = self.embeddings.embed_query(query_text)
        
        # 1. Use Supabase if configured
        if self.supabase:
            try:
                # Call match_documents1 RPC
                params = {
                    "query_embedding": query_embedding,
                    "match_threshold": 0.0,  # 0.0 means return all matches sorted by similarity
                    "match_count": n_results
                }
                
                response = self.supabase.rpc("match_documents1", params).execute()
                rows = response.data or []
                
                # Filter rows in memory if metadata filters are specified (RPC has basic default filter)
                if filter_dict:
                    filtered_rows = []
                    for row in rows:
                        meta = row.get("metadata", {})
                        match = True
                        for k, v in filter_dict.items():
                            if meta.get(k) != v:
                                match = False
                                break
                        if match:
                            filtered_rows.append(row)
                    rows = filtered_rows
                
                formatted_results = []
                for row in rows:
                    similarity = row.get("similarity", 0.0)
                    # Convert cosine similarity to cosine distance (for consistency with Chroma)
                    distance = 1.0 - similarity
                    formatted_results.append({
                        "id": row.get("id"),
                        "content": row.get("content"),
                        "metadata": row.get("metadata", {}),
                        "distance": distance
                    })
                return formatted_results
            except Exception as e:
                logger.error(f"Failed to query Supabase: {str(e)}. Falling back to ChromaDB query.")
        
        # 2. ChromaDB Fallback
        where = None
        if filter_dict:
            if len(filter_dict) == 1:
                where = filter_dict
            else:
                where = {"$and": [{k: v} for k, v in filter_dict.items()]}
                
        results = self.chroma_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where
        )
        
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
        # 1. Use Supabase if configured
        if self.supabase:
            try:
                # Delete all rows in documents1
                self.supabase.table(self.table_name).delete().neq("content", "").execute()
                logger.info(f"Supabase table '{self.table_name}' cleared successfully.")
                return
            except Exception as e:
                logger.error(f"Failed to reset Supabase table: {str(e)}. Resetting ChromaDB instead.")
                
        # 2. ChromaDB reset
        try:
            self.chroma_client.reset()
            self.chroma_collection = self.chroma_client.get_or_create_collection(
                name="multimodal_rag",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("ChromaDB reset successfully.")
        except Exception as e:
            logger.error(f"Failed to reset ChromaDB: {str(e)}")

vector_store_service = VectorStoreService()
