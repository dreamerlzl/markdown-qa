## 1. Tests First (TDD)

- [x] 1.1 Write unit tests for file change detection (added/modified/deleted scenarios)
- [x] 1.3 Write unit tests for manifest per-file metadata storage
- [x] 1.4 Write integration tests for incremental update (add file, modify file, delete file)
- [x] 1.5 Write test for fallback to full rebuild when manifest lacks per-file data

## 2. Infrastructure Changes

- [x] 2.1 Extend manifest schema to include per-file metadata (mtime, chunk_ids)
- [x] 2.2 Add chunk ID generation utility function (file_path + chunk_index → stable 64-bit ID)
- [x] 2.3 Update VectorStore to use FAISS IndexIDMap2 wrapper for ID-based operations

## 3. Core Implementation

- [x] 3.1 Add `get_file_mtimes()` to loader.py for per-file mtime retrieval
- [x] 3.2 Add `detect_file_changes()` to manifest.py (returns added/modified/deleted sets)
- [x] 3.3 Implement `remove_chunks()` in VectorStore to remove vectors by ID list
- [x] 3.4 Implement `add_chunks_with_ids()` in VectorStore to add vectors with explicit IDs
- [x] 3.5 Implement `incremental_update()` in IndexManager orchestrating the update flow

## 4. Integration

- [x] 4.1 Update `_reload_indexes()` in server.py to use incremental update when possible
- [x] 4.2 Add fallback to full rebuild if incremental update fails or manifest is missing per-file data
- [x] 4.3 Update manifest save/load to persist per-file metadata

## 5. Documentation

- [ ] 5.1 Update design.md with final implementation details
- [ ] 5.2 Add logging for incremental update operations (files changed, chunks added/removed)
