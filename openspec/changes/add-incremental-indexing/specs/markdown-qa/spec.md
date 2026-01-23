## MODIFIED Requirements

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

#### Scenario: Assign stable chunk identifiers
- **WHEN** chunks are created from a markdown file
- **THEN** each chunk receives a stable identifier derived from its file path and position
- **AND** the identifier remains consistent across index rebuilds for unchanged files
- **AND** identifiers enable removal of specific chunks when files are deleted or modified

#### Scenario: Track per-file metadata in manifest
- **WHEN** an index is created or updated
- **THEN** the manifest tracks metadata for each indexed file
- **AND** metadata includes file modification time (mtime) and list of chunk identifiers
- **AND** files with changed mtime are considered modified and re-indexed
- **AND** metadata enables detection of which specific files have changed

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

#### Scenario: Periodic index reload with incremental updates
- **WHEN** the server is running
- **THEN** the server checks for file changes every 5 minutes
- **AND** detects which files were added, modified, or deleted since last reload
- **AND** removes chunks only for deleted or modified files
- **AND** generates embeddings only for new or modified files
- **AND** updates the index incrementally without rebuilding unchanged content
- **AND** continues serving queries using the current index during reload
- **AND** atomically swaps to the updated index when ready
- **AND** saves updated index and manifest to disk cache
- **AND** falls back to full rebuild if incremental update is not possible

#### Scenario: Handle queries without disk I/O
- **WHEN** a query is received
- **THEN** the server uses in-memory indexes directly
- **AND** does not perform any disk I/O during query processing
- **AND** responds quickly (< 2 seconds total)
