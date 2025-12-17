# JobiAI - LinkedIn Job Application Bot

## Project Overview
A bot that helps users apply for jobs by leveraging LinkedIn connections. Users submit job URLs through a web app, and the bot automatically finds and contacts relevant people at the target company.

## Tech Stack
- **Backend**: Python, FastAPI, PostgreSQL, SQLAlchemy, Alembic
- **Frontend**: React, TypeScript, Vite
- **Automation**: Playwright with playwright-stealth (anti-detection)
- **Containerization**: Docker, Docker Compose

## Project Structure
```
JobiAI/
├── backend/           # FastAPI Python backend
│   ├── app/
│   │   ├── api/       # API route handlers
│   │   ├── models/    # SQLAlchemy models
│   │   ├── services/  # Business logic
│   │   │   └── linkedin/  # LinkedIn automation
│   │   └── utils/     # Helpers
│   ├── browser_data/  # Persistent LinkedIn session
│   └── alembic/       # Database migrations
├── frontend/          # React web dashboard
└── docker-compose.yml
```

---

## Current Implementation Status

### ✅ COMPLETED FEATURES

#### 1. Job URL Submission & Processing
- Submit job URLs via web dashboard
- Background processing with status updates
- Job statuses: PENDING → PROCESSING → COMPLETED/NEEDS_INPUT/FAILED
- Retry failed jobs, delete jobs

#### 2. Smart Job Site Parser (Pattern-Based Learning)
- **Pre-configured platforms**: Greenhouse, Lever, Workday, Ashby, SmartRecruiters, Breezy, BambooHR, Recruitee, ApplyToJob, iCIMS
- **URL pattern extraction**: Extracts company name from URL structure (subdomain or path)
- **Learning system**: When unknown site encountered:
  - User classifies as "Company Website" or "Job Platform"
  - User provides company name (+ platform name if platform)
  - System learns URL pattern and saves for future auto-extraction
- **No CSS scraping**: Pure URL-based extraction (more reliable)

#### 3. LinkedIn Authentication
- Persistent browser session saved to `browser_data/`
- Manual login on first run, auto-login thereafter
- Login status check via API
- Stealth mode with anti-detection measures

#### 4. LinkedIn Automation (Fully Working)
- **Connection Search**: Search existing 1st degree connections by company
- **People Search**: Search LinkedIn for 2nd/3rd+ degree people at a company
- **Smart Messaging**:
  - Detects existing message history before sending
  - Skips contacts already messaged (prevents duplicates)
  - Properly closes chat modals after checking
- **Connection Requests**: Send requests to 2nd/3rd+ degree with optional notes
- **Multi-Degree Workflow**:
  1. Search 1st degree → send messages
  2. If all 1st degree skipped (existing history) → try 2nd degree
  3. If no 2nd degree with Connect button → try 3rd+ degree
  4. Sends connection requests to 2nd/3rd+ degree people

#### 5. Gender-Aware Messaging
- Templates with male/female/neutral variants
- Gender detection from:
  - Hebrew name database (200+ names)
  - International name analysis (gender-guesser library)
- Template variables: `{name}`, `{company}`

#### 6. Activity Logging
- 9 action types tracked:
  - JOB_SUBMITTED, COMPANY_EXTRACTED, COMPANY_INPUT_NEEDED
  - SELECTOR_LEARNED, CONNECTION_SEARCH, CONNECTION_FOUND
  - CONNECTION_REQUEST_SENT, MESSAGE_SENT, LINKEDIN_SEARCH, ERROR
- Dashboard with stats and recent activity
- Filter by action type, job, date

#### 7. Frontend Dashboard
- **Jobs Page**: Submit URLs, view status, retry/delete, company input modal, play button to trigger workflow
- **Dashboard**: Stats cards, recent activity feed
- **Templates Page**: CRUD for message templates with preview
- **Settings Page**: LinkedIn login/logout, site selector management
- **Logs Page**: Activity history with filters

#### 8. Database Models
- `jobs` - URL, company, status, timestamps, pending_hebrew_names
- `contacts` - LinkedIn profile, gender, connection/message status
- `templates` - Gender-specific message content
- `site_selectors` - Domain patterns, site type, learned URL patterns
- `activity_logs` - Action tracking with JSON details
- `hebrew_names` - Hebrew to English name translations

#### 9. End-to-End Workflow Orchestration
- **Full workflow from job submission to outreach**:
  1. Extract company name from job URL
  2. Search LinkedIn for people at that company
  3. Message 1st degree connections (with history check)
  4. Send connection requests to 2nd/3rd+ degree
- **Workflow state tracking**: Jobs track current step
- **Overlay management**: Closes open chat dialogs before automation
- **Hebrew name translation**: Pauses workflow if unknown Hebrew names found

---

### ❌ TODO: Features Still Needed

#### Priority 1: Contacts API & Management
- [ ] **Contacts API endpoints**
  - `GET /api/contacts` - List all contacts
  - `GET /api/jobs/{id}/contacts` - Contacts found for a job
  - `PUT /api/contacts/{id}` - Update contact status
  - `DELETE /api/contacts/{id}` - Delete contact
- [ ] **Contacts Dashboard UI**
  - View contacts per job
  - See message/connection status
  - Manual retry for failed messages

#### Priority 2: Rate Limiting & Safety
- [ ] **Enforce LinkedIn limits in code**
  - Track daily message count (max ~150/day)
  - Track weekly connection requests (max ~100/week)
  - Pause/warn when approaching limits
- [ ] **Backoff on errors**
  - Detect rate limit responses from LinkedIn
  - Auto-pause and retry with exponential backoff

#### Priority 3: Testing & Polish
- [ ] **Integration tests**
  - Test full workflow with mocked LinkedIn
  - Test selector learning flow
- [ ] **Error recovery**
  - Handle LinkedIn session expiry gracefully

---

## Database Schema

### Tables
- `jobs` - Submitted job URLs and status
- `contacts` - People contacted/added on LinkedIn
- `activity_logs` - All bot actions (for dashboard)
- `templates` - Message templates (male/female variants)
- `site_selectors` - Learned URL patterns per job site domain

### Site Selector Fields
- `domain` - The job site domain (e.g., "greenhouse.io")
- `site_type` - "company" or "platform"
- `company_name` - For company sites, the fixed company name
- `platform_name` - For platforms, the platform name (e.g., "Greenhouse")
- `url_pattern` - Regex to extract company from URL

## Anti-Detection Strategy
- Use `playwright-stealth` plugin
- Random delays between actions (2-5 seconds)
- Human-like behavior patterns
- Persistent browser profile
- Respect LinkedIn limits (~100 connections/week, ~150 messages/day)
- Run in headed mode (visible browser)

## API Endpoints

### Jobs (8 endpoints)
- `POST /api/jobs` - Submit new job URL
- `GET /api/jobs` - List all jobs (with status filter)
- `GET /api/jobs/{id}` - Get job details
- `DELETE /api/jobs/{id}` - Delete job
- `POST /api/jobs/{id}/retry` - Retry failed job
- `POST /api/jobs/{id}/company` - Submit company info for unknown site
- `POST /api/jobs/{id}/process` - Manual processing trigger

### Templates (7 endpoints)
- `POST /api/templates` - Create template
- `GET /api/templates` - List templates
- `GET /api/templates/{id}` - Get template
- `PUT /api/templates/{id}` - Update template
- `DELETE /api/templates/{id}` - Delete template
- `POST /api/templates/{id}/preview` - Preview with sample data
- `GET /api/templates/default/current` - Get default template

### Selectors (6 endpoints)
- `POST /api/selectors` - Create/learn selector
- `GET /api/selectors` - List all selectors
- `GET /api/selectors/{id}` - Get by ID
- `GET /api/selectors/domain/{domain}` - Get by domain
- `PUT /api/selectors/{id}` - Update selector
- `DELETE /api/selectors/{id}` - Delete selector

### Logs (4 endpoints)
- `GET /api/logs` - List with filters
- `GET /api/logs/stats` - Get statistics
- `GET /api/logs/recent` - Recent activity
- `GET /api/logs/job/{id}` - Logs for specific job

### Auth (3 endpoints)
- `GET /api/auth/status` - Check LinkedIn login status
- `POST /api/auth/login` - Trigger login flow (opens browser)
- `POST /api/auth/logout` - Clear session

## Environment Variables
```
DATABASE_URL=postgresql://user:pass@localhost:5432/jobiai
LINKEDIN_EMAIL=user@example.com  # Optional, for reference only
BROWSER_HEADLESS=false           # Keep false for safety
```

## Development Commands
```bash
# Start all services
docker-compose up

# Rebuild after code changes
docker-compose up -d --build

# Backend only
cd backend && uvicorn app.main:app --reload

# Frontend only
cd frontend && npm run dev

# Run migrations
docker-compose exec backend alembic upgrade head

# Run tests
docker-compose exec backend pytest
```

## Important Notes
- Never run bot in headless mode (easier detection)
- Always respect LinkedIn's rate limits
- Bot actions are logged for transparency
- User must manually log in to LinkedIn on first run
- **⚠️ Backend does NOT auto-reload** - Must manually restart after code changes

---

## 🚧 Current Development Status (Dec 2025)

### Recently Completed
- ✅ **Full end-to-end workflow working** - Play button triggers complete LinkedIn automation
- ✅ Hebrew name translation feature for personalized messages
- ✅ Database model for Hebrew name mappings (`hebrew_names` table)
- ✅ API endpoints for name translation prompts
- ✅ Workflow pauses at `NEEDS_HEBREW_NAMES` step when unknown names found
- ✅ Frontend UI for handling Hebrew name translation prompts
- ✅ Close all open message overlays when entering LinkedIn workflow
- ✅ **Message history detection** - Skips contacts already messaged
- ✅ **Multi-degree fallback** - If 1st degree all skipped, tries 2nd, then 3rd+
- ✅ **Robust chat modal closing** - Multiple methods to close chat dialogs

### Workflow Steps
```
COMPANY_EXTRACTION → SEARCH_CONNECTIONS → MESSAGE_1ST_DEGREE → CONNECT_2ND/3RD_DEGREE → DONE
```

### Company Matching Behavior
- For 2nd/3rd degree: Only connects to people with company name in their headline
- Example: Searching "home" will only connect to people with "Home" (the company) in their title
- This prevents sending requests to random people who just have the search term elsewhere

### Development Notes
- Backend runs on port 9000
- Frontend runs on Vite dev server
- Database: PostgreSQL with SQLAlchemy async
- Migrations: Alembic (remember to run `alembic upgrade head` after new migrations)
