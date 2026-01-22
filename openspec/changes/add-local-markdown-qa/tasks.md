## 1. Implementation

### 1.1 Setup and Dependencies
- [x] 1.1.1 Add langchain dependency to pyproject.toml
- [x] 1.1.2 Add vector database dependency (FAISS or Chroma)
- [x] 1.1.3 Add OpenAI-compatible API client dependency (openai or compatible library)
- [x] 1.1.4 Add WebSocket library dependency (websockets or fastapi with websockets)
- [x] 1.1.6 Add configuration file parsing library (pyyaml or tomli)
- [x] 1.1.7 Add testing framework dependency (pytest)

### 1.2 Core Components

#### 1.2.1 Testing
- [x] 1.2.1.1 Write unit tests for API configuration (read from config file, env vars, precedence)
- [x] 1.2.1.3 Write unit tests for manifest file system (create, update, read `indexes.json`)

#### 1.2.2 Implementation
- [x] 1.2.2.1 Create markdown file loader module
- [x] 1.2.2.2 Implement text chunking using LangChain's MarkdownTextSplitter with metadata preservation
- [x] 1.2.2.3 Create API configuration module (read from config file or env vars)
- [x] 1.2.2.4 Create embedding generation module using OpenAI-compatible API
- [x] 1.2.2.5 Implement retry logic with exponential backoff for API calls
- [x] 1.2.2.6 Implement embedding caching to avoid redundant API calls
- [x] 1.2.2.7 Implement vector store initialization and document indexing
- [x] 1.2.2.8 Create centralized cache directory management (`~/.markdown-qa/cache/`)
- [x] 1.2.2.9 Implement index persistence (save/load to disk with naming support)
- [x] 1.2.2.10 Create manifest file system (`indexes.json`) to track directory-to-index mappings
- [x] 1.2.2.11 Implement index cache validation (check if index exists and is valid)
- [x] 1.2.2.12 Add progress indicators for index building when it takes > 2 seconds
- [x] 1.2.2.13 Create retrieval module for finding relevant chunks

### 1.3 Q&A System

#### 1.3.1 Testing
- [x] 1.3.1.1 Write unit tests for response formatter (format answer with sources, handle multiple sources)
- [x] 1.3.1.2 Write integration tests for complete Q&A flow (retrieve chunks → generate answer → format with sources)

#### 1.3.2 Implementation
- [x] 1.3.2.1 Implement question answering with LLM integration
- [x] 1.3.2.2 Add source citation extraction and formatting
- [x] 1.3.2.3 Create response formatter that includes sources

### 1.4 Server Implementation

#### 1.4.1 Testing
- [x] 1.4.1.1 Write unit tests for server configuration (port, directories, reload interval parsing)
- [x] 1.4.1.2 Write unit tests for in-memory index manager (load indexes, keep in memory, swap atomically)
- [x] 1.4.1.3 Write unit tests for WebSocket message protocol (query, response, error, status message formats)
- [x] 1.4.1.4 Write unit tests for query handler (process query, use in-memory indexes, return response)
- [x] 1.4.1.5 Write unit tests for periodic reload scheduler (schedule timing, background execution)
- [x] 1.4.1.6 Write unit tests for atomic index swapping (old index used during reload, swap when ready)
- [x] 1.4.1.7 Write unit tests for server startup/shutdown handlers (graceful startup, cleanup on shutdown)
- [x] 1.4.1.8 Write unit tests for server status reporting (ready, indexing states)
- [ ] 1.4.1.9 Write integration tests for WebSocket server (connection handling, message exchange, multiple clients)
- [ ] 1.4.1.10 Write integration tests for server with periodic reload (reload triggers, index updates, query continuity)

#### 1.4.2 Implementation
- [x] 1.4.2.1 Create server module with main entry point
- [x] 1.4.2.2 Implement server configuration (port, directories, reload interval, API settings)
- [x] 1.4.2.3 Validate API configuration on startup (check API base URL and key)
- [x] 1.4.2.4 Create in-memory index manager (loads indexes at startup, keeps in memory)
- [x] 1.4.2.5 Implement WebSocket server setup and connection handling
- [x] 1.4.2.6 Define WebSocket message protocol (query, response, error, status messages)
- [x] 1.4.2.7 Implement query handler that uses in-memory indexes
- [x] 1.4.2.8 Create periodic reload scheduler (every 5 minutes by default)
- [x] 1.4.2.9 Implement atomic index swapping during reload (queries use old index until new ready)
- [x] 1.4.2.10 Add server startup/shutdown handlers
- [x] 1.4.2.11 Implement server status reporting (ready, indexing, etc.)
- [x] 1.4.2.12 Add graceful shutdown handling

### 1.5 CLI Client Implementation

#### 1.5.1 Testing
- [x] 1.5.1.1 Write unit tests for query message sending (format messages, send via WebSocket)
- [x] 1.5.1.2 Write unit tests for response parsing (parse JSON, extract answer and sources)
- [x] 1.5.1.3 Write unit tests for single question mode (CLI argument parsing, display response)
- [x] 1.5.1.4 Write unit tests for interactive question mode (prompt loop, exit handling)
- [x] 1.5.1.5 Write unit tests for error handling (server unavailable, connection errors)
- [x] 1.5.1.6 Write integration tests for CLI client with server (end-to-end query flow)

#### 1.5.2 Implementation
- [x] 1.5.2.1 Create CLI client module that connects to WebSocket server
- [x] 1.5.2.2 Implement WebSocket client connection (default: `ws://localhost:8765`)
- [x] 1.5.2.3 Add `--server` flag for custom server address
- [x] 1.5.2.4 Implement query message sending via WebSocket
- [x] 1.5.2.5 Implement response parsing and display
- [x] 1.5.2.6 Add single question mode (question as CLI argument)
- [x] 1.5.2.7 Add interactive question mode (repeated prompts)
- [x] 1.5.2.8 Implement error handling for server unavailable scenarios
- [x] 1.5.2.9 Add connection status display

### 1.6 End-to-End Integration Testing
- [ ] 1.6.1 Write integration tests for complete flow (server startup → index loading → client query → response)
- [ ] 1.6.2 Write integration tests for periodic reload during active queries
- [ ] 1.6.3 Write integration tests for multiple clients querying simultaneously
- [ ] 1.6.4 Write integration tests for server restart and index persistence
