## ADDED Requirements

### Requirement: Markdown File Loading
The system SHALL load markdown files from one or more specified directories.

#### Scenario: Load markdown files from directory
- **WHEN** a directory path is provided containing markdown files
- **THEN** the system loads all `.md` files from that directory recursively
- **AND** preserves file path information for each loaded file

#### Scenario: Handle missing or empty directories
- **WHEN** a specified directory does not exist or contains no markdown files
- **THEN** the system reports an error or warning
- **AND** continues processing other valid directories if multiple are provided

### Requirement: Document Chunking with Metadata
The system SHALL split markdown content into chunks while preserving structural metadata using LangChain's MarkdownTextSplitter.

#### Scenario: Chunk markdown using LangChain splitter
- **WHEN** a markdown file is loaded
- **THEN** the system uses LangChain's MarkdownTextSplitter to split content
- **AND** preserves markdown structure (headers, code blocks, lists, etc.)
- **AND** preserves section hierarchy (header levels) in chunk metadata
- **AND** includes file path in chunk metadata

#### Scenario: Handle chunk overlap
- **WHEN** chunks are created from markdown content
- **THEN** adjacent chunks overlap by a configurable amount (default: 200 characters)
- **AND** overlap prevents information loss at boundaries
- **AND** chunk size is configurable (default: 1000 characters)

### Requirement: Vector Index Creation
The system SHALL create a searchable vector index from markdown content.

#### Scenario: Generate embeddings for chunks
- **WHEN** markdown chunks are created
- **THEN** the system generates embeddings for each chunk using an OpenAI-compatible API
- **AND** uses API base URL and API key from configuration file or environment variables
- **AND** stores embeddings in a vector database (FAISS)

#### Scenario: Configure API settings
- **WHEN** the server starts or needs to generate embeddings
- **THEN** the system reads API configuration from config file (`~/.markdown-qa/config.yaml` or `config.toml`)
- **OR** reads from environment variables (`MARKDOWN_QA_API_BASE_URL`, `MARKDOWN_QA_API_KEY`)
- **AND** config file takes precedence over environment variables
- **AND** reports error if API configuration is missing or invalid

#### Scenario: Index persistence
- **WHEN** an index is created or updated
- **THEN** the system saves the index to a centralized cache directory (e.g., `~/.markdown-qa/cache/`)
- **AND** saves both the vector index file (`.faiss`) and metadata file (`.pkl`)
- **AND** updates a manifest file tracking which directories are indexed
- **AND** server can load previously saved indexes on startup to avoid re-indexing

#### Scenario: Multiple directories in one index
- **WHEN** multiple directories are provided during index creation
- **THEN** the system combines all markdown files from all directories into a single index
- **AND** preserves directory path information in chunk metadata
- **AND** saves as one combined index file in the cache directory

#### Scenario: Load index at server startup
- **WHEN** the server starts up
- **THEN** the system loads indexes from disk cache if available (or builds from scratch if not)
- **AND** keeps indexes in memory for fast query access
- **AND** provides progress feedback during loading if it takes > 2 seconds
- **AND** reports server ready status when indexes are loaded

#### Scenario: Handle large indexes efficiently
- **WHEN** an index contains hundreds of markdown files (10,000+ chunks)
- **THEN** the system loads the index efficiently using FAISS
- **AND** keeps the index in memory for fast queries
- **AND** search performance remains fast (sub-second search time) regardless of index size

### Requirement: Server Process
The system SHALL run as a long-running server process that maintains indexes in memory.

#### Scenario: Server startup and index loading
- **WHEN** the server starts
- **THEN** the server loads configured markdown directories
- **AND** builds or loads indexes into memory
- **AND** starts WebSocket server on configured port (default: 8765)
- **AND** reports ready status when indexes are loaded

#### Scenario: Keep indexes in memory
- **WHEN** the server is running
- **THEN** indexes remain in memory for fast access
- **AND** queries use in-memory indexes without disk I/O
- **AND** query response time is consistent regardless of index size (< 2 seconds)

#### Scenario: Periodic index reload
- **WHEN** the server is running
- **THEN** the server rebuilds indexes every 5 minutes in the background
- **AND** continues serving queries using the current index during reload
- **AND** atomically swaps to the new index when ready
- **AND** saves updated indexes to disk cache

#### Scenario: Handle queries without disk I/O
- **WHEN** a query is received
- **THEN** the server uses in-memory indexes directly
- **AND** does not perform any disk I/O during query processing
- **AND** responds quickly (< 2 seconds total)

### Requirement: Question Answering
The system SHALL answer questions using content from loaded markdown files.

#### Scenario: Answer question with relevant content
- **WHEN** a user asks a question via WebSocket
- **THEN** the server uses in-memory vector indexes (no disk I/O)
- **AND** retrieves the most relevant chunks from the vector index
- **AND** generates an answer using retrieved content
- **AND** returns the answer with source citations to the client
- **AND** completes the query quickly (< 2 seconds)

#### Scenario: Handle server not ready
- **WHEN** a query is received but server is still loading indexes
- **THEN** the server responds with a "not ready" status
- **AND** client can retry after a delay

#### Scenario: Handle questions with no relevant content
- **WHEN** a question has no relevant content in the loaded markdown files
- **THEN** the system indicates that no relevant information was found
- **AND** does not generate a fabricated answer

### Requirement: Source Citation Display
The system SHALL display source citations showing which markdown files were used.

#### Scenario: Show sources for answer
- **WHEN** an answer is generated
- **THEN** the system displays the file path(s) used

#### Scenario: Multiple source citations
- **WHEN** an answer uses content from multiple markdown files
- **THEN** the system lists all unique file paths used

### Requirement: WebSocket Communication
The system SHALL provide WebSocket-based communication between server and clients.

#### Scenario: Client connects to server
- **WHEN** a client connects to the WebSocket server
- **THEN** the server accepts the connection
- **AND** sends a status message indicating server readiness
- **AND** maintains the connection for query messages

#### Scenario: Query message format
- **WHEN** a client sends a query
- **THEN** the client sends a JSON message: `{"type": "query", "question": "..."}`
- **AND** optionally specifies index name: `{"type": "query", "question": "...", "index": "name"}`
- **AND** server validates the message format

#### Scenario: Response format with sources
- **WHEN** the server processes a query
- **THEN** the server responds with JSON: `{"type": "response", "answer": "...", "sources": [...]}`
- **AND** sources contain file paths only
- **AND** client displays the answer and sources

#### Scenario: Error handling
- **WHEN** an error occurs during query processing
- **THEN** the server sends an error message: `{"type": "error", "message": "..."}`
- **AND** the connection remains open for subsequent queries

### Requirement: Command-Line Client Interface
The system SHALL provide a CLI client that connects to the server for asking questions.

#### Scenario: Connect to server
- **WHEN** user runs the CLI client
- **THEN** the client connects to WebSocket server (default: `ws://localhost:8765`)
- **AND** displays connection status
- **AND** allows specifying custom server address via `--server` flag

#### Scenario: Send query via CLI
- **WHEN** user provides a question as CLI argument
- **THEN** the client sends query message to server via WebSocket
- **AND** waits for response
- **AND** displays answer with source citations
- **AND** exits after displaying response

#### Scenario: Interactive question mode
- **WHEN** user runs the CLI in interactive mode
- **THEN** the client connects to server and maintains connection
- **AND** prompts for questions repeatedly
- **AND** sends each question to server via WebSocket
- **AND** displays answers with source citations
- **AND** continues until user exits (Ctrl+C or "quit")

#### Scenario: Handle server unavailable
- **WHEN** the server is not running or unreachable
- **THEN** the client reports connection error
- **AND** suggests starting the server
- **AND** exits with error code
