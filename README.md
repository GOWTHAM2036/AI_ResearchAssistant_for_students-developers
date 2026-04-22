# 🚀 AI Research Crew — Multi-Agent Agentic Workflow

A fully autonomous **5-agent pipeline** that goes beyond chat into real-world execution. Built for hackathon excellence.

## Architecture

```
User Input → Manager Agent → Research Agent → Analysis Agent → Writer Agent → Delivery Agent → Output
                (Reasoning)     (Perception)    (Reasoning)      (Action)       (Action)
```

| Agent | Pillar | What It Does |
|-------|--------|-------------|
| 🧠 **Manager** | Reasoning | Reads the task, generates a JSON research plan, delegates to sub-agents |
| 🔍 **Researcher** | Perception | Calls DuckDuckGo web search API — browses the web autonomously |
| 📊 **Analyst** | Reasoning | Self-corrects with JSON fallbacks, extracts 5 key insights + confidence score |
| ✍️ **Writer** | Action | Drafts a full HTML technical briefing with 5 structured sections |
| 📧 **Delivery** | Action | Sends the final briefing via SMTP email |

## The Agentic Standard

- **Perception** — Research Agent searches real-time web data
- **Reasoning** — Manager plans & delegates; Analyst synthesizes with confidence scoring
- **Action** — Writer produces deliverables; Delivery Agent distributes via email
- **Self-Correction** — 3-tier resilience: primary → retry → fallback (pipeline never breaks)

## Quick Start

### 1. Setup
```bash
# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure
```bash
# Copy the example env file
copy .env.example .env    # Windows
cp .env.example .env      # Mac/Linux

# Edit .env and add your Groq API key (free at console.groq.com)
```

### 3. Run
```bash
python -m backend.app
```

Open **http://localhost:5000** in your browser.

### 4. Use
1. Enter a research topic (e.g., "EV battery technology 2026")
2. Optionally add an email address for delivery
3. Click **Deploy Crew ↗**
4. Watch agents work in real-time in the activity feed
5. View the generated HTML briefing below

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | Groq (Llama 3.3 70B) — free, blazing fast |
| Web Search | DuckDuckGo — no API key required |
| Backend | Flask + SSE streaming |
| Frontend | Vanilla HTML/CSS/JS + Glassmorphism UI |
| Email | SMTP (Gmail App Password) |

## Impact

A task that takes a human analyst **45–90 minutes** (research → synthesize → write → distribute) runs in **under 2 minutes**.

## License

MIT
