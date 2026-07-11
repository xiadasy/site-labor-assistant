CREATE TABLE IF NOT EXISTS state (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  action TEXT NOT NULL,
  summary TEXT,
  user_agent TEXT,
  ip TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);

CREATE TABLE IF NOT EXISTS cert_files (
  key TEXT PRIMARY KEY,
  content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
  size INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cert_file_chunks (
  key TEXT NOT NULL,
  idx INTEGER NOT NULL,
  body_base64 TEXT NOT NULL,
  PRIMARY KEY (key, idx)
);

CREATE INDEX IF NOT EXISTS idx_cert_chunks_key ON cert_file_chunks(key);
