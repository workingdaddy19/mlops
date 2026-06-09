1. DB 접속 정보 설정 위치
application.yaml:7-11을 직접 수정하세요:


spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/mlfoundry   # ← DB 호스트/포트/DB명
    username: postgres                                 # ← DB 계정
    password: postgres                                 # ← DB 비밀번호
환경변수로도 주입 가능 (${DB_HOST:localhost} 형식이므로):


export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=mlfoundry
export DB_USER=postgres
export DB_PASSWORD=your_password
2. DB 및 테이블 생성 순서
Step 1 — DB 생성 (init.sql)


psql -U postgres -f src/main/resources/db/init.sql
Step 2 — 테이블 생성 (schema.sql)


psql -U postgres -d mlfoundry -f src/main/resources/db/schema.sql
3. 생성되는 테이블 목록
테이블	설명
users	사용자 계정 (admin 자동 삽입)
board	공지/자료 게시판
board_file	게시판 첨부파일
datasets	데이터셋 메타데이터
dataset_features	데이터셋 컬럼 정보
data_query_history	SQL 실행 이력
s3_download_log	S3 다운로드 로그
schema_context	Text2SQL 스키마 정보
master_resource	동적 설정값
4. 초기 admin 계정
schema.sql 실행 시 자동 생성됩니다:

ID: admin
PW: admin (BCrypt 암호화 저장)
AppConfig의 CommandLineRunner도 시작 시 admin1234로 업데이트하므로 최종 비밀번호는 admin1234 입니다.