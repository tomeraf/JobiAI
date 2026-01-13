# JobiAI - LinkedIn Job Application Bot

An automated bot that helps you apply for jobs by leveraging your LinkedIn connections. Submit a job URL, and the bot finds people at that company and sends personalized outreach messages.

## Features

### Core Workflow
- **Job URL Submission**: Paste any job URL - the bot extracts the company name automatically
- **Smart Site Learning**: Unknown job site? Teach the bot once, it remembers forever
- **Connection Discovery**: Finds your LinkedIn connections at the target company
- **Personalized Messaging**: Sends customized messages with Hebrew name support
- **Persistent Follow-up**: Jobs stay active until someone actually replies

### LinkedIn Automation
- **Multi-Degree Outreach**:
  1. First, messages your 1st degree connections at the company
  2. If all 1st degree already messaged → sends connection requests to 2nd degree
  3. Falls back to 3rd+ degree if no 2nd degree available
- **Message History Detection**: Skips contacts you've already messaged
- **Connection Request Tracking**: Waits for accepts, then re-searches for new 1st degree contacts
- **Reply Checking**: Monitors for responses to your outreach

### Smart Features
- **Hebrew Name Translation**: Automatically translates names to Hebrew for personalized messages
  - Built-in dictionary of 200+ common Israeli names
  - Pauses workflow if unknown name found, prompts you for translation
- **Template System**: Reusable message templates with `{name}` and `{company}` placeholders
- **Activity Logging**: Full audit trail of all bot actions

## Tech Stack

- **Backend**: Python 3.11, FastAPI, PostgreSQL, SQLAlchemy 2.0, Alembic
- **Frontend**: React 18, TypeScript, Vite, TailwindCSS, React Query
- **Automation**: Playwright with playwright-stealth (anti-detection)
- **Containerization**: Docker & Docker Compose

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 18+ (for frontend)
- Python 3.11+ (for backend)

### Development Setup

```bash
# 1. Start the database only
docker-compose up -d db

# 2. Set up the backend
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
playwright install chromium

# Run migrations
alembic upgrade head

# Start backend on port 9000
uvicorn app.main:app --reload --port 9000

# 3. In another terminal, set up the frontend
cd frontend
npm install
npm run dev  # Starts on port 5173

# 4. Open http://localhost:5173
```

### Production Deployment

```bash
docker-compose --profile full up -d
# Access at http://localhost:3000
```

## Usage Guide

### 1. Connect to LinkedIn

1. Go to **Settings**
2. Click **Login with Browser**
3. Log in to LinkedIn in the browser window that opens
4. Your session is saved automatically in `linkedin_data/`

### 2. Create Message Templates

1. Go to **Templates**
2. Create a new template with your message
3. Use placeholders:
   - `{name}` - Contact's first name (auto-translated to Hebrew if template contains Hebrew)
   - `{company}` - Company name
4. Set one template as default

**Example template:**
```
היי {name}, ראיתי שאתה עובד ב-{company} וחשבתי ליצור קשר...
```

### 3. Submit Jobs

1. Go to **Jobs**
2. Paste a job URL (auto-submits on paste)
3. Click the **Play** button to start the workflow
4. The bot will:
   - Extract company name from URL
   - Search LinkedIn for people at that company
   - Send personalized messages to 1st degree connections
   - Send connection requests to 2nd/3rd degree if needed

### 4. Workflow States

Jobs progress through these states:

| Status | Meaning |
|--------|---------|
| **Pending** | Job submitted, awaiting processing |
| **Processing** | Currently running LinkedIn automation |
| **Needs Input** | Waiting for you (company name or Hebrew translation) |
| **Waiting for Reply** | Messages sent, waiting for responses |
| **Waiting for Accept** | Connection requests sent, waiting for accepts |
| **Done** | Someone replied! Mission complete |
| **Failed** | Something went wrong |
| **Aborted** | You stopped the workflow |

### 5. Action Buttons

| Button | Action |
|--------|--------|
| **Play** (green) | Start workflow / Search for new people to message |
| **Message** (blue) | Check for replies only (for waiting jobs) |
| **Retry** | Retry failed job |
| **Stop** | Abort running workflow |
| **Delete** | Remove job |

### 6. Monitor Activity

- **Dashboard**: Overview stats and recent activity
- **Logs**: Detailed activity history with filters

## Project Structure

```
JobiAI/
├── backend/
│   ├── app/
│   │   ├── api/              # API route handlers
│   │   │   ├── jobs.py       # Job management endpoints
│   │   │   ├── templates.py  # Message template CRUD
│   │   │   ├── selectors.py  # Site selector management
│   │   │   ├── logs.py       # Activity log viewing
│   │   │   ├── auth.py       # LinkedIn authentication
│   │   │   └── hebrew_names.py # Name translation API
│   │   ├── models/           # SQLAlchemy models
│   │   │   ├── job.py        # Job with workflow states
│   │   │   ├── contact.py    # LinkedIn contacts
│   │   │   ├── template.py   # Message templates
│   │   │   ├── site_selector.py # URL pattern learning
│   │   │   ├── activity.py   # Activity logs
│   │   │   └── hebrew_name.py # Name translations
│   │   ├── services/
│   │   │   ├── job_processor.py      # Company extraction
│   │   │   ├── workflow_orchestrator.py # Main workflow engine
│   │   │   ├── hebrew_names.py       # Name translation service
│   │   │   ├── job_parser.py         # URL parsing
│   │   │   └── linkedin/
│   │   │       ├── client.py         # Main Playwright automation (singleton)
│   │   │       ├── selectors.py      # CSS selectors for LinkedIn
│   │   │       ├── extractors.py     # Person data extraction
│   │   │       ├── browser_utils.py  # Browser context & helpers
│   │   │       ├── vip_filter.py     # VIP title detection
│   │   │       └── js_scripts.py     # JavaScript evaluation strings
│   │   └── utils/
│   │       └── logger.py     # Logging utilities
│   ├── alembic/              # Database migrations
│   └── linkedin_data/        # Persistent browser session
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── client.ts     # API client (axios)
│   │   ├── components/
│   │   │   └── Layout.tsx    # App layout with navigation
│   │   └── pages/
│   │       ├── Dashboard.tsx # Stats and activity feed
│   │       ├── Jobs.tsx      # Job management UI
│   │       ├── Templates.tsx # Template editor
│   │       ├── Logs.tsx      # Activity log viewer
│   │       └── Settings.tsx  # LinkedIn auth & selectors
│   └── ...
└── docker-compose.yml
```

## API Reference

### Jobs API (`/api/jobs`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/` | Submit new job URL |
| GET | `/` | List jobs (optional status filter) |
| GET | `/{id}` | Get job details |
| DELETE | `/{id}` | Delete job |
| POST | `/{id}/retry` | Retry failed job |
| POST | `/{id}/company` | Submit company info for unknown site |
| POST | `/{id}/workflow` | Trigger LinkedIn workflow |
| POST | `/{id}/hebrew-names` | Submit Hebrew translations |
| GET | `/{id}/contacts` | Get contacts for job |
| POST | `/abort` | Abort running workflow |
| GET | `/current` | Get currently running job |

### Templates API (`/api/templates`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/` | Create template |
| GET | `/` | List all templates |
| GET | `/{id}` | Get template |
| PUT | `/{id}` | Update template |
| DELETE | `/{id}` | Delete template |
| POST | `/{id}/preview` | Preview with sample data |
| GET | `/default/current` | Get default template |

### Other APIs
- **Selectors** (`/api/selectors`): Manage learned URL patterns
- **Logs** (`/api/logs`): View activity history
- **Auth** (`/api/auth`): LinkedIn login status
- **Hebrew Names** (`/api/hebrew-names`): Name translations

## Configuration

### Environment Variables

```env
# Backend (.env)
DATABASE_URL=postgresql://user:pass@localhost:5436/jobiai
BROWSER_HEADLESS=false  # Always false for safety
FAST_MODE=true          # true=300ms delays, false=1000ms delays
```

### LinkedIn Rate Limits

The bot respects LinkedIn's limits to avoid detection:
- ~100-150 messages per day
- ~50-100 connection requests per week
- Random delays between actions (300-2000ms)

## Anti-Detection Measures

- **playwright-stealth**: Evades bot detection
- **Headed browser**: Always visible (headless is easily detected)
- **Human-like delays**: Random pauses between actions
- **Persistent session**: Reuses browser profile
- **No automation flags**: Clean browser fingerprint

## Important Notes

- **Manual LinkedIn login required** on first run
- **Never run in headless mode** - LinkedIn detects it
- **Respect rate limits** - Aggressive usage gets accounts flagged
- **Session persistence** - Browser data saved in `linkedin_data/`
- **Backend doesn't auto-reload** - Restart after code changes

## Supported Job Platforms

Pre-configured URL pattern extraction for:
- Greenhouse, Lever, Workday, Ashby
- SmartRecruiters, Breezy, BambooHR
- Recruitee, ApplyToJob, iCIMS

For other sites, the bot learns the pattern from your first example.

## License

MIT
