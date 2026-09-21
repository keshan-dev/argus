"""Import guard test asserting no HTTP client is imported under app/tools/.

Mandatory check enforcing AC-1, DEC-002, and project security baseline.
Read tools must remain strictly offline and query PostgreSQL only.
"""

import ast
from pathlib import Path

FORBIDDEN_MODULES = frozenset(
    {
        "httpx",
        "requests",
        "urllib.request",
        "http.client",
        "aiohttp",
        "urllib3",
    }
)


def test_no_http_client_imported_in_tools() -> None:
    """Scan all Python files in app/tools/ and verify no forbidden HTTP client imports."""
    tools_dir = Path(__file__).resolve().parent.parent / "app" / "tools"
    assert tools_dir.is_dir(), f"Tools directory {tools_dir} does not exist"

    python_files = list(tools_dir.glob("*.py"))
    assert len(python_files) >= 7, "Expected at least 7 tool modules in app/tools/"

    violations: list[str] = []

    for file_path in python_files:
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in FORBIDDEN_MODULES:
                        if alias.name == forbidden or alias.name.startswith(f"{forbidden}."):
                            violations.append(
                                f"{file_path.name}:{node.lineno} imports '{alias.name}'"
                            )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for forbidden in FORBIDDEN_MODULES:
                        if node.module == forbidden or node.module.startswith(f"{forbidden}."):
                            violations.append(
                                f"{file_path.name}:{node.lineno} imports from '{node.module}'"
                            )

    assert not violations, (
        "Forbidden HTTP client imports found under app/tools/ (violating AC-1/DEC-002):\n"
        + "\n".join(violations)
    )
