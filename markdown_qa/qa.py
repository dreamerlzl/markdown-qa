"""Question answering module with LLM integration."""

from typing import Any, Generator, List, Optional, Tuple

from openai import OpenAI

from markdown_qa.config import APIConfig
from markdown_qa.retrieval import RetrievalEngine


class QuestionAnswerer:
    """Generates answers to questions using LLM and retrieved context."""

    def __init__(
        self,
        retrieval_engine: RetrievalEngine,
        api_config: Optional[APIConfig] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize question answerer.

        Args:
            retrieval_engine: Retrieval engine for finding relevant chunks.
            api_config: API configuration. If None, creates from defaults.
            model: LLM model name to use for answering questions.
                   If None, uses the model from api_config.
        """
        self.retrieval_engine = retrieval_engine
        if api_config is None:
            api_config = APIConfig()
        self.api_config = api_config
        self.client = OpenAI(
            base_url=api_config.base_url,
            api_key=api_config.api_key,
        )
        self.model = model if model is not None else api_config.llm_model

    def answer(
        self, question: str, k: int = 5, min_relevance_threshold: float = 0.0
    ) -> Tuple[str, List[str]]:
        """
        Answer a question using retrieved context.

        Args:
            question: The question to answer.
            k: Number of relevant chunks to retrieve.
            min_relevance_threshold: Minimum relevance score (lower distance = more relevant).
                                     Chunks with distance above this threshold are filtered out.

        Returns:
            Tuple of (answer, sources) where sources is a list of file paths.

        Raises:
            ValueError: If no relevant content is found.
        """
        # Retrieve relevant chunks
        results = self.retrieval_engine.retrieve(question, k=k)

        # Filter by relevance threshold (lower distance = more relevant)
        filtered_results = [
            (text, metadata, distance)
            for text, metadata, distance in results
            if distance <= min_relevance_threshold or min_relevance_threshold == 0.0
        ]

        if not filtered_results:
            raise ValueError(
                "No relevant content found in the loaded markdown files to answer this question."
            )

        # Extract sources (file paths only)
        sources = []
        context_parts = []
        for text, metadata, distance in filtered_results:
            file_path = metadata.get("file_path", "")
            if file_path:
                sources.append(file_path)
            context_parts.append(f"Source: {file_path}\n{text}")

        # Build context from retrieved chunks
        context = "\n\n---\n\n".join(context_parts)

        # Generate answer using LLM
        prompt = self._build_prompt(question, context)
        answer = self._generate_answer(prompt)

        return answer, sources

    def _build_prompt(self, question: str, context: str) -> str:
        """
        Build prompt for LLM.

        Args:
            question: The question to answer.
            context: Retrieved context from markdown files.

        Returns:
            Formatted prompt string.
        """
        return f"""You are a helpful assistant that answers questions based on the provided context from markdown documentation files.

Context from documentation:
{context}

Question: {question}

Please provide a clear and concise answer based on the context above. If the context does not contain enough information to answer the question, say so explicitly. Do not make up information that is not in the context."""

    def _generate_answer(self, prompt: str) -> str:
        """
        Generate answer using LLM.

        Args:
            prompt: The prompt to send to the LLM.

        Returns:
            Generated answer string.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            raise RuntimeError(f"Failed to generate answer: {e}") from e

    def answer_stream(
        self, question: str, k: int = 5, min_relevance_threshold: float = 0.0
    ) -> Generator[Tuple[str, Optional[List[str]]], None, None]:
        """
        Answer a question using retrieved context, streaming the response.

        Yields chunks of the answer as they are generated. The final yield
        includes the sources.

        Args:
            question: The question to answer.
            k: Number of relevant chunks to retrieve.
            min_relevance_threshold: Minimum relevance score.

        Yields:
            Tuples of (chunk, sources) where sources is None for intermediate
            chunks and a list of file paths for the final chunk.

        Raises:
            ValueError: If no relevant content is found.
        """
        # Retrieve relevant chunks
        results = self.retrieval_engine.retrieve(question, k=k)

        # Filter by relevance threshold
        filtered_results = [
            (text, metadata, distance)
            for text, metadata, distance in results
            if distance <= min_relevance_threshold or min_relevance_threshold == 0.0
        ]

        if not filtered_results:
            raise ValueError(
                "No relevant content found in the loaded markdown files to answer this question."
            )

        # Extract sources
        sources = []
        context_parts = []
        for text, metadata, distance in filtered_results:
            file_path = metadata.get("file_path", "")
            if file_path:
                sources.append(file_path)
            context_parts.append(f"Source: {file_path}\n{text}")

        # Build context
        context = "\n\n---\n\n".join(context_parts)

        # Generate answer using streaming
        prompt = self._build_prompt(question, context)

        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=500,
                stream=True,
            )

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    yield (content, None)

            # Final yield with sources
            yield ("", sources)

        except Exception as e:
            raise RuntimeError(f"Failed to generate answer: {e}") from e
