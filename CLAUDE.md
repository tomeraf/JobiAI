# JobiAI - LinkedIn Job Application Bot

## Two Running Modes

### 1. Hidden Background Mode (Recommended for Daily Use)
Double-click `JobiAI.vbs` to run completely hidden (no CMD windows):
- **Backend**: Runs hidden on port 9000
- **Frontend**: Runs hidden on port 5173 (Vite dev server)
- **Database**: SQLite at `%LOCALAPPDATA%\JobiAI\jobiai.db`
- **Browser data**: `backend/linkedin_data/browser_context/` (same as dev mode)
- **Stop**: Close the browser tab (auto-exits), or run `exit-JobiAI.bat`
- **No Docker required** - uses SQLite by default

**Auto-shutdown**: When you close the browser tab, the frontend sends a shutdown signal to the backend. As a fallback, if no heartbeat is received for 30 seconds, the backend auto-shuts down. This means you don't need to manually stop anything.

**How it works**: The VBS sets `DATABASE_URL` env var before starting Python. The [config.py](backend/app/config.py) checks if `DATABASE_URL` is already set - if so, it skips loading `.env` (which contains PostgreSQL settings for dev mode). This lets the same code run with different databases.

### 2. Development Mode (for developers)
- **Backend and Frontend run LOCALLY** (not in Docker)
- **Only PostgreSQL runs in Docker** (via docker-compose)
- **Backend logs are at**: `c:\projects\JobiAI\backend\backend.log`
- **Start everything with**: `start-dev.bat` (opens CMD windows with live output)
- **Restart with**: `restart-dev.bat` (stops and starts all services)
- **The app runs in CMD windows** - check these for live errors/logs when debugging
- **Backend port**: Dynamic (tries 9000-9099, then 9200-9299, then 9500-9599 due to Windows/Hyper-V port exclusions)
- **Frontend port**: 5173 (local Vite)
- **Port config saved to**: `.ports.json` (shared between backend and frontend)

### Migrating Data from Dev (PostgreSQL) to Hidden Mode (SQLite)
```bash
# Start Docker with PostgreSQL first, then run:
cd backend
python scripts/migrate_to_sqlite.py migrate \
  --from "postgresql://postgres:postgres@localhost:5436/jobiai" \
  --to "sqlite:///C:/Users/YOUR_USER/AppData/Local/JobiAI/jobiai.db"
```

### Database Selection
- **If `DATABASE_URL` env var is set BEFORE Python starts**: Uses that value, `.env` file is NOT loaded
- **If `DATABASE_URL` is NOT set**: Loads `.env` file (PostgreSQL for dev mode)
- **If neither**: Defaults to SQLite at `%LOCALAPPDATA%\JobiAI\jobiai.db`
- Key logic in [config.py:64](backend/app/config.py#L64): `env_file = ".env" if not os.environ.get('DATABASE_URL') else None`


## Project Overview
A bot that helps users apply for jobs by leveraging LinkedIn connections. Users submit job URLs through a web app, and the bot automatically finds and contacts relevant people at the target company.

## Tech Stack
- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic
- **Database**: SQLite (desktop) or PostgreSQL (dev mode)
- **Frontend**: React 18, TypeScript, Vite, TailwindCSS, React Query
- **Automation**: Playwright with playwright-stealth (anti-detection)
- **Containerization**: Docker, Docker Compose (dev mode only)

## Project Structure
```
JobiAI/
├── backend/
│   ├── app/
│   │   ├── api/              # API route handlers
│   │   │   ├── jobs.py       # Job CRUD + workflow triggers
│   │   │   ├── templates.py  # Message template management
│   │   │   ├── selectors.py  # Site selector CRUD
│   │   │   ├── logs.py       # Activity log viewing
│   │   │   ├── auth.py       # LinkedIn authentication
│   │   │   └── hebrew_names.py # Name translation API
│   │   ├── models/           # SQLAlchemy models
│   │   │   ├── job.py        # Job with status + workflow_step
│   │   │   ├── contact.py    # LinkedIn contacts
│   │   │   ├── template.py   # Message templates
│   │   │   ├── site_selector.py # URL pattern learning
│   │   │   ├── activity.py   # Activity logs
│   │   │   └── hebrew_name.py # Name translations
│   │   ├── services/
│   │   │   ├── job_processor.py      # Company extraction from URLs
│   │   │   ├── workflow_orchestrator.py # Main workflow engine
│   │   │   ├── hebrew_names.py       # Name translation service
│   │   │   ├── job_parser.py         # URL parsing utilities
│   │   │   └── linkedin/             # LinkedIn automation module
│   │   │       ├── client.py         # Main Playwright browser automation
│   │   │       ├── selectors.py      # Centralized CSS selectors
│   │   │       ├── extractors.py     # Person data extraction utilities
│   │   │       ├── browser_utils.py  # Browser context & retry helpers
│   │   │       ├── js_scripts.py     # JavaScript evaluation strings
│   │   │       └── vip_filter.py     # VIP title detection
│   │   ├── utils/
│   │   │   ├── logger.py     # Logging utilities
│   │   │   ├── delays.py     # Random delay helper
│   │   │   └── port_finder.py # Dynamic port allocation
│   ├── scripts/
│   │   └── migrate_to_sqlite.py # PostgreSQL to SQLite migration
│   ├── alembic/              # Database migrations
│   └── linkedin_data/        # Persistent browser session
├── frontend/
│   ├── src/
│   │   ├── api/client.ts     # Axios API wrapper
│   │   ├── components/Layout.tsx
│   │   └── pages/
│   │       ├── Jobs.tsx      # Job management + workflow UI
│   │       ├── Stats.tsx     # Statistics page
│   │       ├── Templates.tsx # Template editor
│   │       ├── Logs.tsx      # Activity log viewer
│   │       └── Settings.tsx  # LinkedIn auth + selectors
└── docker-compose.yml
```

---

## Database Schema

### Job Model (`jobs` table)
```
id                    INT PK
url                   TEXT (job posting URL)
company_name          VARCHAR (extracted or user-provided)
job_title             VARCHAR (optional)
status                ENUM: pending|processing|needs_input|completed|failed|aborted|done|rejected
workflow_step         ENUM: company_extraction|search_connections|needs_hebrew_names|
                            message_connections|waiting_for_reply|search_linkedin|
                            send_requests|waiting_for_accept|done
error_message         TEXT (if failed)
pending_hebrew_names  JSON ARRAY (names needing translation)
last_reply_check_at   DATETIME (when replies were last checked)
created_at            DATETIME
processed_at          DATETIME
```

### Contact Model (`contacts` table)
```
id                      INT PK
linkedin_url            TEXT UNIQUE (profile URL)
name                    VARCHAR
company                 VARCHAR
position                VARCHAR
is_connection           BOOLEAN (1st degree = true)
connection_requested_at DATETIME
message_sent_at         DATETIME
message_content         TEXT
reply_received_at       DATETIME
job_id                  INT FK → jobs
created_at              DATETIME
```

### Template Model (`templates` table)
```
id          INT PK
name        VARCHAR
content     TEXT (supports {name}, {company} placeholders)
is_default  BOOLEAN
created_at  DATETIME
updated_at  DATETIME
```

### SiteSelector Model (`site_selectors` table)
```
id              INT PK
domain          VARCHAR UNIQUE
site_type       ENUM: company|platform
company_name    VARCHAR (for company sites)
platform_name   VARCHAR (e.g., "Greenhouse")
url_pattern     TEXT (regex for company extraction)
example_url     TEXT
example_company TEXT
created_at      DATETIME
last_used_at    DATETIME
```

### HebrewName Model (`hebrew_names` table)
```
id            INT PK
english_name  VARCHAR UNIQUE
hebrew_name   VARCHAR
created_at    DATETIME
```

### ActivityLog Model (`activity_logs` table)
```
id          INT PK
action_type ENUM: job_submitted|company_extracted|company_input_needed|
                  selector_learned|connection_search|connection_found|
                  connection_request_sent|message_sent|linkedin_search|error
description TEXT
details     JSON
job_id      INT FK → jobs (optional)
created_at  DATETIME
```

---

## API Endpoints

### Jobs (`/api/jobs`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/` | Submit new job URL |
| GET | `/` | List jobs (optional `?status=` filter) |
| GET | `/{id}` | Get job details |
| DELETE | `/{id}` | Delete job |
| POST | `/{id}/retry` | Retry failed job |
| POST | `/{id}/company` | Submit company info for unknown site |
| POST | `/{id}/process` | Trigger company extraction only |
| POST | `/{id}/workflow` | Trigger full LinkedIn workflow |
| POST | `/{id}/search-connections` | Manual connection search |
| GET | `/{id}/contacts` | Get contacts for this job |
| GET | `/{id}/pending-hebrew-names` | Get names needing translation |
| POST | `/{id}/hebrew-names` | Submit Hebrew translations |
| POST | `/abort` | Abort currently running workflow |
| GET | `/current` | Get info about running workflow |

### Templates (`/api/templates`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/` | Create template |
| GET | `/` | List all templates |
| GET | `/{id}` | Get template |
| PUT | `/{id}` | Update template |
| DELETE | `/{id}` | Delete template |
| POST | `/{id}/preview` | Preview with sample data |
| GET | `/default/current` | Get default template |

### Selectors (`/api/selectors`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/` | Create/learn selector |
| GET | `/` | List all selectors |
| GET | `/{id}` | Get by ID |
| GET | `/domain/{domain}` | Get by domain |
| PUT | `/{id}` | Update selector |
| DELETE | `/{id}` | Delete selector |
| POST | `/check` | Check if URL has known selector |

### Logs (`/api/logs`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List logs (filters: action_type, job_id, skip, limit) |
| GET | `/stats` | Get activity statistics |
| GET | `/recent` | Get most recent logs |
| GET | `/job/{id}` | Get logs for specific job |

### Auth (`/api/auth`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/status` | Check LinkedIn login status |
| POST | `/login` | Login with email/password |
| POST | `/login-browser` | Open browser for manual login |
| POST | `/logout` | Clear session |

### Hebrew Names (`/api/hebrew-names`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/` | Add single translation |
| POST | `/bulk` | Add multiple translations |
| GET | `/` | List all translations |
| GET | `/{name}` | Get translation for name |
| POST | `/check-missing` | Check which names need translation |
| DELETE | `/{id}` | Delete translation |

---

## Workflow State Machine

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           JOB SUBMISSION                                     │
│  User pastes URL → Job created with status=PENDING                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       COMPANY_EXTRACTION                                     │
│  Extract company name from URL using:                                        │
│  1. Database selectors (learned patterns)                                    │
│  2. Pre-configured platforms (Greenhouse, Lever, etc.)                       │
│  3. User input if unknown                                                    │
│                                                                              │
│  → Success: status=COMPLETED, company_name set                               │
│  → Unknown site: status=NEEDS_INPUT (wait for user)                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                     User clicks Play button
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       SEARCH_CONNECTIONS                                     │
│  Search LinkedIn for people at the company                                   │
│  - Uses search_company_all_degrees() which:                                  │
│    1. Searches 1st degree connections                                        │
│    2. Sends message to ONE person, then stops                                │
│    3. Falls back to 2nd/3rd degree if no 1st available                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
            Found 1st degree   Missing Hebrew   No 1st degree
                    │          names found           │
                    │               │                │
                    ▼               ▼                ▼
┌──────────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ MESSAGE_CONNECTIONS  │  │ NEEDS_HEBREW_    │  │ SEND_REQUESTS    │
│                      │  │ NAMES            │  │                  │
│ Send ONE message to  │  │                  │  │ Send connection  │
│ first available 1st  │  │ status=NEEDS_    │  │ requests to up   │
│ degree connection    │  │ INPUT            │  │ to 10 people     │
│                      │  │ Pause workflow   │  │ (max 5 pages)    │
│ Skips VIPs (CEO,     │  │ Display UI for   │  │                  │
│ CTO, founders, etc.) │  │ user to provide  │  │ Skips VIPs and   │
│                      │  │ translations     │  │ email-required   │
│ Checks for existing  │  │                  │  │ connections      │
│ conversation history │  │                  │  │                  │
└──────────────────────┘  └──────────────────┘  └──────────────────┘
           │                       │                    │
           ▼                       │                    ▼
┌──────────────────────┐           │           ┌──────────────────┐
│ WAITING_FOR_REPLY    │           │           │ WAITING_FOR_     │
│                      │◄──────────┘           │ ACCEPT           │
│ status=COMPLETED     │  (User provides       │                  │
│ Message sent,        │   translations,       │ status=COMPLETED │
│ waiting for reply    │   workflow resumes)   │ Requests sent,   │
│                      │                       │ waiting for      │
│ Blue "Check Replies" │                       │ accepts          │
│ + Green "Play" btn   │                       │                  │
└──────────────────────┘                       └──────────────────┘
           │                                            │
           │  (User clicks Check Replies                │  (User clicks Play
           │   or Play button)                          │   to re-search)
           ▼                                            ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  REPLY CHECK / RE-SEARCH                                                      │
│                                                                               │
│  - Check Replies (forceSearch=false): Only checks inbox for replies           │
│  - Play (forceSearch=true): Searches for NEW people to message                │
│                                                                               │
│  → Found reply: workflow_step=DONE, mission complete!                         │
│  → No reply: Stay in WAITING state or find new people                         │
│  → New 1st degree (from accepted requests): Message them                      │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DONE                                            │
│  Someone replied to our message! Job complete.                               │
│  Green checkmark badge displayed.                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Workflow Steps Enum
```python
class WorkflowStep(str, Enum):
    COMPANY_EXTRACTION = "company_extraction"
    SEARCH_CONNECTIONS = "search_connections"
    NEEDS_HEBREW_NAMES = "needs_hebrew_names"
    MESSAGE_CONNECTIONS = "message_connections"
    WAITING_FOR_REPLY = "waiting_for_reply"
    SEARCH_LINKEDIN = "search_linkedin"
    SEND_REQUESTS = "send_requests"
    WAITING_FOR_ACCEPT = "waiting_for_accept"
    DONE = "done"
```

### Job Status Enum
```python
class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    NEEDS_INPUT = "needs_input"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"
    DONE = "done"        # User marked as successfully done
    REJECTED = "rejected"  # User marked as rejected/not interested
```

---

## Key Services

### WorkflowOrchestrator (`services/workflow_orchestrator.py`)
Main workflow engine. Key methods:
- `run_workflow(job_id, template_id, force_search)` - Orchestrates full workflow
- Uses `LinkedInClient` directly (no wrapper classes)
- Handles workflow state persistence and resumption
- Catches `MissingHebrewNamesException` to pause for user input
- Saves contacts to database after operations
- **Abort handling**: Restores previous status and workflow_step, clears error_message

### LinkedInClient (`services/linkedin/client.py`)
Main Playwright browser automation class. Key features:
- Singleton pattern (one browser instance)
- **Persistent browser session** - Browser stays open between operations for faster subsequent calls
- Persistent context in `linkedin_data/browser_context/`
- Anti-detection with playwright-stealth
- Job queue management (only one job runs at a time)
- Abort signal handling for user cancellation
- Key methods:
  - `_get_or_create_browser()` - Reuses existing browser or creates new one
  - `close_browser()` - Explicitly close browser (for shutdown)
  - `search_company_all_degrees()` - Combined 1st/2nd/3rd degree search
  - `check_for_replies()` - Check for message replies
  - `send_message()` - Send direct message
  - `send_connection_request()` - Send connection request
- Exceptions:
  - `MissingHebrewNamesException` - Raised when Hebrew translation needed but missing
  - `WorkflowAbortedException` - Raised when user aborts workflow

### LinkedIn Module Utilities (`services/linkedin/`)
Centralized utilities for LinkedIn automation:
- **`selectors.py`** - All CSS selectors in one place (easy to update when LinkedIn changes)
- **`extractors.py`** - Person data extraction from search results
  - `clean_name()` - Removes degree indicators (• 1st, • 2nd) from names
  - `extract_person_from_search_result()` - Extracts name, headline, and **current job** from "Current:" paragraph
  - Company filtering checks both headline AND current job text
- **`browser_utils.py`** - Browser context management, retry helpers, chat modal helpers
- **`js_scripts.py`** - JavaScript evaluation strings for page interactions
- **`vip_filter.py`** - VIP title detection (CEO, CTO, founders, etc.)

### HebrewNames Service (`services/hebrew_names.py`)
Name translation. Key methods:
- `translate_name_to_hebrew(name, db)` - Async translation
- `translate_name_to_hebrew_sync(name)` - Sync version for message generator
- `is_hebrew_text(text)` - Detect Hebrew in text
- Built-in dictionary of 200+ Israeli names

### JobProcessor (`services/job_processor.py`)
Company extraction from URLs:
- Checks database for learned patterns
- Checks pre-configured platforms
- Generates regex patterns for new sites

---

## Pre-configured Job Platforms

URL pattern extraction works automatically for:
- Greenhouse (`company.greenhouse.io`)
- Lever (`jobs.lever.co/company`)
- Workday (`company.wd5.myworkdayjobs.com`)
- Ashby (`jobs.ashbyhq.com/company`)
- SmartRecruiters
- Breezy
- BambooHR
- Recruitee
- ApplyToJob
- iCIMS
- Comeet

### Known Company Career Sites (26 built-in)
These domains are recognized and map directly to company names:
- amazon.jobs, careers.cisco.com, careers.ibm.com, jobs.sap.com
- nanit.com, rapyd.net, nayax.com, papaya.com, cato networks
- fullpath.com, tailorbrands.com, global-e.com, surecomp.com
- elbit, qualitest, KMS, McCann, and more

See `KNOWN_COMPANY_SITES` in [job_parser.py](backend/app/services/job_parser.py) for full list.

For unknown sites, the system learns the pattern from user input.

---

## Frontend Components

### Jobs Page (`pages/Jobs.tsx`)
Key features:
- URL input with auto-submit on paste
- Job list with status badges
- Company input modal (for unknown sites)
- Hebrew names input form (for translations)
- Workflow action buttons:
  - **Play** (green): Start workflow / Search new people (`forceSearch=true`)
  - **Check Replies** (blue): Check for replies only (`forceSearch=false`) - shown for `waiting_for_reply` jobs
  - **Stop** (red): Abort running workflow
  - **Retry**: Retry failed job
  - **Delete**: Remove job
- Contact viewer for each job
- "Waiting for Reply/Accept" badges with time since last check
- **Dropdown filter**: Action-focused options (Run All Pending, Send All Messages, etc.) - only shows options with count > 0

### Stats (`pages/Stats.tsx`)
- Statistics cards (jobs, messages, connections, errors)
- Recent activity feed

### Templates (`pages/Templates.tsx`)
- Template list with edit/delete
- Create new template
- Preview with sample data
- Set default template

### Settings (`pages/Settings.tsx`)
- LinkedIn login status
- Login/logout buttons
- Learned site selectors management

---

## Development Setup

```bash
# 1. Start PostgreSQL only
docker-compose up -d db

# 2. Backend (port 9000)
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
playwright install chromium
alembic upgrade head
uvicorn app.main:app --reload --port 9000

# 3. Frontend (port 5173)
cd frontend
npm install
npm run dev

# 4. Open http://localhost:5173
```

**Note**: Backend does NOT auto-reload with `--reload` - restart after code changes.

---

## Environment Variables

```env
# Backend (.env)
DATABASE_URL=postgresql://user:pass@localhost:5436/jobiai
BROWSER_HEADLESS=false  # Always false (LinkedIn detects headless)
FAST_MODE=true          # true=300ms delays, false=1000ms delays
```

## Port Configuration

**Hidden mode** (`JobiAI.vbs`): Fixed ports - backend 9000, frontend 5173

**Dev mode** (`start-dev.bat`): Dynamic port allocation due to Windows/Hyper-V reserving random port ranges:
- **Backend ports**: Tries 9000-9099, then 9200-9299, then 9500-9599
- **Frontend ports**: 5173-5999
- **Database ports**: 5432-5436, then 15432-15532, then 25432-25532
- **Config file**: `.ports.json` stores the current port configuration
- **Check excluded ports**: `netsh interface ipv4 show excludedportrange protocol=tcp`

---

## Anti-Detection Strategy

- `playwright-stealth` plugin for fingerprint evasion
- Random delays between actions (300-2000ms)
- Headed browser only (headless is detected)
- Persistent browser profile (maintains cookies/session)
- **Browser stays open between missions** - more human-like, avoids repeated launches
- Human-like scrolling and clicking patterns
- Respects rate limits (~100-150 messages/day, ~50-100 connections/week)

---

## Important Implementation Details

### Message ONE Person Strategy
The bot sends a message to **ONE person** then stops and waits for a reply. This is intentional:
1. More natural/human-like behavior
2. Prevents spamming multiple people at the same company
3. User can click Play again to search for more people if no reply

### VIP Filtering
The bot skips important people who shouldn't be cold-messaged:
- CEO, CTO, CFO, COO, CMO, CPO (and "Chief X" variants)
- Founders, Co-founders
- Presidents, Chairmen
- VPs, Vice Presidents
- Managing Directors, General Managers, Owners

### Message History Detection
Before sending a message, the bot:
1. Opens the chat window with the contact
2. Checks if there's existing message history (real messages, not system notifications)
3. Filters out system messages like "accepted your invitation", "you are now connected"
4. If real history exists, closes chat and skips to next contact
5. Logs detected text for debugging (first 50 chars of each detected item)

### Email Verification Modal Handling
When LinkedIn requires email to connect with someone:
1. The "Send without a note" button is disabled
2. Bot detects this and closes the modal (clicks X)
3. Skips that person and doesn't count toward the 10-connection limit
4. Continues to next person

### Hebrew Name Translation Flow
1. When about to send message, checks if template contains Hebrew
2. If Hebrew text detected, attempts to translate recipient's name
3. If translation not found (not in dictionary or database):
   - Raises `MissingHebrewNamesException`
   - Workflow pauses at `NEEDS_HEBREW_NAMES` step
   - Frontend shows translation input form
   - User provides translation
   - Workflow resumes with translated name

### Multi-Degree Fallback
1. First searches for 1st degree connections at company
2. If found, sends ONE personalized message then stops
3. If all 1st degree already messaged (history detected), tries 2nd degree
4. If no 2nd degree with "Connect" button available, tries 3rd+ degree
5. Sends up to 10 connection requests across max 5 pages
6. Only connects to people with company name in their headline (prevents random connections)

### Pagination
- Search results pagination: max 5 pages
- Uses scroll-to-bottom + `query_selector` to find Next button
- Waits for page load after clicking Next

### Two-Button Workflow Control
- **Play button** (green, `forceSearch=true`): Searches for NEW people to message
- **Check Replies button** (blue, `forceSearch=false`): Only checks inbox for replies
- Both buttons available for `waiting_for_reply` jobs

### Reply Detection System
The "Check Replies" feature opens LinkedIn messaging and checks if any contact has replied:

1. **Panel Detection**: Before clicking the messaging button, checks if panel is already open
2. **Wait for conversations to load**: 5 second wait after opening messaging panel (critical for reliability)
3. **Close existing chats**: Closes all open message overlays at page load
4. **Conversation Search**: Finds conversations by contact name in the messaging overlay (3 retry attempts)
5. **Wait for conversation load**: 3 second wait after clicking a conversation
6. **Reply Detection**: Uses JavaScript to analyze messages in the conversation
7. **Result**: If ANY inbound message exists, marks as replied and sets `workflow_step=DONE`

**UI Feedback**: When in `waiting_for_reply` or `waiting_for_accept` state, the badge shows "No reply (checked Xm ago)" using the `last_reply_check_at` timestamp.

### Abort Behavior
When user clicks Stop/Abort:
- **Status**: Restored to previous value (not set to ABORTED)
- **Workflow step**: Restored to previous value
- **Error message**: Set to "Aborted by user"
- This allows resuming from where you left off

---

## Known Issues & TODO

### Hidden Background Mode
- [x] **Working** - `JobiAI.vbs` successfully launches backend/frontend hidden with SQLite database

### Priority 1: Rate Limiting
- [ ] Track daily message count in database
- [ ] Track weekly connection request count
- [ ] Pause/warn when approaching limits
- [ ] Detect LinkedIn rate limit responses

### Priority 2: Contacts Management
- [ ] Contacts list page with filtering
- [ ] Manual retry for failed messages
- [ ] Contact notes/tags

### Priority 3: Testing
- [ ] Integration tests with mocked LinkedIn
- [ ] Reply checking end-to-end testing
- [ ] Selector learning flow tests

---

## File Locations Quick Reference

| Component | Path |
|-----------|------|
| Main API entry | `backend/app/main.py` |
| Job endpoints | `backend/app/api/jobs.py` |
| Workflow engine | `backend/app/services/workflow_orchestrator.py` |
| LinkedIn client | `backend/app/services/linkedin/client.py` |
| Hebrew names service | `backend/app/services/hebrew_names.py` |
| Job model | `backend/app/models/job.py` |
| Contact model | `backend/app/models/contact.py` |
| Frontend API client | `frontend/src/api/client.ts` |
| Jobs page | `frontend/src/pages/Jobs.tsx` |
| Browser data | `backend/linkedin_data/browser_context/` |
| SQLite database (hidden mode) | `%LOCALAPPDATA%\JobiAI\jobiai.db` |
| Migrations | `backend/alembic/versions/` |
| Migration script | `backend/scripts/migrate_to_sqlite.py` |
| **Hidden mode launcher** | `JobiAI.vbs` |
| Hidden mode stop | `exit-JobiAI.bat` (or just close browser tab) |
