# 部署指南

本指南提供 AERO Agent 系统的生产部署步骤。

⚠️ **当前状态**: 系统处于Early Beta阶段（45%生产就绪），本指南描述的是**目标架构**。

---

## 快速开始

### 本地开发

```bash
# 1. 克隆仓库
git clone <repository-url>
cd AERO_Agent

# 2. 安装依赖
pip install -e ".[dev,llm]"

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，设置 LLM_API_KEY

# 4. 启动服务
python -m apps.api.main
```

### Docker 部署（规划中）

```bash
# 构建镜像
docker build -t aero-agent:latest .

# 运行容器
docker run -p 8000:8000 \
  -e LLM_API_KEY=your_key \
  -e DATABASE_URL=postgresql://... \
  aero-agent:latest
```

---

## 生产部署架构（目标）

```
┌─────────────────────────────────────────────────────────┐
│                     负载均衡器 (Nginx)                    │
│                    SSL Termination                       │
└─────────────────────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
    ┌───▼───┐       ┌───▼───┐       ┌───▼───┐
    │ API 1 │       │ API 2 │       │ API N │
    │(Docker│       │(Docker│       │(Docker│
    │ 容器) │       │ 容器) │       │ 容器) │
    └───┬───┘       └───┬───┘       └───┬───┘
        │               │               │
        └───────────────┼───────────────┘
                        │
            ┌───────────┴───────────┐
            │                       │
    ┌───────▼────────┐      ┌──────▼──────┐
    │   PostgreSQL   │      │    Redis    │
    │ (会话+报告存储) │      │  (缓存层)   │
    └────────────────┘      └─────────────┘
            │
    ┌───────▼────────┐
    │  Prometheus    │
    │   + Grafana    │
    │  (监控告警)     │
    └────────────────┘
```

---

## 环境配置

### 必需的环境变量

```bash
# LLM 配置
LLM_PROVIDER=zhipu          # 或 openai
LLM_MODEL=glm-4             # 模型名称
LLM_API_KEY=your_api_key    # API 密钥
LLM_BASE_URL=               # 可选：自定义端点

# 数据库配置 (规划中)
DATABASE_URL=postgresql://user:pass@localhost:5432/aero

# Redis 配置 (规划中)
REDIS_URL=redis://localhost:6379/0

# 应用配置
DEBUG=false                 # 生产环境必须为 false
LOG_LEVEL=INFO              # DEBUG, INFO, WARNING, ERROR
API_HOST=0.0.0.0
API_PORT=8000

# 安全配置 (规划中)
API_KEY=secret_key_here
CORS_ORIGINS=https://your-frontend.com

# LangSmith 追踪 (可选)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=aero-agent-prod
LANGCHAIN_API_KEY=your_langsmith_key
```

### 数据文件配置

```bash
# 拓扑数据
TOPOLOGY_FILE_PATH=./scripts/data_processing/topology_clustering_based.json

# 航班数据目录
FLIGHT_DATA_DIR=./data/raw/航班计划

# 输出目录
REPORTS_OUTPUT_DIR=./outputs/reports
```

---

## Docker 配置（目标实现）

### Dockerfile

```dockerfile
FROM python:3.10-slim as builder

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[llm]"

FROM python:3.10-slim

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY . .

ENV PYTHONUNBUFFERED=1
ENV DEBUG=false

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health/liveness || exit 1

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://aero:password@db:5432/aero
      - REDIS_URL=redis://redis:6379/0
      - LLM_API_KEY=${LLM_API_KEY}
      - DEBUG=false
      - LOG_LEVEL=INFO
    depends_on:
      - db
      - redis
    volumes:
      - ./data:/app/data:ro
      - ./outputs:/app/outputs
    restart: unless-stopped

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: aero
      POSTGRES_USER: aero
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
    ports:
      - "3000:3000"
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:
```

---

## 数据库设置（规划中）

### PostgreSQL 表结构

```sql
-- 会话表
CREATE TABLE sessions (
    session_id UUID PRIMARY KEY,
    scenario_type VARCHAR(50) NOT NULL,
    state JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_created_at (created_at)
);

-- 报告表
CREATE TABLE reports (
    id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES sessions(session_id),
    report_type VARCHAR(50),
    content JSONB NOT NULL,
    generated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_session_id (session_id),
    INDEX idx_generated_at (generated_at)
);

-- 审计日志表
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    session_id UUID,
    event_type VARCHAR(100),
    event_data JSONB,
    user_id VARCHAR(100),
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_session_id (session_id),
    INDEX idx_timestamp (timestamp)
);
```

### 迁移脚本

```bash
# 使用 Alembic 管理数据库迁移
pip install alembic

# 初始化
alembic init migrations

# 创建迁移
alembic revision --autogenerate -m "Initial schema"

# 应用迁移
alembic upgrade head
```

---

## 监控配置（规划中）

### Prometheus 配置

```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'aero-agent'
    static_configs:
      - targets: ['api:8000']
```

### Grafana 仪表板

关键指标：
- 请求速率（按端点）
- 响应时间（p50, p95, p99）
- 错误率
- 活动会话数
- 数据库连接池使用率
- LLM API 调用延迟

---

## 日志管理

### 日志格式（规划中）

```python
# JSON 结构化日志
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "logger": "agent.nodes.reasoning",
  "message": "Tool execution completed",
  "session_id": "550e8400-...",
  "tool_name": "assess_risk",
  "duration_ms": 123
}
```

### 日志聚合（规划中）

选项：
1. **ELK Stack** (Elasticsearch + Logstash + Kibana)
2. **Loki + Grafana**
3. **CloudWatch Logs** (AWS)
4. **Cloud Logging** (GCP)

---

## 安全最佳实践

### 密钥管理（规划中）

**选项 1: AWS Secrets Manager**
```python
import boto3

def get_secret(secret_name):
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return response['SecretString']

# 使用
LLM_API_KEY = get_secret('aero-agent/llm-api-key')
```

**选项 2: HashiCorp Vault**
```python
import hvac

client = hvac.Client(url='http://vault:8200', token=os.getenv('VAULT_TOKEN'))
secret = client.secrets.kv.v2.read_secret_version(path='aero-agent/llm')
LLM_API_KEY = secret['data']['data']['api_key']
```

### API 认证（规划中）

```python
# apps/api/auth.py
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != settings.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key
```

### HTTPS/SSL

```nginx
# Nginx SSL 配置
server {
    listen 443 ssl http2;
    server_name api.aero-agent.com;

    ssl_certificate /etc/ssl/certs/cert.pem;
    ssl_certificate_key /etc/ssl/private/key.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://aero-api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 故障排除

### 常见问题

**1. 服务无法启动**
```bash
# 检查日志
docker logs aero-agent-api-1

# 检查端口占用
lsof -i :8000

# 检查环境变量
docker exec aero-agent-api-1 env
```

**2. 数据库连接失败**
```bash
# 测试连接
docker exec -it aero-agent-db-1 psql -U aero -d aero

# 检查网络
docker network inspect aero-agent_default
```

**3. LLM API 调用失败**
```bash
# 测试 API 密钥
curl -H "Authorization: Bearer $LLM_API_KEY" https://api.zhipuai.cn/v1/models
```

---

## 性能优化

### 1. 连接池配置

```python
# config/database.py
from sqlalchemy import create_engine

engine = create_engine(
    DATABASE_URL,
    pool_size=20,          # 连接池大小
    max_overflow=10,       # 额外连接数
    pool_timeout=30,       # 超时时间
    pool_recycle=3600,     # 连接回收时间
)
```

### 2. Redis 缓存

```python
# 缓存航班数据
import redis

redis_client = redis.from_url(REDIS_URL)

def get_flight_data_cached(flight_no: str):
    cache_key = f"flight:{flight_no}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    data = fetch_flight_data(flight_no)
    redis_client.setex(cache_key, 3600, json.dumps(data))  # 1小时过期
    return data
```

### 3. 并发优化

```bash
# 使用 Gunicorn + Uvicorn workers
gunicorn apps.api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120
```

---

## 备份与恢复

### PostgreSQL 备份

```bash
# 每日备份
docker exec aero-agent-db-1 pg_dump -U aero aero > backup_$(date +%Y%m%d).sql

# 恢复
docker exec -i aero-agent-db-1 psql -U aero aero < backup_20240115.sql
```

### 数据文件备份

```bash
# 备份拓扑和航班数据
tar -czf data_backup_$(date +%Y%m%d).tar.gz ./data ./scripts/data_processing
```

---

## 扩展部署（Kubernetes）

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aero-agent-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: aero-agent-api
  template:
    metadata:
      labels:
        app: aero-agent-api
    spec:
      containers:
      - name: api
        image: aero-agent:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: aero-secrets
              key: database-url
        livenessProbe:
          httpGet:
            path: /health/liveness
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/readiness
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
```

---

## 相关文档

- [生产就绪度评估](./PRODUCTION_READINESS.md) - 当前限制
- [API 文档](./API_DOCUMENTATION.md) - API 端点说明
- [CLAUDE.md](../CLAUDE.md) - 开发指南
