"""System navigation map for Phase 1.

This file provides a high-level map of entry points, routes, schemas, and
service handlers so engineers and agents can quickly locate code paths without
 scanning the full codebase.
Use this map as a lookup index before opening implementation files.
"""

SYSTEM_MAP = {
    "entry_point": "app/main.py",
    "routes": {
        "/match": {
            "file": "app/routes/match.py",
            "service": "app/services/match_service.py",
            "description": "Matches resume with job description",
        },
        "/tailor": {
            "file": "app/routes/tailor.py",
            "service": "app/services/tailor_service.py",
            "description": "Generates tailored resume using LLM",
        },
        "/cover-letter": {
            "file": "app/routes/cover_letter.py",
            "service": "app/services/cover_letter_service.py",
            "description": "Generates cover letter using LLM",
        },
        "/applications": {
            "file": "app/routes/applications.py",
            "service": "app/services/application_service.py",
            "description": "Manage job applications (create, list, detail, update status)",
            "endpoints": {
                "create": "POST /applications/",
                "list": "GET /applications/?limit=&offset=",
                "detail": "GET /applications/{id}",
                "update": "PATCH /applications/{id}",
            },
        },
    },
    "schemas": {
        "match": "app/schemas/match.py",
        "tailor": "app/schemas/tailor.py",
        "cover_letter": "app/schemas/cover_letter.py",
        "applications": "app/schemas/applications.py",
    },
    "services": {
        "match": "process_match",
        "tailor": "process_tailor",
        "cover_letter": "process_cover_letter",
        "applications": [
            "create_application",
            "get_applications",
            "get_application_by_id",
            "update_application_status",
        ],
    },
    "external_dependencies": [
        "matcher",
        "db_service",
        "ollama_client",
    ],
    "database": {
        "table": "applications",
        "description": "Stores job applications with status tracking and metadata",
    },
}
