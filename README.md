# IDEONIX – AI-Powered Volunteer Coordination Platform

## Setup Instructions (VS Code)

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set your Anthropic API Key
**Windows (Command Prompt):**
```cmd
set ANTHROPIC_API_KEY=your_api_key_here
```
**Mac/Linux:**
```bash
export ANTHROPIC_API_KEY=your_api_key_here
```
Get your free API key at: https://console.anthropic.com

### 3. Run the app
```bash
python app.py
```

### 4. Open in browser
```
http://localhost:5000
```

---

## How to Demo (Hackathon Flow)

1. **Sign up as NGO** (e.g., "Hope Foundation")
2. **Post 3 tasks:**
   - Food distribution in rural area (High urgency, skills: social work)
   - Medical camp for elderly (High urgency, skills: medical)
   - Teaching children (Medium, skills: teaching)

3. **Sign up as Volunteers** (3 separate accounts):
   - Rahul | skills: teaching | availability: weekends
   - Ankit | skills: medical student | availability: weekdays
   - Sanya | skills: social work | availability: anytime

4. **Log back in as NGO → click "🤖 AI Match All Tasks"**
   - Gemini AI will match: Sanya→Food, Ankit→Medical, Rahul→Teaching

5. **Log in as each volunteer** to see their AI-matched task with score + reason

---

## Project Structure
```
ideonix/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── ideonix.db          # SQLite database (auto-created)
└── templates/
    ├── base.html       # Layout with navigation
    ├── index.html      # Landing page
    ├── login.html      # Login form
    ├── signup.html     # Signup (NGO + Volunteer)
    ├── dashboard_ngo.html       # NGO dashboard with AI matching
    ├── dashboard_volunteer.html # Volunteer matches view
    ├── new_task.html   # Post a task
    ├── tasks.html      # Browse all tasks
    └── analytics.html  # Impact statistics
```

## Features
- ✅ User Login / Signup (NGO & Volunteer roles)
- ✅ NGO posts community needs with urgency levels
- ✅ Volunteer registers with skills & availability
- ✅ AI Smart Matching (Claude API) — scored with explanations
- ✅ Volunteer can accept matched tasks
- ✅ Analytics dashboard
- ✅ SQLite database (no setup needed)
