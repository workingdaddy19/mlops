-- ============================================================
-- mlfoundry 로컬 개발 초기 스키마
-- Docker MySQL 8.0 초기화 시 자동 실행
-- ============================================================

SET NAMES utf8mb4;
SET time_zone = '+09:00';

USE mlfoundry;

-- ──────────────────────────────────────────────
-- 1. users
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id          BIGINT       AUTO_INCREMENT PRIMARY KEY,
    user_id     VARCHAR(100) NOT NULL UNIQUE,
    password    VARCHAR(255),
    name        VARCHAR(100),
    email       VARCHAR(200),
    dept_code   VARCHAR(50),
    dept_name   VARCHAR(100),
    emp_no      VARCHAR(50),
    role        VARCHAR(20)  NOT NULL DEFAULT 'USER',
    sso_id      VARCHAR(200),
    auth_type   INT          NOT NULL DEFAULT 1,
    enabled     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 로컬 개발용 기본 계정 (password: admin)
INSERT IGNORE INTO users (user_id, password, name, role, auth_type, enabled)
VALUES ('admin', '$2a$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', '관리자', 'ADMIN', 1, TRUE);

-- ──────────────────────────────────────────────
-- 2. board
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS board (
    id          BIGINT       AUTO_INCREMENT PRIMARY KEY,
    board_type  VARCHAR(50)  NOT NULL,
    title       VARCHAR(500) NOT NULL,
    content     LONGTEXT,
    author_id   VARCHAR(100),
    view_count  INT          NOT NULL DEFAULT 0,
    is_deleted  BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ──────────────────────────────────────────────
-- 3. datasets
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS datasets (
    id            BIGINT       AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(200) NOT NULL,
    version       VARCHAR(50),
    description   TEXT,
    source_type   VARCHAR(50),
    source_uri    VARCHAR(500),
    row_count     BIGINT,
    column_count  INT,
    tags          TEXT,
    owner         VARCHAR(100),
    quality_score DECIMAL(5,2),
    created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dataset_features (
    id          BIGINT       AUTO_INCREMENT PRIMARY KEY,
    dataset_id  BIGINT       NOT NULL,
    name        VARCHAR(200) NOT NULL,
    dtype       VARCHAR(50),
    description TEXT,
    stats       TEXT,
    is_target   BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ──────────────────────────────────────────────
-- 4. data_query_history
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS data_query_history (
    id           BIGINT       AUTO_INCREMENT PRIMARY KEY,
    user_id      VARCHAR(100) NOT NULL,
    query_sql    TEXT,
    nl_query     TEXT,
    status       VARCHAR(20)  NOT NULL DEFAULT 'RUNNING',
    row_count    INT          NOT NULL DEFAULT 0,
    exec_ms      BIGINT       NOT NULL DEFAULT 0,
    error_msg    TEXT,
    executed_at  DATETIME     DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ──────────────────────────────────────────────
-- 5. s3_download_log
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS s3_download_log (
    id              BIGINT       AUTO_INCREMENT PRIMARY KEY,
    user_id         VARCHAR(100) NOT NULL,
    file_key        VARCHAR(500),
    file_name       VARCHAR(300),
    download_reason TEXT,
    drm_applied     BOOLEAN      NOT NULL DEFAULT FALSE,
    client_ip       VARCHAR(50),
    downloaded_at   DATETIME     DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ──────────────────────────────────────────────
-- 6. schema_context (Text2SQL 용)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schema_context (
    id          BIGINT       AUTO_INCREMENT PRIMARY KEY,
    db_name     VARCHAR(50)  NOT NULL,
    table_name  VARCHAR(200) NOT NULL,
    ddl_text    TEXT,
    description TEXT,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_db_table (db_name, table_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
