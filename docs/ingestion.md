# Ingestion boundaries

Uploads accept PDF and supported image extensions, matching content types, and
matching file signatures. `UPLOAD_MAX_BYTES` defaults to 20 MiB per file and
`UPLOAD_MAX_FILES` defaults to three per request. Total upload request bodies are
bounded at 64 MiB, including chunked uploads. Extraction occurs in a separate
process with `EXTRACT_TIMEOUT` (120 seconds), a CPU limit, and a Linux address-space
limit. Timeout kills the extraction process group, including OCR children. The
extractor can return at most 10 MiB of chunk JSON. Documents stay in temporary or
workspace job storage; original filenames are labels, never destination paths.

Set `SCANNER_COMMAND` to a JSON argv list for a scanner, e.g.
`["clamscan","--no-summary"]`. The file path is appended without a shell. Nonzero
exit status or scanner timeout rejects the upload. Antivirus is an operator-supplied
hook, not an included malware database. Run containers without root and publish
only the authenticated API; operator CLI/Streamlit paths are outside the HTTP boundary.

Web GET allows only HTTP(S) on ports 80/443. Every DNS answer must be globally
routable; private, loopback, link-local, multicast and reserved destinations are
rejected. The socket connects directly to the validated IP while preserving the
original TLS hostname and certificate checks, preventing DNS rebinding. Each
redirect is separately validated. Downloads accept only text/HTML, request identity
encoding, reject compressed responses, cap bytes at 2 MB, and enforce a deadline
between bounded reads. No proxy environment variables or URL credentials are used.

All model input receives a system-level rule that retrieved material is untrusted
evidence and cannot override instructions or authorize tools. Prompt-injection
resistance is a defense in depth, not a guarantee that a local model will obey.
Workspace-scoped tools and restricted network fetching limit the available actions.

Failed jobs can be retried. Deterministic chunk IDs skip previously completed
embeddings; all batches are embedded before vector writes start. Partially completed
vector writes can therefore be replayed safely. Source labels and document content
must not be included in operational logs.
