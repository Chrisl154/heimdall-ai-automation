"""Task templates routes for Heimdall."""
import os
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/templates", tags=["templates"])

_DEFAULT_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "react-component",
        "label": "React Component",
        "priority": "medium",
        "tags": ["frontend", "react", "typescript"],
        "max_review_iterations": 3,
        "description_template": (
            "Implement the React component described below.\n"
            "Use TypeScript, Tailwind CSS, and lucide-react for icons.\n"
            "Export the component as default.\n\n"
            "Component spec:\n{{user_spec}}"
        ),
    },
    {
        "id": "python-module",
        "label": "Python Module",
        "priority": "medium",
        "tags": ["python", "backend", "types"],
        "max_review_iterations": 3,
        "description_template": (
            "Implement the Python module described below.\n"
            "Use type annotations, docstrings, and follow PEP 8 style.\n\n"
            "Module spec:\n{{user_spec}}"
        ),
    },
    {
        "id": "api-endpoint",
        "label": "API Endpoint",
        "priority": "medium",
        "tags": ["python", "fastapi", "api"],
        "max_review_iterations": 3,
        "description_template": (
            "Implement the FastAPI endpoint described below.\n"
            "Use Pydantic models for request/response validation.\n"
            "Include error handling and appropriate status codes.\n\n"
            "Endpoint spec:\n{{user_spec}}"
        ),
    },
    {
        "id": "bug-fix",
        "label": "Bug Fix",
        "priority": "high",
        "tags": ["debugging", "fix"],
        "max_review_iterations": 5,
        "description_template": (
            "Fix the bug described below.\n"
            "Include root cause analysis in the implementation notes.\n"
            "Add tests to prevent regression.\n\n"
            "Bug description:\n{{user_spec}}"
        ),
    },
    {
        "id": "refactor",
        "label": "Refactor",
        "priority": "low",
        "tags": ["refactoring", "code-quality"],
        "max_review_iterations": 3,
        "description_template": (
            "Refactor the described code for improved clarity and performance.\n"
            "Maintain backward compatibility.\n\n"
            "Refactoring target:\n{{user_spec}}"
        ),
    },
]


def _templates_file() -> Path:
    config_dir = os.getenv("HEIMDALL_CONFIG_DIR", "config")
    return Path(config_dir) / "templates.yaml"


def _load_templates() -> list[dict[str, Any]]:
    path = _templates_file()
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, list) else []


def _get_templates() -> list[dict[str, Any]]:
    templates = _load_templates()
    if templates:
        return templates
    path = _templates_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(_DEFAULT_TEMPLATES, f, allow_unicode=True, sort_keys=False)
    return _DEFAULT_TEMPLATES


@router.get("")
def list_templates():
    return _get_templates()


@router.get("/{template_id}")
def get_template(template_id: str):
    for t in _get_templates():
        if t["id"] == template_id:
            return t
    raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
