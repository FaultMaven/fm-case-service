-- SQLite-compatible 10-table hybrid schema for fm-case-service
-- Converted from PostgreSQL schema (001_initial_hybrid_schema.sql)
-- Date: 2025-12-08

-- ============================================================================
-- TABLE: cases
-- ============================================================================

CREATE TABLE IF NOT EXISTS cases (
    -- Primary Key
    case_id VARCHAR(17) PRIMARY KEY,

    -- Core Attributes
    user_id VARCHAR(255) NOT NULL,
    organization_id VARCHAR(255) NOT NULL,
    title VARCHAR(200) NOT NULL,
    status TEXT NOT NULL DEFAULT 'consulting' CHECK(status IN ('consulting', 'investigating', 'resolved', 'closed')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP,
    resolved_at TIMESTAMP,
    closed_at TIMESTAMP,

    -- JSONB columns (stored as TEXT in SQLite)
    consulting TEXT NOT NULL DEFAULT '{"initial_description": "", "context": {}, "user_goals": []}',
    problem_verification TEXT,
    working_conclusion TEXT,
    root_cause_conclusion TEXT,
    path_selection TEXT,
    degraded_mode TEXT,
    escalation_state TEXT,
    documentation TEXT NOT NULL DEFAULT '{"summary": "", "timeline": [], "lessons_learned": []}',
    progress TEXT NOT NULL DEFAULT '{"current_phase": "consulting", "completion_percentage": 0, "milestones": []}',
    metadata TEXT NOT NULL DEFAULT '{}',

    -- Turn Tracking
    current_turn INTEGER NOT NULL DEFAULT 0,
    turns_without_progress INTEGER NOT NULL DEFAULT 0,

    -- Constraints
    CHECK(LENGTH(TRIM(title)) > 0),
    CHECK(LENGTH(TRIM(user_id)) > 0),
    CHECK(LENGTH(TRIM(organization_id)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_cases_user_id ON cases(user_id);
CREATE INDEX IF NOT EXISTS idx_cases_organization_id ON cases(organization_id);
CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_created_at ON cases(created_at);
CREATE INDEX IF NOT EXISTS idx_cases_updated_at ON cases(updated_at);

-- ============================================================================
-- TABLE: evidence
-- ============================================================================

CREATE TABLE IF NOT EXISTS evidence (
    -- Primary Key
    evidence_id VARCHAR(15) PRIMARY KEY,

    -- Foreign Key
    case_id VARCHAR(17) NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,

    -- Core Attributes
    category TEXT NOT NULL CHECK(category IN ('LOGS_AND_ERRORS', 'STRUCTURED_CONFIG', 'METRICS_AND_PERFORMANCE', 'UNSTRUCTURED_TEXT', 'SOURCE_CODE', 'VISUAL_EVIDENCE', 'UNKNOWN')),
    summary VARCHAR(500) NOT NULL,
    preprocessed_content TEXT NOT NULL,
    content_ref VARCHAR(1000),

    -- Metadata
    file_size INTEGER,
    filename VARCHAR(255),
    upload_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT NOT NULL DEFAULT '{}',

    -- Constraints
    CHECK(LENGTH(TRIM(summary)) > 0),
    CHECK(LENGTH(TRIM(preprocessed_content)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_evidence_case_id ON evidence(case_id);
CREATE INDEX IF NOT EXISTS idx_evidence_category ON evidence(category);
CREATE INDEX IF NOT EXISTS idx_evidence_upload_timestamp ON evidence(upload_timestamp);

-- ============================================================================
-- TABLE: hypotheses
-- ============================================================================

CREATE TABLE IF NOT EXISTS hypotheses (
    -- Primary Key
    hypothesis_id VARCHAR(15) PRIMARY KEY,

    -- Foreign Key
    case_id VARCHAR(17) NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,

    -- Core Attributes
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed' CHECK(status IN ('proposed', 'testing', 'validated', 'invalidated', 'deferred')),
    confidence_score REAL,

    -- Supporting Evidence (stored as JSON TEXT in SQLite)
    supporting_evidence_ids TEXT,

    -- Validation
    validation_result TEXT,
    validation_timestamp TIMESTAMP,

    -- Timeline
    proposed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Metadata
    metadata TEXT NOT NULL DEFAULT '{}',

    -- Constraints
    CHECK(LENGTH(TRIM(description)) > 0),
    CHECK(confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1))
);

CREATE INDEX IF NOT EXISTS idx_hypotheses_case_id ON hypotheses(case_id);
CREATE INDEX IF NOT EXISTS idx_hypotheses_status ON hypotheses(status);
CREATE INDEX IF NOT EXISTS idx_hypotheses_proposed_at ON hypotheses(proposed_at);
CREATE INDEX IF NOT EXISTS idx_hypotheses_confidence_score ON hypotheses(confidence_score);

-- ============================================================================
-- TABLE: solutions
-- ============================================================================

CREATE TABLE IF NOT EXISTS solutions (
    -- Primary Key
    solution_id VARCHAR(15) PRIMARY KEY,

    -- Foreign Key
    case_id VARCHAR(17) NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,

    -- Core Attributes
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed' CHECK(status IN ('proposed', 'in_progress', 'implemented', 'verified', 'rejected')),
    implementation_steps TEXT,  -- JSON array stored as TEXT

    -- Risk Assessment
    risk_level VARCHAR(20) CHECK(risk_level IS NULL OR risk_level IN ('low', 'medium', 'high', 'critical')),
    estimated_effort VARCHAR(50),

    -- Validation
    verification_result TEXT,
    verification_timestamp TIMESTAMP,

    -- Timeline
    proposed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    implemented_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Metadata
    metadata TEXT NOT NULL DEFAULT '{}',

    -- Constraints
    CHECK(LENGTH(TRIM(description)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_solutions_case_id ON solutions(case_id);
CREATE INDEX IF NOT EXISTS idx_solutions_status ON solutions(status);
CREATE INDEX IF NOT EXISTS idx_solutions_proposed_at ON solutions(proposed_at);
CREATE INDEX IF NOT EXISTS idx_solutions_risk_level ON solutions(risk_level);

-- ============================================================================
-- TABLE: case_messages
-- ============================================================================

CREATE TABLE IF NOT EXISTS case_messages (
    -- Primary Key
    message_id VARCHAR(20) PRIMARY KEY,

    -- Foreign Key
    case_id VARCHAR(17) NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,

    -- Core Attributes
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,

    -- Timeline
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Metadata
    metadata TEXT NOT NULL DEFAULT '{}',

    -- Constraints
    CHECK(LENGTH(TRIM(content)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_case_messages_case_id ON case_messages(case_id);
CREATE INDEX IF NOT EXISTS idx_case_messages_timestamp ON case_messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_case_messages_role ON case_messages(role);

-- ============================================================================
-- TABLE: uploaded_files
-- ============================================================================

CREATE TABLE IF NOT EXISTS uploaded_files (
    -- Primary Key
    file_id VARCHAR(15) PRIMARY KEY,

    -- Foreign Key
    case_id VARCHAR(17) NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,

    -- Core Attributes
    filename VARCHAR(255) NOT NULL,
    file_size INTEGER NOT NULL,
    content_type VARCHAR(100),
    storage_path VARCHAR(1000),

    -- Processing
    processing_status TEXT NOT NULL DEFAULT 'pending' CHECK(processing_status IN ('pending', 'processing', 'completed', 'failed')),
    processing_error TEXT,

    -- Timeline
    uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,

    -- Metadata
    metadata TEXT NOT NULL DEFAULT '{}',

    -- Constraints
    CHECK(LENGTH(TRIM(filename)) > 0),
    CHECK(file_size > 0)
);

CREATE INDEX IF NOT EXISTS idx_uploaded_files_case_id ON uploaded_files(case_id);
CREATE INDEX IF NOT EXISTS idx_uploaded_files_uploaded_at ON uploaded_files(uploaded_at);
CREATE INDEX IF NOT EXISTS idx_uploaded_files_processing_status ON uploaded_files(processing_status);

-- ============================================================================
-- TABLE: case_status_transitions
-- ============================================================================

CREATE TABLE IF NOT EXISTS case_status_transitions (
    -- Primary Key
    transition_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Foreign Key
    case_id VARCHAR(17) NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,

    -- Core Attributes
    from_status TEXT CHECK(from_status IS NULL OR from_status IN ('consulting', 'investigating', 'resolved', 'closed')),
    to_status TEXT NOT NULL CHECK(to_status IN ('consulting', 'investigating', 'resolved', 'closed')),
    reason TEXT,

    -- Timeline
    transitioned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Metadata
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_case_status_transitions_case_id ON case_status_transitions(case_id);
CREATE INDEX IF NOT EXISTS idx_case_status_transitions_timestamp ON case_status_transitions(transitioned_at);

-- ============================================================================
-- TABLE: case_tags
-- ============================================================================

CREATE TABLE IF NOT EXISTS case_tags (
    -- Primary Key
    tag_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Foreign Key
    case_id VARCHAR(17) NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,

    -- Core Attributes
    tag VARCHAR(50) NOT NULL,

    -- Timeline
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    UNIQUE(case_id, tag),
    CHECK(LENGTH(TRIM(tag)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_case_tags_case_id ON case_tags(case_id);
CREATE INDEX IF NOT EXISTS idx_case_tags_tag ON case_tags(tag);

-- ============================================================================
-- TABLE: agent_tool_calls
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_tool_calls (
    -- Primary Key
    call_id VARCHAR(20) PRIMARY KEY,

    -- Foreign Key
    case_id VARCHAR(17) NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,

    -- Core Attributes
    tool_name VARCHAR(100) NOT NULL,
    tool_input TEXT NOT NULL,  -- JSON
    tool_output TEXT,  -- JSON

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'running', 'success', 'error')),
    error_message TEXT,

    -- Performance
    duration_ms INTEGER,

    -- Timeline
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,

    -- Metadata
    metadata TEXT NOT NULL DEFAULT '{}',

    -- Constraints
    CHECK(LENGTH(TRIM(tool_name)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_agent_tool_calls_case_id ON agent_tool_calls(case_id);
CREATE INDEX IF NOT EXISTS idx_agent_tool_calls_tool_name ON agent_tool_calls(tool_name);
CREATE INDEX IF NOT EXISTS idx_agent_tool_calls_status ON agent_tool_calls(status);
CREATE INDEX IF NOT EXISTS idx_agent_tool_calls_started_at ON agent_tool_calls(started_at);

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT 'Schema created successfully. Tables:' AS status;
SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;
