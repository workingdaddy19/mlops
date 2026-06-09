-- ============================================================
-- RDS PostgreSQL 초기화 스크립트 (mlops 사용자용)
-- EC2 또는 Kubernetes Pod에서 mlops 사용자로 실행
-- ============================================================
-- 주의: mlops 사용자는 CREATEROLE 권한이 없으므로,
--       추가 사용자 생성은 불가능합니다.
--       현재 mlops 사용자로만 작업합니다.
-- ============================================================

-- 1. 현재 권한 확인
SELECT current_user, current_database();

-- 2. 생성된 테이블 확인
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
