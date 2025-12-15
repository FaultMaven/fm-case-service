# Hybrid Template README Upgrade

This directory contains files to upgrade from full-generation README to a hybrid template approach.

## Why Upgrade?

The previous approach generated the entire README from a Python f-string. This had drawbacks:
- **Typo friction**: To fix a typo, edit Python code instead of Markdown
- **Merge conflicts**: Harder to resolve conflicts inside multi-line strings
- **Contributor confusion**: "This file is auto-generated" discourages contributions

The hybrid approach fixes these:
- **Humans own prose** - Static sections in editable Markdown
- **Robots own data** - API tables/stats auto-injected from code
- **Best of both worlds** - Zero drift for API docs, easy edits for prose

## Files Included

```
hybrid-template-upgrade/
├── README.md                    # This guide
├── generate_readme.py           # Universal script (copy to scripts/)
├── workflow-paths-addition.txt  # What to add to generate-docs.yml
├── fm-agent-service/
│   └── README_TEMPLATE.md       # Template for fm-agent-service
├── fm-auth-service/
│   ├── README_TEMPLATE.md       # Template (dual-app version)
│   └── generate_readme.py       # Special dual-app script
├── fm-session-service/
│   └── README_TEMPLATE.md
├── fm-knowledge-service/
│   └── README_TEMPLATE.md
├── fm-evidence-service/
│   └── README_TEMPLATE.md
└── fm-api-gateway/
    └── README_TEMPLATE.md
```

## How to Apply

For each service:

### 1. Copy the template
```bash
cd /path/to/fm-{service}
cp /path/to/hybrid-template-upgrade/fm-{service}/README_TEMPLATE.md .
```

### 2. Replace generate_readme.py
```bash
# For most services:
cp /path/to/hybrid-template-upgrade/generate_readme.py scripts/

# For fm-auth-service (dual-app):
cp /path/to/hybrid-template-upgrade/fm-auth-service/generate_readme.py scripts/
```

### 3. Update workflow paths
Add this line to `.github/workflows/generate-docs.yml` in both `push.paths` and `pull_request.paths`:

```yaml
      - 'README_TEMPLATE.md'         # README template (human-editable)
```

### 4. Test locally
```bash
python scripts/generate_readme.py
```

### 5. Commit and push
```bash
git add README_TEMPLATE.md scripts/generate_readme.py .github/workflows/generate-docs.yml
git commit -m "refactor(docs): switch to hybrid template-based README generation"
git push
```

## Placeholders Reference

| Placeholder | Replaced With |
|-------------|---------------|
| `<!-- GENERATED:BADGE_LINE -->` | Timestamp and endpoint count |
| `<!-- GENERATED:API_TABLE -->` | Endpoint table from OpenAPI |
| `<!-- GENERATED:RESPONSE_CODES -->` | HTTP response codes section |
| `<!-- GENERATED:STATS -->` | Documentation statistics footer |

For fm-auth-service (dual-app):
| Placeholder | Replaced With |
|-------------|---------------|
| `<!-- GENERATED:MAIN_API_TABLE -->` | Main app endpoints |
| `<!-- GENERATED:ENTERPRISE_API_TABLE -->` | Enterprise endpoints |

## Editing the README

After applying the upgrade:

1. **To edit prose** (overview, features, etc.): Edit `README_TEMPLATE.md`
2. **To update API docs**: Just push API code changes - they auto-regenerate
3. **Workflow triggers on**: API code changes OR template changes

The generated `README.md` is still the published output, but now the template is the source for prose.
