# Markdown Q&A System Specification

## Requirement: Markdown File Loading
The system SHALL load markdown files from one or more specified directories.

### Scenario: Load markdown files from directory
- **WHEN** a directory path is provided containing markdown files
- **THEN** the system loads all `.md` files from that directory recursively
- **AND** preserves file path information for each loaded file

### Scenario: Handle missing or empty directories
- **WHEN** no directories are specified, or a directory does not exist or is not a directory, or all directories are skipped (e.g. over file limit)
- **THEN** the system logs a warning and does not raise
- **AND** skips invalid entries and keeps only valid directories; if none remain, the directory list may be empty
- **AND** the server may start without indexed content when the directory list is empty

## Requirement: Document Chunking with Metadata
The system SHALL split markdown content into chunks while preserving structural metadata using LangChain's MarkdownTextSplitter.

### Scenario: Chunk markdown using LangChain splitter
- **WHEN** a markdown file is loaded
- **THEN** the system uses LangChain's MarkdownTextSplitter to split content
- **AND** preserves markdown structure (headers, code blocks, lists, etc.)
- **AND** preserves section hierarchy (header levels) in chunk metadata
- **AND** includes file path in chunk metadata

### Scenario: Handle chunk overlap
- **WHEN** chunks are created from markdown content
- **THEN** adjacent chunks overlap by a configurable amount (default: 200 characters)
- **AND** overlap prevents information loss at boundaries
- **AND** chunk size is configurable (default: 1000 characters)

## Requirement: Vector Index Creation
The system SHALL create a searchable vector index from markdown content.

### Scenario: Generate embeddings for chunks
- **WHEN** markdown chunks are created
- **THEN** the system generates embeddings for each chunk using an OpenAI-compatible API
- **AND** uses API base URL and API key from configuration file or environment variables
- **AND** stores embeddings in a vector database (FAISS)
- **AND** caches embeddings by content hash to avoid regenerating identical embeddings

### Scenario: Configure API settings
- **WHEN** the server starts or needs to generate embeddings
- **THEN** the system reads API configuration from config file (`~/.md-qa/config.yaml` or `config.toml`)
- **OR** reads from environment variables (`MARKDOWN_QA_API_BASE_URL`, `MARKDOWN_QA_API_KEY`, `MARKDOWN_QA_EMBEDDING_MODEL`, `MARKDOWN_QA_LLM_MODEL`)
- **AND** config file takes precedence over environment variables
- **AND** uses default embedding model "text-embedding-3-small" if not specified
- **AND** uses default LLM model "qwen-flash" if not specified
- **AND** reports error if API configuration is missing or invalid

### Scenario: Index persistence
- **WHEN** an index is created or updated
- **THEN** the system saves the index to a centralized cache directory (`~/.md-qa/cache/`)
- **AND** saves both the vector index file (`.faiss`) and metadata file (`.pkl`)
- **AND** updates a manifest file tracking which directories are indexed
- **AND** server can load previously saved indexes on startup to avoid re-indexing

### Scenario: Multiple directories in one index
- **WHEN** multiple directories are provided during index creation
- **THEN** the system combines all markdown files from all directories into a single index
- **AND** preserves directory path information in chunk metadata
- **AND** saves as one combined index file in the cache directory

### Scenario: Load index at server startup
- **WHEN** the server starts up
- **THEN** if directories are configured, the system loads indexes from disk cache if available (or builds from scratch if not), keeps them in memory, provides progress feedback during loading if it takes > 2 seconds, and reports server ready when indexes are loaded; if loading fails, the system clears the index and raises so startup fails
- **AND** if no directories are configured, the system starts without loading indexes, clears any in-memory index, and reports status indicating no indexed content (server still accepts connections)

### Scenario: Handle large indexes efficiently
- **WHEN** an index contains hundreds of markdown files (10,000+ chunks)
- **THEN** the system loads the index efficiently using FAISS
- **AND** keeps the index in memory for fast queries
- **AND** search performance remains fast (sub-second search time) regardless of index size

### Scenario: Assign stable chunk identifiers
- **WHEN** chunks are created from a markdown file
- **THEN** each chunk receives a stable identifier derived from its file path and position
- **AND** the identifier remains consistent across index rebuilds for unchanged files
- **AND** identifiers enable removal of specific chunks when files are deleted or modified

### Scenario: Track per-file metadata in manifest
- **WHEN** an index is created or updated
- **THEN** the manifest tracks metadata for each indexed file
- **AND** metadata includes file modification time (mtime) and list of chunk identifiers
- **AND** files with changed mtime are considered modified and re-indexed
- **AND** metadata enables detection of which specific files have changed

## Requirement: Incremental Index Updates
The system SHALL update indexes incrementally when files change, only processing modified files.

### Scenario: Detect file changes
- **WHEN** the system checks for file changes
- **THEN** it compares current file modification times with stored metadata
- **AND** identifies files that were added, modified, or deleted
- **AND** uses per-file metadata from manifest to determine changes

### Scenario: Incremental update process
- **WHEN** files are added, modified, or deleted
- **THEN** the system removes chunks only for deleted or modified files
- **AND** generates embeddings only for new or modified files
- **AND** adds new chunks to the existing index without rebuilding unchanged content
- **AND** updates the manifest with new per-file metadata
- **AND** saves the updated index to disk

### Scenario: Fallback to full rebuild
- **WHEN** incremental update is not possible (e.g., index doesn't exist, missing per-file metadata)
- **THEN** the system falls back to a full index rebuild
- **AND** stores per-file metadata for future incremental updates

## Requirement: Server Process
The system SHALL run as a long-running server process that maintains indexes in memory.

### Scenario: Server startup and index loading
- **WHEN** the server starts
- **THEN** the server loads configured markdown directories
- **AND** builds or loads indexes into memory
- **AND** starts WebSocket server on configured port (default: 8765)
- **AND** reports ready status when indexes are loaded

### Scenario: Keep indexes in memory
- **WHEN** the server is running
- **THEN** indexes remain in memory for fast access
- **AND** queries use in-memory indexes without disk I/O
- **AND** query response time is consistent regardless of index size (< 2 seconds)

### Scenario: Periodic index reload with incremental updates
- **WHEN** the server is running
- **THEN** the server checks for file changes every N minutes (default: 5 minutes, configurable)
- **AND** detects which files were added, modified, or deleted since last reload
- **AND** performs incremental update if possible
- **AND** continues serving queries using the current index during reload
- **AND** atomically swaps to the updated index when ready
- **AND** saves updated index and manifest to disk cache
- **AND** falls back to full rebuild if incremental update is not possible

### Scenario: Handle queries without disk I/O
- **WHEN** a query is received
- **THEN** the server uses in-memory indexes directly
- **AND** does not perform any disk I/O during query processing
- **AND** responds quickly (< 2 seconds total)

### Scenario: Configuration file watching
- **WHEN** the server is running with a configuration file
- **THEN** the server watches the configuration file for changes
- **AND** reloads configuration when the file is modified
- **AND** applies new configuration settings without restarting
- **AND** preserves CLI argument overrides during config reload

## Requirement: Question Answering
The system SHALL answer questions using content from loaded markdown files.

### Scenario: Answer question with relevant content
- **WHEN** a user asks a question via WebSocket
- **THEN** the server uses in-memory vector indexes (no disk I/O)
- **AND** generates embedding for the question
- **AND** retrieves the most relevant chunks from the vector index
- **AND** filters chunks by relevance threshold if specified
- **AND** streams the answer using retrieved content and LLM
- **AND** sends answer chunks as they are generated
- **AND** sends source citations when streaming completes
- **AND** completes the query quickly (< 2 seconds)

### Scenario: Handle server not ready
- **WHEN** a query is received but server is still loading indexes
- **THEN** the server responds with a "not ready" status
- **AND** client can retry after a delay

### Scenario: Handle questions with no relevant content
- **WHEN** a question has no relevant content in the loaded markdown files
- **THEN** the system indicates that no relevant information was found
- **AND** does not generate a fabricated answer

### Scenario: Streaming answer generation
- **WHEN** a user asks a question via WebSocket
- **THEN** the server always streams answer chunks as they are generated
- **AND** sends stream start message first
- **AND** sends stream chunk messages for each text chunk
- **AND** sends stream end message with sources when complete
- **AND** client can display answer incrementally as it arrives

## Requirement: Source Citation Display
The system SHALL display source citations showing which markdown files were used.

### Scenario: Show sources for answer
- **WHEN** an answer is generated
- **THEN** the system displays the file path(s) used

### Scenario: Multiple source citations
- **WHEN** an answer uses content from multiple markdown files
- **THEN** the system lists all unique file paths used
- **AND** deduplicates file paths

## Requirement: WebSocket Communication
The system SHALL provide WebSocket-based communication between server and clients.

### Scenario: Client connects to server
- **WHEN** a client connects to the WebSocket server
- **THEN** the server accepts the connection
- **AND** sends a status message indicating server readiness
- **AND** maintains the connection for query messages

### Scenario: Query message format
- **WHEN** a client sends a query
- **THEN** the client sends a JSON message: `{"type": "query", "question": "..."}`
- **AND** optionally specifies index name: `{"type": "query", "question": "...", "index": "name"}`
- **AND** server validates the message format

### Scenario: Response format with sources
- **WHEN** the server processes a query
- **THEN** the server streams the response using stream messages
- **AND** sends stream start, stream chunks, and stream end messages
- **AND** stream end message contains sources: `{"type": "stream_end", "sources": [...]}`
- **AND** sources contain file paths only
- **AND** client displays the answer and sources

### Scenario: Streaming response format
- **WHEN** the server processes a query with streaming
- **THEN** the server sends stream start: `{"type": "stream_start"}`
- **AND** sends stream chunks: `{"type": "stream_chunk", "chunk": "..."}`
- **AND** sends stream end: `{"type": "stream_end", "sources": [...]}`

### Scenario: Error handling
- **WHEN** an error occurs during query processing
- **THEN** the server sends an error message: `{"type": "error", "message": "..."}`
- **AND** the connection remains open for subsequent queries

### Scenario: Invalid message handling
- **WHEN** a client sends invalid JSON or malformed message
- **THEN** the server responds with an error message
- **AND** the connection remains open for subsequent messages

## Requirement: Command-Line Client Interface
The system SHALL provide a CLI client that connects to the server for asking questions.

### Scenario: Connect to server
- **WHEN** user runs the CLI client
- **THEN** the client connects to WebSocket server (default: `ws://localhost:8765`)
- **AND** displays connection status
- **AND** allows specifying custom server address via `--server` flag

### Scenario: Send query via CLI
- **WHEN** user provides a question as CLI argument
- **THEN** the client sends query message to server via WebSocket
- **AND** waits for response
- **AND** displays answer with source citations
- **AND** exits after displaying response

### Scenario: Interactive question mode
- **WHEN** user runs the CLI in interactive mode
- **THEN** the client connects to server and maintains connection
- **AND** prompts for questions repeatedly
- **AND** sends each question to server via WebSocket
- **AND** displays answers with source citations
- **AND** continues until user exits (Ctrl+C or "quit")

### Scenario: Handle server unavailable
- **WHEN** the server is not running or unreachable
- **THEN** the client reports connection error
- **AND** suggests starting the server
- **AND** exits with error code

### Scenario: Streaming response display
- **WHEN** the server processes a query
- **THEN** the client displays answer chunks as they arrive
- **AND** displays sources when stream completes
- **AND** handles both streaming and non-streaming responses (fallback)

## Requirement: Server Configuration
The system SHALL support configuration via files and command-line arguments.

### Scenario: Load server configuration
- **WHEN** the server starts
- **THEN** it reads configuration from file (`~/.md-qa/config.yaml` or `config.toml`) if available
- **OR** reads from command-line arguments
- **OR** uses environment variables
- **AND** command-line arguments take precedence over config file
- **AND** config file takes precedence over environment variables

### Scenario: Server configuration settings
- **WHEN** configuring the server
- **THEN** the system supports setting port (default: 8765)
- **AND** supports setting directories to index
- **AND** supports setting reload interval in seconds (default: 300)
- **AND** supports setting index name (default: "default")
- **AND** supports API configuration (base URL, API key, models)

### Scenario: Configuration file format
- **WHEN** using a configuration file
- **THEN** the system supports YAML format (`config.yaml`)
- **AND** supports TOML format (`config.toml`)
- **AND** validates configuration on load
- **AND** reports errors for invalid configuration
