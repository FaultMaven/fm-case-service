#!/usr/bin/env python3
"""Auto-generate dynamic sections of README.md from OpenAPI specifications.

SPECIAL VERSION FOR fm-auth-service (dual FastAPI apps)

This script uses a template-based approach:
- README_TEMPLATE.md contains human-editable prose (owned by developers)
- This script injects dynamic API data into placeholders (owned by automation)

Placeholders for fm-auth-service:
- <!-- GENERATED:BADGE_LINE --> : Auto-update timestamp and endpoint count
- <!-- GENERATED:MAIN_API_TABLE --> : Main app endpoint table
- <!-- GENERATED:ENTERPRISE_API_TABLE --> : Enterprise app endpoint table
- <!-- GENERATED:STATS --> : Documentation statistics footer
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Set, Any


def load_openapi_spec(filename: str) -> Dict[str, Any]:
    """Load OpenAPI spec from docs/api/{filename}"""
    spec_path = Path(__file__).parent.parent / "docs" / "api" / filename

    if not spec_path.exists():
        raise FileNotFoundError(
            f"OpenAPI spec not found at {spec_path}. "
            "Run the app to generate it first."
        )

    with open(spec_path, 'r') as f:
        return json.load(f)


def load_template() -> str:
    """Load README template file"""
    template_path = Path(__file__).parent.parent / "README_TEMPLATE.md"

    if not template_path.exists():
        raise FileNotFoundError(
            f"README template not found at {template_path}. "
            "Create README_TEMPLATE.md with placeholders."
        )

    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()


def generate_endpoint_table(spec: Dict[str, Any]) -> str:
    """Generate markdown table of endpoints"""
    endpoints = []

    for path, methods in spec.get('paths', {}).items():
        for method, details in methods.items():
            if method.lower() in ['get', 'post', 'put', 'delete', 'patch']:
                summary = details.get('summary', path)
                endpoints.append({
                    'method': method.upper(),
                    'path': path,
                    'summary': summary
                })

    # Sort endpoints: health first, then by path
    def sort_key(e):
        if e['path'] == '/health':
            return (0, '')
        return (1, e['path'])

    endpoints.sort(key=sort_key)

    # Build markdown table
    table = "| Method | Endpoint | Description |\n"
    table += "|--------|----------|-------------|\n"

    for endpoint in endpoints:
        table += f"| {endpoint['method']} | `{endpoint['path']}` | {endpoint['summary']} |\n"

    return table


def count_endpoints(spec: Dict[str, Any]) -> int:
    """Count total number of endpoints"""
    count = 0
    for path, methods in spec.get('paths', {}).items():
        for method in methods.keys():
            if method.lower() in ['get', 'post', 'put', 'delete', 'patch']:
                count += 1
    return count


def generate_badge_line(main_endpoints: int, enterprise_endpoints: int, timestamp: str) -> str:
    """Generate the auto-update badge line"""
    total = main_endpoints + enterprise_endpoints
    return f"> **Auto-generated API docs** | Last updated: **{timestamp}** | Endpoints: **{total}** ({main_endpoints} main + {enterprise_endpoints} enterprise)"


def generate_stats_footer(main_endpoints: int, enterprise_endpoints: int, timestamp: str, main_version: str, enterprise_version: str) -> str:
    """Generate documentation statistics footer"""
    total = main_endpoints + enterprise_endpoints
    return f"""**Documentation Statistics**
- Main application: {main_endpoints} endpoints
- Enterprise edition: {enterprise_endpoints} endpoints
- Total endpoints: {total}
- Last generated: {timestamp}
- Main API version: {main_version}
- Enterprise API version: {enterprise_version}
- Generator: scripts/generate_readme.py
- Template: README_TEMPLATE.md

*API sections are automatically updated on every commit. Prose sections are human-editable.*"""


def inject_content(template: str, replacements: Dict[str, str]) -> str:
    """Inject generated content into template placeholders"""
    result = template

    for placeholder, content in replacements.items():
        # Match <!-- GENERATED:PLACEHOLDER --> pattern
        pattern = rf'<!-- GENERATED:{placeholder} -->'
        result = re.sub(pattern, content, result)

    return result


def main():
    """Generate README.md by injecting dynamic content into template"""
    print("Generating README.md from template + OpenAPI specifications...")

    # Load both specs
    main_spec = load_openapi_spec("openapi-main.json")
    enterprise_spec = load_openapi_spec("openapi-enterprise.json")
    template = load_template()

    # Extract metadata
    main_info = main_spec.get('info', {})
    enterprise_info = enterprise_spec.get('info', {})
    main_version = main_info.get('version', '1.0.0')
    enterprise_version = enterprise_info.get('version', '1.0.0')

    # Generate dynamic content
    main_endpoints = count_endpoints(main_spec)
    enterprise_endpoints = count_endpoints(enterprise_spec)
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

    replacements = {
        'BADGE_LINE': generate_badge_line(main_endpoints, enterprise_endpoints, timestamp),
        'MAIN_API_TABLE': generate_endpoint_table(main_spec),
        'ENTERPRISE_API_TABLE': generate_endpoint_table(enterprise_spec),
        'STATS': generate_stats_footer(main_endpoints, enterprise_endpoints, timestamp, main_version, enterprise_version),
    }

    # Inject into template
    readme_content = inject_content(template, replacements)

    # Write README
    readme_path = Path(__file__).parent.parent / "README.md"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)

    print(f"README.md generated successfully")
    print(f"   Location: {readme_path}")
    print(f"   Main endpoints: {main_endpoints}")
    print(f"   Enterprise endpoints: {enterprise_endpoints}")
    print(f"   Timestamp: {timestamp}")
    print(f"   Template: README_TEMPLATE.md")


if __name__ == "__main__":
    main()
