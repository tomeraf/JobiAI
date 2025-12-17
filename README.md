# JobiAI - LinkedIn Job Application Bot

An automated bot that helps you apply for jobs by leveraging LinkedIn connections.

## Features

- **Job URL Submission**: Paste job URLs and the bot extracts company information
- **Smart Site Learning**: First time on a new job site? Show the bot where the company name is, and it remembers for next time
- **Connection Discovery**: Automatically finds your existing LinkedIn connections at the target company
- **Smart Messaging**:
  - Sends personalized, gender-appropriate messages to 1st degree connections
  - Detects existing message history and skips already-messaged contacts
  - Supports Hebrew name translations for proper gender detection
- **Multi-Degree Outreach**:
  - Messages 1st degree connections first
  - If all 1st degree already messaged, sends connection requests to 2nd degree
  - Falls back to 3rd+ degree if no 2nd degree available
- **Activity Logging**: Track all bot actions in a clean dashboard

## Tech Stack

- **Backend**: Python, FastAPI, PostgreSQL, SQLAlchemy
- **Frontend**: React, TypeScript, TailwindCSS, React Query
- **Automation**: Playwright with stealth plugin
- **Containerization**: Docker

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 18+ (for local frontend dev)
- Python 3.11+ (for local backend dev)

### Development Setup

1. **Start the database**:
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```

2. **Set up the backend**:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # or `venv\Scripts\activate` on Windows
   pip install -r requirements.txt
   playwright install chromium

   # Run migrations
   alembic upgrade head

   # Start the server
   uvicorn app.main:app --reload
   ```

3. **Set up the frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. **Open the app**: http://localhost:5173

### Production Deployment

```bash
docker-compose up -d
```

Access at http://localhost:3000

## Usage

### 1. Connect LinkedIn

1. Go to **Settings**
2. Click **Connect LinkedIn**
3. Log in to LinkedIn in the browser window that opens
4. Your session is saved automatically

### 2. Create Message Templates

1. Go to **Templates**
2. Create a new template with:
   - Male version (uses masculine Hebrew grammar)
   - Female version (uses feminine Hebrew grammar)
   - Neutral version (fallback)
3. Use `{name}` and `{company}` placeholders

Example:
```
Male:   היי {name}, ראיתי שאתה עובד ב-{company}...
Female: היי {name}, ראיתי שאת עובדת ב-{company}...
```

### 3. Submit Jobs

1. Go to **Jobs**
2. Paste a job URL
3. Click the ▶ (play) button to start the workflow
4. The bot will:
   - Extract the company name from the job URL
   - Search your LinkedIn for people at that company
   - Message 1st degree connections (skipping those already messaged)
   - Send connection requests to 2nd/3rd degree if no 1st degree available

### 4. Monitor Activity

- **Dashboard**: Overview of stats and recent activity
- **Logs**: Detailed activity history

## Rate Limits

LinkedIn has limits on automation. Default safe limits:

- ~50 connection requests per day
- ~100 messages per day

## Project Structure

```
JobiAI/
├── backend/
│   ├── app/
│   │   ├── api/           # API endpoints
│   │   ├── models/        # Database models
│   │   ├── services/      # Business logic
│   │   │   └── linkedin/  # LinkedIn automation
│   │   └── utils/         # Helpers
│   ├── alembic/           # DB migrations
│   └── browser_data/      # Saved LinkedIn session
├── frontend/
│   ├── src/
│   │   ├── api/           # API client
│   │   ├── components/    # React components
│   │   └── pages/         # Page components
│   └── ...
└── docker-compose.yml
```

## Important Notes

- **Never run in headless mode** - LinkedIn detects headless browsers
- **Respect rate limits** - Don't spam, it'll get your account flagged
- **Manual login required** - For security, you must log in manually the first time
- **Session persistence** - Your LinkedIn session is saved locally

## License

MIT
