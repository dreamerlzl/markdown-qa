## Context
This system will enable local question-answering over markdown documentation files. It needs to work entirely offline, process multiple markdown files, and provide source citations for answers.

## Goals / Non-Goals

### Goals
- Load markdown files from specified directories
- Answer questions using content from loaded markdown files
- Show source citations (file path and section) for each answer
- Use OpenAI-compatible API for embeddings and chunking
- Support querying across multiple markdown files

### Non-Goals
- Real-time file watching or immediate auto-reloading (only periodic reloads)
- Web interface (CLI client only for initial implementation)
- Support for non-markdown file formats
- Multi-user or concurrent query support (single server instance)

## Decisions

### Decision: Use FAISS for vector storage
- **Rationale**: FAISS is lightweight, fast, and works well for local development. It doesn't require a separate service and can be easily serialized to disk.
- **Alternatives considered**: 
  - Chroma: More features but requires a separate service or embedded database
  - Pinecone: Cloud-based, not suitable for local-only use case

### Decision: Use OpenAI-compatible API for embeddings
- **Rationale**: OpenAI-compatible APIs provide high-quality embeddings and are widely supported. Using an API allows flexibility to use various embedding services (OpenAI, local servers like Ollama, or other compatible providers). Configuration via config file or environment variables allows easy switching between providers.
- **Configuration**:
  - API base URL and API key configured via configuration file or environment variables
  - Default configuration file location: `~/.markdown-qa/config.yaml` or `config.toml`
  - Environment variables: `MARKDOWN_QA_API_BASE_URL` and `MARKDOWN_QA_API_KEY`
  - Config file takes precedence over environment variables
- **Alternatives considered**:
  - Local models (sentence-transformers): Simpler but requires model downloads and local processing
  - Direct OpenAI SDK: Less flexible, tied to specific provider

### Decision: Use LangChain's MarkdownTextSplitter for chunking
- **Rationale**: LangChain's MarkdownTextSplitter provides robust markdown-aware chunking that preserves structure (headers, code blocks, etc.) and supports configurable overlap. Using a well-tested library reduces implementation complexity and maintenance burden.
- **Configuration**:
  - Uses LangChain's `MarkdownTextSplitter` with configurable chunk size and overlap
  - Default chunk size: 1000 characters
  - Default overlap: 200 characters
  - Preserves markdown structure and metadata
- **Alternatives considered**:
  - Custom markdown parser: More control but requires more implementation and testing
  - Fixed-size chunks: Simpler but loses structural context
  - Paragraph-based: May create too many small chunks

### Decision: Store metadata (file path, section headers) with chunks
- **Rationale**: Enables accurate source citations showing both file and section context.
- **Alternatives considered**:
  - File-only citations: Less precise but simpler

### Decision: Centralized index cache storage
- **Rationale**: All indexes stored in a single cache directory (e.g., `~/.markdown-qa/cache/`) for easy management and loading. Multiple directories can be indexed together into one combined index, or separately as named indexes.
- **Storage structure**:
  - Default location: `~/.markdown-qa/cache/`
  - Each index stored as: `{index-name}.faiss` (vectors) and `{index-name}.pkl` (metadata)
  - Manifest file (`indexes.json`) tracks which directories map to which index files
- **Alternatives considered**:
  - Separate cache per directory: More complex to manage, harder to query across directories
  - Single global index: Less flexible, harder to update individual directories

### Decision: Server-based architecture with WebSocket
- **Rationale**: Long-running server keeps indexes in memory, eliminating per-query disk I/O. WebSocket provides efficient bidirectional communication for queries and responses. Periodic reloads (every 5 minutes) keep indexes fresh without requiring immediate file watching.
- **Architecture**:
  - Server process runs continuously, maintains indexes in memory
  - WebSocket server listens on configurable port (default: 8765)
  - CLI client connects to server via WebSocket
  - Indexes reloaded periodically (every 5 minutes) in background
  - Indexes persisted to disk for server restarts
- **Alternatives considered**:
  - HTTP REST API: More overhead, stateless but requires per-request index loading
  - gRPC: More complex, better for high-throughput but overkill for this use case
  - File watching: Immediate updates but adds complexity and system dependencies
  - CLI-only with disk caching: Simpler but requires disk I/O on every query

## Risks / Trade-offs

- **Risk**: Large markdown files may slow down indexing
  - **Mitigation**: Implement chunking limits and progress indicators

- **Risk**: API availability and rate limits may affect indexing
  - **Mitigation**: 
    - Implement retry logic with exponential backoff
    - Cache embeddings to avoid redundant API calls
    - Provide clear error messages for API failures
    - Support configuration for rate limit handling

- **Risk**: Large indexes (hundreds of files) consume memory and take time to build
  - **Mitigation**: 
    - Server loads indexes once at startup, then keeps in memory
    - Memory usage is predictable (indexes stay loaded)
    - Consider splitting very large document sets into multiple named indexes
    - Provide progress indicators during index building for transparency
- **Risk**: Server process must run continuously
  - **Mitigation**: Server can be run as a systemd service or background daemon
  - **Trade-off**: Requires long-running process but eliminates per-query overhead

- **Trade-off**: Requires API access and network connectivity for indexing
  - **Acceptance**: Acceptable trade-off for higher quality embeddings and flexibility
  - **Note**: Once indexed, queries can work offline (indexes stored locally)

## Migration Plan
N/A - This is a new capability with no existing system to migrate from.

## Performance Considerations

### Server-Based Architecture Benefits
- **Zero per-query loading time**: Indexes stay in memory, eliminating disk I/O on every query
- **Fast query response**: Queries use in-memory indexes directly (< 1 second for search, 1-2 seconds total with LLM)
- **Background reload**: Periodic reloads (every 5 minutes) happen in background without blocking queries
- **Memory efficiency**: Only one copy of indexes in memory, shared across all client connections

### Index Management Strategy
- **In-memory storage**: Indexes loaded into memory at server startup and kept there
- **Periodic reload**: Background task rebuilds indexes every 5 minutes from configured directories
- **Atomic updates**: New indexes built in background, swapped atomically when ready (queries continue using old index during rebuild)
- **Disk persistence**: Indexes saved to `~/.markdown-qa/cache/` for server restarts
- **Startup behavior**: Server loads indexes from disk cache if available, otherwise builds from scratch
- **No file watching**: Changes detected only through periodic reloads (not immediate, but simpler and more reliable)

### Index Caching Strategy
- **Centralized storage**: All indexes stored in `~/.markdown-qa/cache/` directory
- **Index naming**: 
  - Default index: `default.faiss` / `default.pkl`
  - Named indexes: `{name}.faiss` / `{name}.pkl` (via configuration)
  - Multiple directories can be combined into one index
- **Manifest tracking**: `indexes.json` maps directory paths to index files and tracks file checksums
- **Server restart**: Loads indexes from disk cache, avoiding full rebuild if cache exists

### Expected Performance

**Server Startup (one-time):**
- **Small indexes (< 50 files, ~1,000 chunks):**
  - Index creation/loading: 30-60 seconds (includes API calls for embeddings)
  - Memory usage: ~50-100 MB
- **Medium indexes (50-200 files, ~5,000 chunks):**
  - Index creation/loading: 2-5 minutes (depends on API rate limits)
  - Memory usage: ~150-300 MB
- **Large indexes (200+ files, 10,000+ chunks):**
  - Index creation/loading: 5-15 minutes (depends on API rate limits and network)
  - Memory usage: ~300-800 MB
- **Note**: Index creation time depends on API response time and rate limits. Once cached, reloads are faster if using cached embeddings.

**Query Performance (after startup, indexes in memory):**
- **All index sizes**: 
  - Query response: < 2 seconds (search: < 0.1s, LLM generation: 1-2s)
  - No disk I/O during queries
  - Consistent performance regardless of index size

**Periodic Reload (every 5 minutes, background):**
- Reload time same as initial creation
- Queries continue using old index during reload
- New index swapped atomically when ready
- No query blocking during reload

**Note**: With indexes in memory, query performance is consistent and fast regardless of index size. The only variable is LLM generation time, which is independent of index size.

## Open Questions
- What is the maximum number of markdown files to support?
- Should chunk size be configurable?
- Should we track file checksums or modification times for change detection?
