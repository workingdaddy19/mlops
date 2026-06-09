-- Service Token Management Table
-- 사용자별 Jupyter/MLflow 서비스 토큰 관리 테이블

CREATE TABLE IF NOT EXISTS user_service_tokens (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL,
  service VARCHAR(50) NOT NULL,
  token VARCHAR(500) NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT uk_user_service UNIQUE(user_id, service)
);

-- 성능 인덱스
CREATE INDEX IF NOT EXISTS idx_user_service ON user_service_tokens(user_id, service);
CREATE INDEX IF NOT EXISTS idx_service ON user_service_tokens(service);

-- 로그 메시지
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_service_tokens') THEN
    RAISE NOTICE 'user_service_tokens table created successfully';
  ELSE
    RAISE NOTICE 'user_service_tokens table already exists';
  END IF;
END $$;
