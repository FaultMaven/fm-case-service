# README Template Extraction Summary

Successfully created README_TEMPLATE.md files for 5 services by extracting static prose from their generate_readme.py files.

## Files Created

1. **fm-auth-service/README_TEMPLATE.md**
   - Special handling: TWO API table placeholders (MAIN and ENTERPRISE)
   - Placeholders:
     - `<!-- GENERATED:BADGE_LINE -->`
     - `<!-- GENERATED:MAIN_API_TABLE -->`
     - `<!-- GENERATED:ENTERPRISE_API_TABLE -->`
     - `<!-- GENERATED:STATS -->`

2. **fm-session-service/README_TEMPLATE.md**
   - Standard service template
   - Placeholders:
     - `<!-- GENERATED:BADGE_LINE -->`
     - `<!-- GENERATED:API_TABLE -->`
     - `<!-- GENERATED:RESPONSE_CODES -->`
     - `<!-- GENERATED:STATS -->`

3. **fm-knowledge-service/README_TEMPLATE.md**
   - Standard service template
   - Placeholders:
     - `<!-- GENERATED:BADGE_LINE -->`
     - `<!-- GENERATED:API_TABLE -->`
     - `<!-- GENERATED:RESPONSE_CODES -->`
     - `<!-- GENERATED:STATS -->`

4. **fm-evidence-service/README_TEMPLATE.md**
   - Standard service template
   - Placeholders:
     - `<!-- GENERATED:BADGE_LINE -->`
     - `<!-- GENERATED:API_TABLE -->`
     - `<!-- GENERATED:RESPONSE_CODES -->`
     - `<!-- GENERATED:STATS -->`

5. **fm-api-gateway/README_TEMPLATE.md**
   - Special handling: Hardcoded proxy routes table (not generated)
   - Placeholders:
     - `<!-- GENERATED:BADGE_LINE -->`
     - `<!-- GENERATED:API_TABLE -->`
     - `<!-- GENERATED:RESPONSE_CODES -->`
     - `<!-- GENERATED:STATS -->`

## Changes Applied

1. ✅ Extracted static prose from f-strings in generate_readme.py files
2. ✅ Replaced dynamic badge/timestamp line with `<!-- GENERATED:BADGE_LINE -->`
3. ✅ Replaced endpoint tables with appropriate placeholders
4. ✅ Replaced response codes section with `<!-- GENERATED:RESPONSE_CODES -->`
5. ✅ Replaced footer statistics with `<!-- GENERATED:STATS -->`
6. ✅ Removed escaped braces from JSON examples ({{ → {)
7. ✅ Preserved all static prose, examples, and documentation

## Location

All templates created in: `/home/user/fm-case-service/hybrid-template-upgrade/{service-name}/README_TEMPLATE.md`
