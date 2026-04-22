# FormForge AI

**Turn your CSV data into completed web applications - intelligently, reliably, at scale.**

FormForge AI is a full-featured, AI-augmented application engine designed to automate the end-to-end process of filling and submitting web forms and multi-step applications on any user-defined website, driven by structured data from CSV, Excel, or Google Sheets.

## Quick Start

```bash
# Clone and setup
git clone <repository-url>
cd formforge-ai
docker-compose up -d

# Access the dashboard
open http://localhost:3000
```

## Architecture

- **Backend**: FastAPI with Playwright automation
- **Frontend**: Next.js with shadcn/ui
- **Database**: PostgreSQL + Redis
- **AI**: Vision models for field detection + LLM for mapping
- **Orchestration**: Celery with Docker/Kubernetes

## Key Features

- **AI-Powered Detection**: Computer vision + semantic understanding
- **CSV-Native**: Deep integration with column mapping and validation
- **Multi-Step Workflows**: Handle complex application flows
- **Stealth Mode**: Human-like behavior patterns
- **Enterprise Scale**: Batch processing thousands of submissions
- **Self-Hostable**: Open-source core with cloud options

## Documentation

See [FormForge_AI_Concept_Spec.md](./FormForge_AI_Concept_Spec.md) for the complete technical specification.

## Development Status

This project is currently in development. See the issues and projects for progress tracking.
# ifill_forms
