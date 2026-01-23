## Context
The current indexing system performs full rebuilds on every periodic reload, even when only one file has changed. This is wasteful for large document sets and causes unnecessary API calls for embedding generation.

## Goals / Non-Goals

### Goals
- Reduce index rebuild time when only a few files change
- Reduce embedding API calls by only processing changed content
- Maintain atomic index updates (queries never see partial state)
- Preserve backward compatibility with existing index cache format

### Non-Goals
- Real-time file watching (still using periodic polling)
- Partial chunk updates within a file (if file changes, all its chunks are replaced)
- Concurrent index modifications (single-threaded updates)

## Decisions

### Decision: Use FAISS IDMap2 wrapper for ID-based removal
- **Rationale**: FAISS `IndexFlatL2` doesn't support removal. Wrapping with `IndexIDMap2` enables `remove_ids()` for removing specific vectors by ID.
- **Trade-off**: Slight memory overhead for ID mapping, but enables O(1) removal.
- **Alternatives considered**:
  - Rebuild entire index: Current approach, wasteful
  - Mark-as-deleted with periodic compaction: More complex, eventual consistency issues

### Decision: Assign stable chunk IDs based on file path + chunk index
- **Rationale**: Each chunk gets a deterministic ID derived from its source file and position. This allows identifying which chunks to remove when a file changes.
- **ID format**: `hash(file_path)[:8] + chunk_index` as 64-bit integer
- **Alternatives considered**:
  - Content-based IDs: Would require re-hashing unchanged files
  - Sequential IDs: Would require tracking ID ranges per file

### Decision: Store per-file metadata in manifest
- **Rationale**: Track file path → {mtime, chunk_ids[]} to detect changes and know which chunks to remove.
- **Storage**: Extend existing `indexes.json` manifest with per-file tracking.
- **Alternatives considered**:
  - Separate tracking file: More files to manage
  - In-memory only: Lost on restart

### Decision: Atomic swap after incremental build
- **Rationale**: Build the updated index in a temporary structure, then swap atomically. Queries continue using the old index during the update.
- **Implementation**: 
  1. Clone current index to working copy
  2. Remove chunks for deleted/modified files
  3. Add new chunks for added/modified files  
  4. Atomically swap the index reference
- **Alternatives considered**:
  - In-place modification: Risk of inconsistent state during updates

## Data Structures

### Extended Manifest Schema
```python
{
  "indexes": {
    "default": {
      "directories": ["/path/to/docs"],
      "checksum": "abc123...",  # overall checksum (existing)
      "files": {  # NEW: per-file tracking
        "/path/to/docs/intro.md": {
          "mtime": 1234567890.123,
          "chunk_ids": [100001, 100002, 100003]
        },
        "/path/to/docs/guide.md": {
          "mtime": 1234567891.456,
          "chunk_ids": [200001, 200002]
        }
      }
    }
  }
}
```

### Chunk ID Generation
```python
def generate_chunk_id(file_path: str, chunk_index: int) -> int:
    """Generate stable 64-bit ID for a chunk."""
    file_hash = hashlib.sha256(file_path.encode()).hexdigest()[:8]
    file_prefix = int(file_hash, 16) << 16  # Upper bits from file
    return file_prefix | (chunk_index & 0xFFFF)  # Lower bits from index
```

## Incremental Update Algorithm

```
1. Load current manifest with per-file metadata
2. Scan directories for current markdown files
3. Compute file changes:
   - deleted = manifest_files - current_files
   - added = current_files - manifest_files
   - modified = {f for f in both if mtime_changed(f)}
4. For deleted files:
   - Get chunk_ids from manifest
   - Remove from FAISS index via remove_ids()
   - Remove from metadata/texts arrays
5. For added/modified files:
   - If modified: first remove old chunks (as above)
   - Load and chunk the file
   - Generate embeddings (uses content-hash cache)
   - Assign chunk IDs
   - Add to FAISS index with IDs
   - Add to metadata/texts arrays
6. Update manifest with new file metadata
7. Atomically swap to updated index
8. Save updated manifest and index to disk
```

## Risks / Trade-offs

- **Risk**: FAISS ID mapping adds memory overhead
  - **Mitigation**: ~8 bytes per vector, negligible for typical index sizes
  
- **Risk**: Manifest corruption could cause orphaned chunks
  - **Mitigation**: Periodic full rebuild option (`force=True`) to reset state
  
- **Risk**: Chunk ID collisions for very large indexes
  - **Mitigation**: 64-bit IDs support billions of unique chunks; collision extremely unlikely

- **Trade-off**: More complex code path than full rebuild
  - **Acceptance**: Worth it for significant performance improvement on large indexes

## Migration Plan

### Backward Compatibility
- Existing indexes without per-file metadata will trigger full rebuild on first incremental attempt
- Manifest format is extended, not changed (new `files` field is optional)
- No breaking changes to external interfaces

### Migration Steps
1. Deploy new code
2. On first periodic reload, system detects missing per-file metadata
3. Performs full rebuild and populates per-file metadata
4. Subsequent reloads use incremental updates

## Open Questions
- Should we add a CLI flag to force full rebuild? (Recommended: yes, `--force-rebuild`)

## Resolved Decisions
- **Change detection uses mtime only**: We use file modification time (mtime) for change detection. This may cause false positives (e.g., `vim :w` without changes updates mtime), but this is acceptable because:
  1. Embedding cache already uses content hash, so redundant API calls are avoided
  2. Only re-chunking cost is paid, which is fast
  3. Simpler implementation without needing to read file contents for change detection
