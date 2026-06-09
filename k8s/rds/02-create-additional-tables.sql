-- ============================================================
-- RDS PostgreSQL 추가 테이블 생성 스크립트
-- schema_context 테이블 (Text2SQL 용)
-- ============================================================

-- 1. schema_context 테이블 생성 (Text2SQL 용 메타데이터)
CREATE TABLE IF NOT EXISTS schema_context (
    id SERIAL PRIMARY KEY,
    db_name VARCHAR(50) NOT NULL,
    table_name VARCHAR(200) NOT NULL,
    ddl_text TEXT,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(db_name, table_name)
);

-- 2. 기본 스키마 메타정보 추가 (LLM 연동용)
INSERT INTO schema_context (db_name, table_name, ddl_text, description, is_active)
VALUES
    ('mlops', 'users', 'SELECT * FROM users;', '사용자 정보 테이블', TRUE),
    ('mlops', 'datasets', 'SELECT * FROM datasets;', '데이터셋 메타정보', TRUE),
    ('mlops', 'dataset_features', 'SELECT * FROM dataset_features;', '데이터셋 컬럼 정의', TRUE),
    ('mlops', 'board', 'SELECT * FROM board;', '게시판', TRUE),
    ('mlops', 'data_query_history', 'SELECT * FROM data_query_history;', 'SQL 쿼리 이력', TRUE)
ON CONFLICT (db_name, table_name) DO NOTHING;
