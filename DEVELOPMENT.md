# FormForge AI Development Guide

## Quick Start

1. **Clone and Setup**
   ```bash
   git clone <repository-url>
   cd formforge-ai
   cp .env.example .env
   # Edit .env with your configuration
   ```

2. **Start with Docker**
   ```bash
   docker-compose up -d
   ```

3. **Access the Application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - MinIO Console: http://localhost:9001

## Development Setup

### Backend (FastAPI)

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Run database migrations
python -c "from models import create_db_and_tables; create_db_and_tables()"

# Start development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

## Architecture Overview

### Backend Components

- **`main.py`**: FastAPI application entry point
- **`browser_engine.py`**: Playwright automation with stealth
- **`ai_mapper.py`**: AI-powered field detection and mapping
- **`data_processor.py`**: CSV/Excel data processing pipeline
- **`job_manager.py`**: Job orchestration and execution
- **`models.py`**: SQLModel database models
- **`schemas.py`**: Pydantic data validation schemas

### Frontend Components

- **`app/page.tsx`**: Main dashboard with jobs/profiles overview
- **`components/ui/`**: Reusable UI components (shadcn/ui)
- **`lib/utils.ts`**: Utility functions and helpers

### Key Features

1. **AI-Powered Form Detection**: Uses computer vision + LLM to understand web forms
2. **CSV-Native Processing**: Deep integration with data mapping and validation
3. **Multi-Step Workflows**: Handle complex application flows
4. **Stealth Automation**: Human-like behavior patterns
5. **Real-Time Monitoring**: WebSocket-based job progress tracking
6. **Enterprise Scale**: Docker/Kubernetes ready

## API Endpoints

### Profiles
- `POST /api/profiles` - Create new site profile
- `GET /api/profiles` - List all profiles
- `GET /api/profiles/{id}` - Get specific profile
- `PUT /api/profiles/{id}` - Update profile
- `DELETE /api/profiles/{id}` - Delete profile

### Jobs
- `POST /api/jobs` - Create new automation job
- `GET /api/jobs` - List all jobs
- `GET /api/jobs/{id}` - Get job details
- `POST /api/jobs/{id}/start` - Start job execution
- `POST /api/jobs/{id}/stop` - Stop job execution
- `GET /api/jobs/{id}/logs` - Get job execution logs

### AI & Analysis
- `POST /api/analyze-site` - Analyze website for form detection
- `POST /api/map-fields` - AI-powered CSV to field mapping
- `POST /api/test-profile` - Test profile with sample data

### File Processing
- `POST /api/upload-csv` - Upload and analyze CSV/Excel files

## Configuration

### Environment Variables

Key environment variables in `.env`:

```bash
# Database
DATABASE_URL=postgresql://formforge:password@localhost:5432/formforge

# AI Services
OPENAI_API_KEY=your-openai-api-key

# Browser Settings
BROWSER_HEADLESS=true
BROWSER_CONCURRENCY=5

# Security
SECRET_KEY=your-secret-key
```

### Browser Configuration

The system uses Playwright with stealth features:

- **Headless Mode**: Configurable (default: true)
- **Concurrency**: Multiple browser instances
- **Stealth**: Anti-detection measures
- **Proxy Support**: Rotating proxy integration

## Testing

### Unit Tests
```bash
# Backend
cd backend
pytest

# Frontend  
cd frontend
npm test
```

### Integration Tests
```bash
# Test profile creation and execution
curl -X POST "http://localhost:8000/api/test-profile" \
  -H "Content-Type: application/json" \
  -d '{"profile_id": "test", "test_data": {...}}'
```

## Deployment

### Docker Production
```bash
# Build and deploy
docker-compose -f docker-compose.prod.yml up -d

# Scale workers
docker-compose -f docker-compose.prod.yml up -d --scale worker=3
```

### Kubernetes
```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/
```

## Monitoring & Logging

- **Logs**: Located in `./logs/` directory
- **Metrics**: Real-time job progress via WebSocket
- **Health Checks**: `/health` endpoint
- **Error Tracking**: Detailed execution logs with screenshots

## Security Considerations

1. **Data Privacy**: All PII encrypted at rest
2. **Access Control**: RBAC with API keys
3. **Audit Trail**: Immutable execution logs
4. **Rate Limiting**: Configurable delays and limits
5. **Proxy Rotation**: Residential proxy support

## Troubleshooting

### Common Issues

1. **Browser Launch Failures**
   - Ensure Playwright browsers installed: `playwright install`
   - Check system dependencies for headless Chrome

2. **Database Connection**
   - Verify PostgreSQL container is running
   - Check connection string in `.env`

3. **AI Service Errors**
   - Verify OpenAI API key is valid
   - Check rate limits and quotas

4. **Memory Issues**
   - Reduce browser concurrency
   - Enable headless mode
   - Monitor Docker resource limits

### Debug Mode

Enable detailed logging:
```bash
LOG_LEVEL=DEBUG docker-compose up
```

## Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Submit pull request

## License

This project is licensed under AGPL-3.0 - see LICENSE file for details.
