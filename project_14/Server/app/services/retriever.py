import logging
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.config import config
from app.services.vectorstore import vector_store_service

logger = logging.getLogger(__name__)

class RetrieverService:
    def __init__(self):
        # LLM for generating query variations (MultiQuery)
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.2,
            openai_api_key=config.OPENAI_API_KEY
        )
        
        # Prompt template to generate alternative queries
        self.multi_query_prompt = PromptTemplate(
            input_variables=["question"],
            template="""You are an AI assistant helping a search retriever find relevant documents in a vector database.
Generate 3 different search query variations (in Korean) related to the user's original query.
These variations should use different synonyms, sentence structures, or terminology to maximize retrieval recall of texts, tables, or images.

Original Query: {question}

Provide the output as a list of queries, one per line, without any numbering, bullet points, or additional text.
Example:
첫 번째 쿼리 변형
두 번째 쿼리 변형
세 번째 쿼리 변형"""
        )
        
        # Create the chain for query generation
        self.query_generator = self.multi_query_prompt | self.llm | StrOutputParser()

    def generate_alternative_queries(self, original_query: str) -> List[str]:
        """
        Uses an LLM to generate alternative formulations of the user query.
        """
        try:
            response = self.query_generator.invoke({"question": original_query})
            queries = [q.strip() for q in response.strip().split('\n') if q.strip()]
            # Ensure original query is included
            if original_query not in queries:
                queries.insert(0, original_query)
            logger.info(f"Generated search queries: {queries}")
            return queries
        except Exception as e:
            logger.error(f"Error generating alternative queries: {str(e)}")
            return [original_query]

    def retrieve(
        self, 
        query_text: str, 
        top_k: int = 5, 
        filter_dict: Optional[Dict[str, Any]] = None,
        use_multiquery: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Retrieves relevant documents using MultiQuery and Reciprocal Rank Fusion (RRF) reranking.
        """
        queries = self.generate_alternative_queries(query_text) if use_multiquery else [query_text]
        
        # 1. Retrieve raw results for each query
        raw_results_per_query = []
        for q in queries:
            # Query the vector store
            results = vector_store_service.query(
                query_text=q,
                n_results=top_k * 2,  # Retrieve more than top_k to allow robust RRF
                filter_dict=filter_dict
            )
            raw_results_per_query.append(results)
            
        # 2. Reciprocal Rank Fusion (RRF)
        # RRF constant k
        RRF_K = 60
        rrf_scores: Dict[str, float] = {}
        doc_map: Dict[str, Dict[str, Any]] = {}
        
        for query_results in raw_results_per_query:
            for rank, doc in enumerate(query_results):
                doc_id = doc["id"]
                doc_map[doc_id] = doc
                
                # RRF score formula: sum(1 / (RRF_K + rank))
                # rank is 0-indexed, so we use rank + 1
                rank_score = 1.0 / (RRF_K + (rank + 1))
                rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + rank_score
                
        # 3. Sort documents by RRF score descending
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        
        # 4. Compile the final top_k documents
        top_docs = []
        for doc_id in sorted_ids[:top_k]:
            doc = doc_map[doc_id]
            # Attach the rrf score to metadata for debug/info
            doc["rrf_score"] = rrf_scores[doc_id]
            top_docs.append(doc)
            
        logger.info(f"Retrieved {len(top_docs)} documents after RRF reranking.")
        return top_docs

retriever_service = RetrieverService()
