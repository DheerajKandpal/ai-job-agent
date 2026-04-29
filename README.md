# AI Job Application Agent
> AI-powered backend system that automates job matching, resume tailoring, and application tracking in a single workflow.

## 🚀 Problem Statement
Job applications are repetitive and time-consuming.  
Applicants often lose opportunities because resumes do not align closely with each job description.  
On top of that, many workflows lack reliable tracking, making iteration and improvement difficult.

## 💡 Solution
This project automates and strengthens the application workflow by:
- Matching resumes against job descriptions with custom scoring
- Generating tailored resume content using a local LLM (Ollama)
- Generating targeted cover letters
- Applying threshold-based validation to keep outputs relevant and safe

## 🏗️ Architecture
`User Input → Matcher → Threshold → LLM → Validation → Output`

## Key Highlights
- Clean layered architecture (routes → services → schemas)
- AI integration with controlled, normalized outputs
- Production-style REST API with pagination and validation
- System map for fast code navigation (agent-friendly design)

## ⚙️ Features
- Resume–JD matching engine (custom scoring)
- Skill normalization (for example, `Postgres` vs `PostgreSQL`)
- LLM resume tailoring with anti-hallucination safeguards
- Cover letter generation aligned to JD context
- Threshold-based filtering (`5%` minimum relevance rule)
- PostgreSQL-based resume storage and version retrieval

## 🧠 Key Engineering Decisions
- Strict data integrity: no fake skills, tools, or experience
- Hybrid design: rule-based scoring + LLM rewriting
- Local LLM with Ollama to avoid per-request API cost
- Deterministic validation layer before final output acceptance

## 🛠️ Tech Stack
- Python
- PostgreSQL
- Ollama (`qwen2.5-coder`)
- Git / GitHub

## 📸 Example Output
```text
Match Score: 0.75
Matched Skills: ['python', 'sql', 'power bi']
Missing Skills: ['excel']
```

## 🔮 Future Improvements
- FastAPI backend for API-first integration
- UI dashboard for resume/job tracking and insights
- Automated job scraping pipeline
- Multi-resume strategy and role-specific profile selection
