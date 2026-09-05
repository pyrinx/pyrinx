PRAGMA journal_mode  = WAL;
PRAGMA synchronous   = NORMAL;
PRAGMA foreign_keys  = ON;
PRAGMA busy_timeout  = 5000;
PRAGMA temp_store    = MEMORY;

-- ─── SESSIONS ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sessions (
    id               TEXT PRIMARY KEY,
    target           TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'active',
    vuln_class       TEXT NOT NULL,
    created_at       TEXT NOT NULL
                     DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_accessed_at TEXT NOT NULL
                     DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    CHECK (id GLOB 'ses[0-9]*'),
    CHECK (length(trim(target)) > 0),
    CHECK (length(trim(vuln_class)) > 0),
    CHECK (status IN ('active', 'closed'))
);

-- ─── EXCHANGES ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS exchanges (
    id               TEXT PRIMARY KEY,
    session_id       TEXT NOT NULL,
    url              TEXT NOT NULL,
    method           TEXT NOT NULL,
    status_code      INTEGER NOT NULL,
    request_headers  TEXT NOT NULL DEFAULT '{}',
    response_headers TEXT NOT NULL DEFAULT '{}',
    request_body     TEXT,
    response_body    TEXT,
    response_time    TEXT,
    vuln_class       TEXT,
    created_at       TEXT NOT NULL
                     DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_accessed_at TEXT NOT NULL
                     DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,

    CHECK (id GLOB 'exc[0-9]*'),
    CHECK (length(trim(url)) > 0),
    CHECK (method IN (
        'GET','POST','PUT','PATCH','DELETE',
        'HEAD','OPTIONS','TRACE','CONNECT')),
    CHECK (status_code BETWEEN 100 AND 599),
    CHECK (json_valid(request_headers)
           AND json_type(request_headers) = 'object'),
    CHECK (json_valid(response_headers)
           AND json_type(response_headers) = 'object')
);

-- ─── EVIDENCES ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS evidences (
    id               TEXT PRIMARY KEY,
    session_id       TEXT NOT NULL,
    exchange_id      TEXT,
    observation      TEXT NOT NULL,
    observed_value   TEXT,
    confidence       REAL NOT NULL DEFAULT 0.5,
    vuln_class       TEXT,
    created_at       TEXT NOT NULL
                     DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_accessed_at TEXT NOT NULL
                     DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    FOREIGN KEY (session_id)  REFERENCES sessions(id)  ON DELETE CASCADE,
    FOREIGN KEY (exchange_id) REFERENCES exchanges(id)  ON DELETE SET NULL,

    CHECK (id GLOB 'evi[0-9]*'),
    CHECK (length(trim(observation)) > 0),
    CHECK (confidence >= 0.0 AND confidence <= 1.0)
);

-- ─── HYPOTHESES (tree via parent_id) ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS hypotheses (
    id               TEXT PRIMARY KEY,
    session_id       TEXT NOT NULL,
    parent_id        TEXT,
    claim            TEXT NOT NULL,
    rationale        TEXT,
    test             TEXT,
    expected_result  TEXT,
    status           TEXT NOT NULL DEFAULT 'proposed',
    vuln_class       TEXT,
    created_at       TEXT NOT NULL
                     DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at       TEXT NOT NULL
                     DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_accessed_at TEXT NOT NULL
                     DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    FOREIGN KEY (session_id) REFERENCES sessions(id)    ON DELETE CASCADE,
    FOREIGN KEY (parent_id)  REFERENCES hypotheses(id)  ON DELETE CASCADE,

    CHECK (id GLOB 'hyp[0-9]*'),
    CHECK (length(trim(claim)) > 0),
    CHECK (status IN (
        'proposed','testing','supported',
        'rejected','inconclusive')),
    CHECK (parent_id IS NULL OR parent_id != id)
);

-- ─── FINDINGS ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS findings (
    id               TEXT PRIMARY KEY,
    session_id       TEXT NOT NULL,
    title            TEXT NOT NULL,
    detail           TEXT,
    impact           TEXT,
    verified         INTEGER NOT NULL DEFAULT 0,
    vuln_class       TEXT,
    created_at       TEXT NOT NULL
                     DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at       TEXT NOT NULL
                     DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_accessed_at TEXT NOT NULL
                     DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,

    CHECK (id GLOB 'fin[0-9]*'),
    CHECK (length(trim(title)) > 0),
    CHECK (verified IN (0, 1))
);

-- ─── KNOWLEDGES (long-term) ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledges (
    id               TEXT PRIMARY KEY,
    summary          TEXT NOT NULL,
    indicators       TEXT NOT NULL DEFAULT '[]',
    attack_surface   TEXT,
    attack_vector    TEXT,
    vuln_class       TEXT,
    tags             TEXT NOT NULL DEFAULT '[]',
    created_at       TEXT NOT NULL
                     DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_accessed_at TEXT NOT NULL
                     DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    CHECK (id GLOB 'kno[0-9]*'),
    CHECK (length(trim(summary)) > 0),
    CHECK (json_valid(indicators) AND json_type(indicators) = 'array'),
    CHECK (json_valid(tags)       AND json_type(tags)       = 'array')
);

-- ─── JUNCTIONS ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS hypotheses_evidences (
    hypothesis_id TEXT NOT NULL,
    evidence_id   TEXT NOT NULL,
    created_at    TEXT NOT NULL
                  DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    PRIMARY KEY (hypothesis_id, evidence_id),
    FOREIGN KEY (hypothesis_id) REFERENCES hypotheses(id) ON DELETE CASCADE,
    FOREIGN KEY (evidence_id)   REFERENCES evidences(id)   ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS findings_evidences (
    finding_id  TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    created_at  TEXT NOT NULL
                DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    PRIMARY KEY (finding_id, evidence_id),
    FOREIGN KEY (finding_id)  REFERENCES findings(id)  ON DELETE CASCADE,
    FOREIGN KEY (evidence_id) REFERENCES evidences(id) ON DELETE CASCADE
);

-- ─── INDEXES ────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_sessions_last_accessed
    ON sessions(last_accessed_at);

CREATE INDEX IF NOT EXISTS idx_exchanges_session
    ON exchanges(session_id);
CREATE INDEX IF NOT EXISTS idx_exchanges_last_accessed
    ON exchanges(last_accessed_at);
CREATE INDEX IF NOT EXISTS idx_exchanges_vuln_class
    ON exchanges(vuln_class);

CREATE INDEX IF NOT EXISTS idx_evidences_session
    ON evidences(session_id);
CREATE INDEX IF NOT EXISTS idx_evidences_exchange
    ON evidences(exchange_id);
CREATE INDEX IF NOT EXISTS idx_evidences_last_accessed
    ON evidences(last_accessed_at);

CREATE INDEX IF NOT EXISTS idx_hypotheses_session
    ON hypotheses(session_id);
CREATE INDEX IF NOT EXISTS idx_hypotheses_parent
    ON hypotheses(parent_id);
CREATE INDEX IF NOT EXISTS idx_hypotheses_status
    ON hypotheses(status);
CREATE INDEX IF NOT EXISTS idx_hypotheses_last_accessed
    ON hypotheses(last_accessed_at);

CREATE INDEX IF NOT EXISTS idx_findings_session
    ON findings(session_id);
CREATE INDEX IF NOT EXISTS idx_findings_verified
    ON findings(verified);
CREATE INDEX IF NOT EXISTS idx_findings_last_accessed
    ON findings(last_accessed_at);

CREATE INDEX IF NOT EXISTS idx_knowledges_vuln_class
    ON knowledges(vuln_class);
CREATE INDEX IF NOT EXISTS idx_knowledges_last_accessed
    ON knowledges(last_accessed_at);

CREATE INDEX IF NOT EXISTS idx_hyp_evi_evidence
    ON hypotheses_evidences(evidence_id);
CREATE INDEX IF NOT EXISTS idx_fin_evi_evidence
    ON findings_evidences(evidence_id);

-- ─── ENFORCE vuln_class = sessions.vuln_class ────────────────────────────────

CREATE TRIGGER IF NOT EXISTS trg_exchanges_vuln_class
BEFORE INSERT ON exchanges
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'vuln_class must match session')
    WHERE NEW.vuln_class IS NOT NULL
      AND NEW.vuln_class != (SELECT vuln_class FROM sessions WHERE id = NEW.session_id);
END;

CREATE TRIGGER IF NOT EXISTS trg_evidences_vuln_class
BEFORE INSERT ON evidences
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'vuln_class must match session')
    WHERE NEW.vuln_class IS NOT NULL
      AND NEW.vuln_class != (SELECT vuln_class FROM sessions WHERE id = NEW.session_id);
END;

CREATE TRIGGER IF NOT EXISTS trg_hypotheses_vuln_class
BEFORE INSERT ON hypotheses
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'vuln_class must match session')
    WHERE NEW.vuln_class IS NOT NULL
      AND NEW.vuln_class != (SELECT vuln_class FROM sessions WHERE id = NEW.session_id);
END;

CREATE TRIGGER IF NOT EXISTS trg_findings_vuln_class
BEFORE INSERT ON findings
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'vuln_class must match session')
    WHERE NEW.vuln_class IS NOT NULL
      AND NEW.vuln_class != (SELECT vuln_class FROM sessions WHERE id = NEW.session_id);
END;