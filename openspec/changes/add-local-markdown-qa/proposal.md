# Change: Add Local Markdown Q&A System

## Why
Users need a system to answer questions using specified markdown files as the knowledge base, with source citations. This enables question-answering over documentation using OpenAI-compatible APIs for embeddings while keeping the query system local and efficient.

## What Changes
- Add capability to load and index markdown files from specified directories
- Implement retrieval-augmented generation (RAG) system for question answering
- Display answers with source citations showing which markdown files and sections were used
- Support querying over multiple markdown files simultaneously
- Implement long-running server process that keeps indexes in memory
- Provide WebSocket-based communication protocol for client-server interaction
- Implement periodic index reload (every 5 minutes) to keep indexes up-to-date
- Provide command-line client interface that connects to the server

## Impact
- Affected specs: New capability `markdown-qa`
- Affected code: New server module for long-running process, WebSocket handler, in-memory index management, periodic reload scheduler, and CLI client that connects to server
- Dependencies: Will require langchain, vector database (e.g., FAISS or Chroma), OpenAI-compatible API client, and WebSocket library (e.g., websockets or fastapi with websockets)
