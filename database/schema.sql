PRAGMA journal_mode  = WAL;
PRAGMA synchronous   = NORMAL;
PRAGMA foreign_keys  = ON;
PRAGMA busy_timeout  = 5000;
PRAGMA temp_store    = MEMORY;

-- ─── SESSION ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS session (
    id          TEXT PRIMARY KEY,
    target      TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',
    vuln_class  TEXT NOT NULL,
    created_at  TEXT NOT NULL
                DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    CHECK (id GLOB 'ses[0-9]*'),
    CHECK (length(trim(target)) > 0),
    CHECK (length(trim(vuln_class)) > 0),
    CHECK (status IN ('active', 'closed'))
);

-- ─── EXCHANGE ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS exchange (
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

    FOREIGN KEY (session_id) REFERENCES session(id) ON DELETE CASCADE,

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

-- ─── EVIDENCE ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS evidence (
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

    FOREIGN KEY (session_id)  REFERENCES session(id)  ON DELETE CASCADE,
    FOREIGN KEY (exchange_id) REFERENCES exchange(id)  ON DELETE SET NULL,

    CHECK (id GLOB 'evi[0-9]*'),
    CHECK (length(trim(observation)) > 0),
    CHECK (confidence >= 0.0 AND confidence <= 1.0)
);

-- ─── HYPOTHESIS (tree via parent_id) ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS hypothesis (
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

    FOREIGN KEY (session_id) REFERENCES session(id)    ON DELETE CASCADE,
    FOREIGN KEY (parent_id)  REFERENCES hypothesis(id)  ON DELETE CASCADE,

    CHECK (id GLOB 'hyp[0-9]*'),
    CHECK (length(trim(claim)) > 0),
    CHECK (status IN (
        'proposed','testing','supported',
        'rejected','inconclusive')),
    CHECK (parent_id IS NULL OR parent_id != id)
);

-- ─── FINDING ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS finding (
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

    FOREIGN KEY (session_id) REFERENCES session(id) ON DELETE CASCADE,

    CHECK (id GLOB 'fin[0-9]*'),
    CHECK (length(trim(title)) > 0),
    CHECK (verified IN (0, 1))
);

-- ─── KNOWLEDGE (long-term) ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledge (
    id             TEXT PRIMARY KEY,
    summary        TEXT NOT NULL,
    indicators     TEXT NOT NULL DEFAULT '[]',
    attack_surface TEXT,
    attack_vector  TEXT,
    vuln_class     TEXT,
    tags           TEXT NOT NULL DEFAULT '[]',
    created_at     TEXT NOT NULL
                   DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    CHECK (id GLOB 'kno[0-9]*'),
    CHECK (length(trim(summary)) > 0),
    CHECK (json_valid(indicators) AND json_type(indicators) = 'array'),
    CHECK (json_valid(tags)       AND json_type(tags)       = 'array')
);

-- ─── JUNCTION ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS hypothesis_evidence (
    hypothesis_id TEXT NOT NULL,
    evidence_id   TEXT NOT NULL,
    created_at    TEXT NOT NULL
                  DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    PRIMARY KEY (hypothesis_id, evidence_id),
    FOREIGN KEY (hypothesis_id) REFERENCES hypothesis(id) ON DELETE CASCADE,
    FOREIGN KEY (evidence_id)   REFERENCES evidence(id)   ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS finding_evidence (
    finding_id  TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    created_at  TEXT NOT NULL
                DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    PRIMARY KEY (finding_id, evidence_id),
    FOREIGN KEY (finding_id)  REFERENCES finding(id)  ON DELETE CASCADE,
    FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE CASCADE
);

-- ─── INDEX ────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_exchange_session
    ON exchange(session_id);
CREATE INDEX IF NOT EXISTS idx_exchange_last_accessed
    ON exchange(last_accessed_at);
CREATE INDEX IF NOT EXISTS idx_exchange_vuln_class
    ON exchange(vuln_class);

CREATE INDEX IF NOT EXISTS idx_evidence_session
    ON evidence(session_id);
CREATE INDEX IF NOT EXISTS idx_evidence_exchange
    ON evidence(exchange_id);
CREATE INDEX IF NOT EXISTS idx_evidence_last_accessed
    ON evidence(last_accessed_at);

CREATE INDEX IF NOT EXISTS idx_hypothesis_session
    ON hypothesis(session_id);
CREATE INDEX IF NOT EXISTS idx_hypothesis_parent
    ON hypothesis(parent_id);
CREATE INDEX IF NOT EXISTS idx_hypothesis_status
    ON hypothesis(status);
CREATE INDEX IF NOT EXISTS idx_hypothesis_last_accessed
    ON hypothesis(last_accessed_at);

CREATE INDEX IF NOT EXISTS idx_finding_session
    ON finding(session_id);
CREATE INDEX IF NOT EXISTS idx_finding_verified
    ON finding(verified);
CREATE INDEX IF NOT EXISTS idx_finding_last_accessed
    ON finding(last_accessed_at);

CREATE INDEX IF NOT EXISTS idx_knowledge_vuln_class
    ON knowledge(vuln_class);

CREATE INDEX IF NOT EXISTS idx_hyp_evi_evidence
    ON hypothesis_evidence(evidence_id);
CREATE INDEX IF NOT EXISTS idx_fin_evi_evidence
    ON finding_evidence(evidence_id);

-- ─── ENFORCE vuln_class = session.vuln_class ────────────────────────────────

CREATE TRIGGER IF NOT EXISTS trg_exchange_vuln_class
BEFORE INSERT ON exchange
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'vuln_class must match session')
    WHERE NEW.vuln_class IS NOT NULL
      AND NEW.vuln_class != (SELECT vuln_class FROM session WHERE id = NEW.session_id);
END;

CREATE TRIGGER IF NOT EXISTS trg_evidence_vuln_class
BEFORE INSERT ON evidence
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'vuln_class must match session')
    WHERE NEW.vuln_class IS NOT NULL
      AND NEW.vuln_class != (SELECT vuln_class FROM session WHERE id = NEW.session_id);
END;

CREATE TRIGGER IF NOT EXISTS trg_hypothesis_vuln_class
BEFORE INSERT ON hypothesis
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'vuln_class must match session')
    WHERE NEW.vuln_class IS NOT NULL
      AND NEW.vuln_class != (SELECT vuln_class FROM session WHERE id = NEW.session_id);
END;

CREATE TRIGGER IF NOT EXISTS trg_finding_vuln_class
BEFORE INSERT ON finding
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'vuln_class must match session')
    WHERE NEW.vuln_class IS NOT NULL
      AND NEW.vuln_class != (SELECT vuln_class FROM session WHERE id = NEW.session_id);
END;