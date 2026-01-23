# Change: Add Incremental Index Updates

## Why
Currently, when any markdown file changes, the entire index is rebuilt from scratch. This is inefficient for large document sets where only a few files change. For a 200-file index, a single file edit triggers re-chunking and re-embedding of all 200 files, wasting API calls and time.

## What Changes
- Track per-file checksums in the manifest (file path → mtime + chunk IDs)
- On periodic reload, detect which specific files changed/added/deleted
- Only process changed files: remove old chunks, add new chunks
- Use FAISS `remove_ids` and `add` to update the index incrementally
- Reuse existing embeddings for unchanged files (already cached by content hash)

## Impact
- Affected specs: `markdown-qa` (modifies Periodic index reload scenario)
- Affected code:
  - `markdown_qa/manifest.py` - Add per-file checksum tracking
  - `markdown_qa/index_manager.py` - Add incremental update logic
  - `markdown_qa/vector_store.py` - Support incremental add/remove operations
  - `markdown_qa/loader.py` - Add per-file checksum computation
