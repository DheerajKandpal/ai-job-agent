"""
jd_parser.py
------------
Deterministic job-description parser.

Given a raw job_description string, extracts:

    {
        "role":             str,        # inferred job title / domain
        "skills":           list[str],  # programming languages, frameworks, platforms
        "experience_level": str,        # "junior" | "mid" | "senior" | "unknown"
        "tools":            list[str],  # software tools, cloud services, databases
        "keywords":         list[str],  # domain / responsibility keywords
    }

Design principles
-----------------
- Pure regex + rule-based.  Zero network calls, zero LLM dependency.
- All lookups are case-insensitive; output is title-cased for readability.
- Deduplication is order-preserving (first occurrence wins).
- Every public function is safe to call with empty / None input.
- The module is self-contained: no imports from the rest of the app so it
  can be tested or reused independently.
"""

from __future__ import annotations

import re
from typing import TypedDict


# ---------------------------------------------------------------------------
# Output type
# ---------------------------------------------------------------------------

class ParsedJD(TypedDict):
    role: str
    skills: list[str]
    experience_level: str
    tools: list[str]
    keywords: list[str]


# ---------------------------------------------------------------------------
# Vocabulary tables
# ---------------------------------------------------------------------------

# Each entry is (canonical_name, [alias, alias, ...]).
# The canonical name is what appears in the output.
# Aliases are matched case-insensitively as whole words (or phrases).
_SKILL_VOCAB: list[tuple[str, list[str]]] = [
    # Languages
    ("Python",          ["python"]),
    ("SQL",             ["sql"]),
    ("R",               [r"\bR\b"]),
    ("Java",            ["java"]),
    ("JavaScript",      ["javascript", "js"]),
    ("TypeScript",      ["typescript", "ts"]),
    ("Go",              [r"\bgo\b", "golang"]),
    ("Rust",            ["rust"]),
    ("C++",             [r"c\+\+"]),
    ("C#",              [r"c#"]),
    ("Scala",           ["scala"]),
    ("Kotlin",          ["kotlin"]),
    ("Swift",           ["swift"]),
    ("PHP",             ["php"]),
    ("Ruby",            ["ruby"]),
    ("Shell",           ["shell", "bash", "zsh"]),
    # Data / ML frameworks
    ("Pandas",          ["pandas"]),
    ("NumPy",           ["numpy"]),
    ("Scikit-learn",    ["scikit-learn", "sklearn"]),
    ("TensorFlow",      ["tensorflow", r"\btf\b"]),
    ("PyTorch",         ["pytorch", "torch"]),
    ("Keras",           ["keras"]),
    ("XGBoost",         ["xgboost"]),
    ("LightGBM",        ["lightgbm"]),
    ("Hugging Face",    ["hugging face", "huggingface"]),
    ("LangChain",       ["langchain"]),
    ("FastAPI",         ["fastapi"]),
    ("Flask",           ["flask"]),
    ("Django",          ["django"]),
    ("Spark",           ["apache spark", r"\bspark\b"]),
    ("Kafka",           ["kafka"]),
    ("Airflow",         ["airflow"]),
    ("dbt",             [r"\bdbt\b"]),
    # Web / API
    ("REST",            ["rest api", "restful", r"\brest\b"]),
    ("GraphQL",         ["graphql"]),
    ("gRPC",            ["grpc"]),
    # ETL / pipelines
    ("ETL",             ["etl pipelines", r"\betl\b"]),
    ("Data Pipelines",  ["data pipelines", "data pipeline"]),
    # Visualisation
    ("Power BI",        ["power bi", "powerbi"]),
    ("Tableau",         ["tableau"]),
    ("Looker",          ["looker"]),
    ("Matplotlib",      ["matplotlib"]),
    ("Seaborn",         ["seaborn"]),
    ("Plotly",          ["plotly"]),
    # Statistics / maths
    ("Statistics",      ["statistics", "statistical analysis", "statistical modeling"]),
    ("Machine Learning",["machine learning", r"\bml\b"]),
    ("Deep Learning",   ["deep learning", r"\bdl\b"]),
    ("NLP",             ["natural language processing", r"\bnlp\b"]),
    ("Computer Vision", ["computer vision", r"\bcv\b"]),
    ("RAG",             [r"\brag\b", "retrieval.augmented generation"]),
    ("LLM",             [r"\bllm\b", "large language model"]),
]

_TOOL_VOCAB: list[tuple[str, list[str]]] = [
    # Databases
    ("PostgreSQL",      ["postgresql", "postgres"]),
    ("MySQL",           ["mysql"]),
    ("SQLite",          ["sqlite"]),
    ("MongoDB",         ["mongodb", "mongo"]),
    ("Redis",           ["redis"]),
    ("Elasticsearch",   ["elasticsearch", "elastic"]),
    ("Snowflake",       ["snowflake"]),
    ("BigQuery",        ["bigquery", "big query"]),
    ("Redshift",        ["redshift"]),
    ("DynamoDB",        ["dynamodb"]),
    ("Cassandra",       ["cassandra"]),
    ("ClickHouse",      ["clickhouse"]),
    # Cloud
    ("AWS",             [r"\baws\b", "amazon web services"]),
    ("GCP",             [r"\bgcp\b", "google cloud"]),
    ("Azure",           ["azure", "microsoft azure"]),
    # DevOps / infra
    ("Docker",          ["docker"]),
    ("Kubernetes",      ["kubernetes", r"\bk8s\b"]),
    ("Terraform",       ["terraform"]),
    ("GitHub Actions",  ["github actions"]),
    ("Jenkins",         ["jenkins"]),
    ("CI/CD",           ["ci/cd", "cicd", "continuous integration", "continuous deployment"]),
    # Data tools
    ("Excel",           ["excel", "microsoft excel"]),
    ("Google Sheets",   ["google sheets"]),
    ("Jupyter",         ["jupyter", "jupyter notebook"]),
    ("dbt",             [r"\bdbt\b"]),
    ("Fivetran",        ["fivetran"]),
    ("Stitch",          [r"\bstitch\b"]),
    ("Databricks",      ["databricks"]),
    ("Hadoop",          ["hadoop"]),
    ("Hive",            [r"\bhive\b"]),
    # Collaboration / project
    ("Jira",            ["jira"]),
    ("Confluence",      ["confluence"]),
    ("Notion",          ["notion"]),
    ("Slack",           ["slack"]),
    ("Git",             [r"\bgit\b"]),
    ("GitHub",          ["github"]),
    ("GitLab",          ["gitlab"]),
    # Monitoring
    ("Grafana",         ["grafana"]),
    ("Prometheus",      ["prometheus"]),
    ("Datadog",         ["datadog"]),
    ("Sentry",          ["sentry"]),
    ("New Relic",       ["new relic"]),
]

# Role titles: (canonical, [alias patterns])
_ROLE_VOCAB: list[tuple[str, list[str]]] = [
    ("Data Analyst",            ["data analyst"]),
    ("Data Scientist",          ["data scientist"]),
    ("Data Engineer",           ["data engineer"]),
    ("ML Engineer",             ["ml engineer", "machine learning engineer"]),
    ("AI Engineer",             ["ai engineer", "applied ai", "applied ml"]),
    ("Analytics Engineer",      ["analytics engineer"]),
    ("Business Analyst",        ["business analyst"]),
    ("Business Intelligence",   ["business intelligence", r"\bbi\b"]),
    ("Software Engineer",       ["software engineer", "software developer", "swe"]),
    ("Backend Engineer",        ["backend engineer", "backend developer", "back.end engineer"]),
    ("Frontend Engineer",       ["frontend engineer", "frontend developer", "front.end engineer"]),
    ("Full Stack Engineer",     ["full.?stack engineer", "full.?stack developer"]),
    ("DevOps Engineer",         ["devops engineer", "devops"]),
    ("Platform Engineer",       ["platform engineer"]),
    ("Site Reliability Engineer",["site reliability", r"\bsre\b"]),
    ("Cloud Engineer",          ["cloud engineer"]),
    ("Data QA",                 ["data qa", "data quality"]),
    ("Research Engineer",       ["research engineer", "research scientist"]),
    ("Product Manager",         ["product manager", r"\bpm\b"]),
    ("QA Engineer",             ["qa engineer", "quality assurance"]),
]

# Domain / responsibility keywords to surface
_KEYWORD_VOCAB: list[tuple[str, list[str]]] = [
    ("Data Analysis",       ["data analysis", "data analytics", "analyze data", "analysing data", "analyse data", "analyzing data", "analyze datasets", "analysing datasets", r"\banalyz", r"\banalys"]),
    ("Data Cleaning",       ["data cleaning", "data cleansing", "clean data"]),
    ("Data Transformation", ["data transformation", "transform data"]),
    ("Data Modeling",       ["data modeling", "data modelling", "data model"]),
    ("Data Visualization",  ["data visualization", "data visualisation", "visualize data"]),
    ("Reporting",           ["reporting", "build reports", "generate reports", "dashboards"]),
    ("Dashboard",           ["dashboard", "dashboards"]),
    ("API Development",     ["api development", "build apis", "develop apis", "api design"]),
    ("API Integration",     ["api integration", "integrate apis", "third.party api"]),
    ("Automation",          ["automation", "automate", "automated workflows"]),
    ("Batch Processing",    ["batch processing", "batch jobs"]),
    ("Real-time Processing",["real.time processing", "real.time data", "streaming"]),
    ("A/B Testing",         ["a/b test", "ab test", "experimentation"]),
    ("Statistical Analysis",["statistical analysis", "statistical modeling", "hypothesis testing"]),
    ("Predictive Modeling", ["predictive modeling", "predictive model", "forecasting"]),
    ("Feature Engineering", ["feature engineering"]),
    ("Model Training",      ["model training", "train models", "model development"]),
    ("Model Deployment",    ["model deployment", "deploy models", "mlops"]),
    ("Database Design",     ["database design", "schema design", "database architecture"]),
    ("Query Optimization",  ["query optimization", "query tuning", "sql optimization"]),
    ("Cloud Infrastructure",["cloud infrastructure", "cloud architecture"]),
    ("Microservices",       ["microservices", "microservice architecture"]),
    ("System Design",       ["system design", "distributed systems"]),
    ("Incident Response",   ["incident response", "on.call", "incident management"]),
    ("Documentation",       ["documentation", "technical writing"]),
    ("Code Review",         ["code review", "peer review"]),
    ("Agile",               ["agile", "scrum", "sprint"]),
    ("Cross-functional",    ["cross.functional", "cross functional", "stakeholder"]),
    ("Business Insights",   ["business insights", "business intelligence", "business metrics"]),
    ("Customer Data",       ["customer data", "user data", "customer analytics"]),
    ("Revenue Analytics",   ["revenue analytics", "revenue data", "sales analytics"]),
    ("Product Analytics",   ["product analytics", "product data", "product metrics"]),
    ("Growth Analytics",    ["growth analytics", "growth data"]),
    ("ETL",                 ["etl", "extract transform load"]),
    ("Data Governance",     ["data governance", "data quality", "data integrity"]),
    ("Security",            ["security", "authentication", "authorization", "oauth"]),
    ("Testing",             ["unit test", "integration test", "test coverage", "pytest"]),
]


# ---------------------------------------------------------------------------
# Seniority patterns  (reuse the same logic as matcher.py)
# ---------------------------------------------------------------------------

_SENIOR_RE = re.compile(
    r"\b(senior|sr\.?|lead|principal|staff|head|director|manager|"
    r"architect|expert|"
    r"[5-9]\+?\s*years?|1[0-9]\+?\s*years?)\b",
    re.IGNORECASE,
)

_JUNIOR_RE = re.compile(
    r"\b(junior|jr\.?|entry[\s\-]?level|associate|intern|graduate|trainee|"
    r"fresher|0[\s\-]\d\s*years?|1[\s\-]2\s*years?)\b",
    re.IGNORECASE,
)

_MID_RE = re.compile(
    r"\b(mid[\s\-]?level|mid[\s\-]?senior|"
    r"[2-4]\+?\s*years?)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compile_vocab(
    vocab: list[tuple[str, list[str]]],
) -> list[tuple[str, re.Pattern[str]]]:
    """
    Pre-compile each alias list into a single OR pattern.
    Returns [(canonical_name, compiled_pattern), ...].
    """
    compiled = []
    for canonical, aliases in vocab:
        # Build one pattern per alias; wrap in word boundaries unless the
        # alias already contains anchors or special constructs.
        parts = []
        for alias in aliases:
            # If the alias already has \b or is a raw regex, use as-is.
            if r"\b" in alias or r"\B" in alias or "." in alias or "+" in alias:
                parts.append(alias)
            else:
                parts.append(r"\b" + re.escape(alias) + r"\b")
        pattern = re.compile("|".join(parts), re.IGNORECASE)
        compiled.append((canonical, pattern))
    return compiled


_COMPILED_SKILLS   = _compile_vocab(_SKILL_VOCAB)
_COMPILED_TOOLS    = _compile_vocab(_TOOL_VOCAB)
_COMPILED_ROLES    = _compile_vocab(_ROLE_VOCAB)
_COMPILED_KEYWORDS = _compile_vocab(_KEYWORD_VOCAB)


def _dedupe_ordered(items: list[str]) -> list[str]:
    """Return items with duplicates removed, preserving first-occurrence order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _extract_matches(
    text: str,
    compiled_vocab: list[tuple[str, re.Pattern[str]]],
) -> list[str]:
    """
    Scan *text* against every entry in *compiled_vocab*.
    Returns a deduplicated list of canonical names that matched.
    """
    found: list[str] = []
    for canonical, pattern in compiled_vocab:
        if pattern.search(text):
            found.append(canonical)
    return _dedupe_ordered(found)


def _infer_role(text: str) -> str:
    """
    Return the best-matching role label, or "Unknown" if nothing matches.

    Strategy: scan the first 400 characters first (job titles usually appear
    at the top), then fall back to the full text.
    """
    for search_text in (text[:400], text):
        for canonical, pattern in _COMPILED_ROLES:
            if pattern.search(search_text):
                return canonical
    return "Unknown"


def _infer_experience_level(text: str) -> str:
    """
    Return "junior" | "mid" | "senior" | "unknown".

    Precedence: senior > mid > junior > unknown.
    A JD that says "3+ years" is mid; "5+ years" is senior.
    """
    is_senior = bool(_SENIOR_RE.search(text))
    is_mid    = bool(_MID_RE.search(text))
    is_junior = bool(_JUNIOR_RE.search(text))

    if is_senior:
        return "senior"
    if is_mid:
        return "mid"
    if is_junior:
        return "junior"
    return "unknown"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_job_description(job_description: str | None) -> ParsedJD:
    """
    Parse a raw job description string into structured fields.

    Parameters
    ----------
    job_description : str | None
        Raw text of the job posting.  None or empty string is handled
        gracefully — all fields return safe empty defaults.

    Returns
    -------
    ParsedJD
        A TypedDict with keys: role, skills, experience_level, tools, keywords.

    Examples
    --------
    >>> result = parse_job_description("Senior Data Analyst — Python, SQL, Tableau")
    >>> result["role"]
    'Data Analyst'
    >>> result["experience_level"]
    'senior'
    >>> "Python" in result["skills"]
    True
    """
    empty: ParsedJD = {
        "role":             "Unknown",
        "skills":           [],
        "experience_level": "unknown",
        "tools":            [],
        "keywords":         [],
    }

    if not job_description or not job_description.strip():
        return empty

    text = job_description.strip()

    return {
        "role":             _infer_role(text),
        "skills":           _extract_matches(text, _COMPILED_SKILLS),
        "experience_level": _infer_experience_level(text),
        "tools":            _extract_matches(text, _COMPILED_TOOLS),
        "keywords":         _extract_matches(text, _COMPILED_KEYWORDS),
    }


# ---------------------------------------------------------------------------
# Smoke tests — run with:  python app/services/parser/jd_parser.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json

    cases = [
        {
            "label": "Senior Data Analyst",
            "jd": (
                "Senior Data Analyst (5+ years). We are looking for a data analyst "
                "with strong Python, SQL, PostgreSQL, Power BI, and Tableau skills. "
                "Experience with ETL pipelines, data transformation, and API integration "
                "required. You will build dashboards, automate reporting, and deliver "
                "business insights to stakeholders."
            ),
        },
        {
            "label": "Junior ML Engineer",
            "jd": (
                "Junior ML Engineer — entry-level position. Must have Python, "
                "scikit-learn, TensorFlow, and basic NLP knowledge. "
                "Familiarity with Docker and AWS is a plus. "
                "You will assist in model training, feature engineering, and deployment."
            ),
        },
        {
            "label": "Backend Engineer (mid-level)",
            "jd": (
                "Backend Engineer (3+ years). Build scalable REST APIs using Python "
                "and FastAPI. Work with PostgreSQL, Redis, and Kafka. "
                "Deploy services on AWS using Docker and Kubernetes. "
                "CI/CD experience with GitHub Actions required."
            ),
        },
        {
            "label": "Data Engineer — cloud-heavy",
            "jd": (
                "Data Engineer. Design and maintain data pipelines using Apache Spark, "
                "Airflow, and dbt. Work with Snowflake, BigQuery, and Redshift. "
                "Strong SQL and Python required. Experience with Databricks preferred."
            ),
        },
        {
            "label": "Edge case: empty string",
            "jd": "",
        },
        {
            "label": "Edge case: no tech keywords",
            "jd": "We are hiring a plumber with 10 years of pipe fitting experience.",
        },
        {
            "label": "Edge case: ambiguous seniority (2-4 years = mid)",
            "jd": (
                "Data Analyst with 2-4 years of experience. "
                "SQL, Excel, and Tableau required."
            ),
        },
    ]

    for case in cases:
        result = parse_job_description(case["jd"])
        print(f"\n{'─' * 60}")
        print(f"  {case['label']}")
        print(f"{'─' * 60}")
        print(json.dumps(result, indent=2))
