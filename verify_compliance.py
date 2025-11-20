#!/usr/bin/env python3
"""Verify microservices API endpoints match OpenAPI specification.

Compares implemented endpoints against openapi.locked.yaml specification.
"""

import yaml
import sys
from pathlib import Path
from collections import defaultdict

# Extract all paths from OpenAPI spec
def extract_spec_endpoints(openapi_file):
    """Extract all endpoints from OpenAPI spec."""
    with open(openapi_file) as f:
        spec = yaml.safe_load(f)

    endpoints = {}
    for path, methods in spec.get('paths', {}).items():
        for method in methods.keys():
            if method in ['get', 'post', 'put', 'delete', 'patch']:
                key = f"{method.upper()} {path}"
                operation_id = methods[method].get('operationId', '')
                summary = methods[method].get('summary', '')
                tags = methods[method].get('tags', [])
                endpoints[key] = {
                    'path': path,
                    'method': method.upper(),
                    'operation_id': operation_id,
                    'summary': summary,
                    'tags': tags
                }

    return endpoints

# Extract implemented endpoints from microservices
def extract_implemented_endpoints(base_dir):
    """Extract all @router decorators from microservices."""
    import re

    endpoints = {}
    services = {
        '.': 'cases',  # Current directory is fm-case-service
    }

    for service_dir, prefix in services.items():
        # For current directory, just check src/case_service/api/routes
        service_path = Path(base_dir) / 'src' / 'case_service' / 'api' / 'routes'

        if not service_path.exists():
            print(f"   ⚠️  Path not found: {service_path}")
            continue

        print(f"   📁 Scanning {service_dir}...")

        for route_file in service_path.glob('*.py'):
            if route_file.name == '__init__.py':
                continue

            content = route_file.read_text()

            # Find router prefix
            router_prefix = ''
            prefix_match = re.search(r'router\s*=\s*APIRouter\([^)]*prefix=["\']([^"\']+)["\']', content)
            if prefix_match:
                router_prefix = prefix_match.group(1)

            # Find all @router decorators
            pattern = r'@router\.(get|post|put|delete|patch)\(\s*["\']([^"\']*)["\']'
            matches = re.finditer(pattern, content)

            for match in matches:
                method = match.group(1).upper()
                path = match.group(2)

                # Construct full path
                full_path = router_prefix + path if not path.startswith('/api') else path

                # Normalize path parameters
                full_path = re.sub(r'\{([^}:]+):[^}]+\}', r'{\1}', full_path)

                key = f"{method} {full_path}"
                endpoints[key] = {
                    'service': 'fm-case-service',
                    'file': route_file.name,
                    'path': full_path,
                    'method': method
                }

    return endpoints

def main():
    print("=" * 80)
    print("FaultMaven API Endpoint Compliance Check")
    print("=" * 80)
    print()

    # Paths
    openapi_file = Path('reference/openapi.locked.yaml')
    base_dir = Path('.')

    # Extract endpoints
    print("📋 Extracting OpenAPI specification...")
    spec_endpoints = extract_spec_endpoints(openapi_file)
    print(f"   Found {len(spec_endpoints)} endpoints in spec")

    print("\n🔍 Scanning microservices implementations...")
    impl_endpoints = extract_implemented_endpoints(base_dir)
    print(f"   Found {len(impl_endpoints)} endpoints implemented")

    # Compare
    print("\n" + "=" * 80)
    print("COMPARISON RESULTS")
    print("=" * 80)

    # Group spec endpoints by service
    spec_by_service = defaultdict(list)
    for key, info in spec_endpoints.items():
        path = info['path']
        if '/auth/' in path:
            spec_by_service['auth'].append(key)
        elif '/sessions/' in path or path == '/api/v1/sessions':
            spec_by_service['sessions'].append(key)
        elif '/cases/' in path or path == '/api/v1/cases':
            spec_by_service['cases'].append(key)
        elif '/knowledge/' in path:
            spec_by_service['knowledge'].append(key)
        elif '/data/' in path:
            spec_by_service['data'].append(key)
        elif '/jobs/' in path:
            spec_by_service['jobs'].append(key)
        elif '/protection/' in path:
            spec_by_service['protection'].append(key)
        elif '/agent/' in path:
            spec_by_service['agent'].append(key)
        else:
            spec_by_service['other'].append(key)

    # Check implementation coverage
    missing = []
    implemented = []

    for key in spec_endpoints.keys():
        if key in impl_endpoints:
            implemented.append(key)
        else:
            missing.append(key)

    # Extra endpoints not in spec
    extra = []
    for key in impl_endpoints.keys():
        if key not in spec_endpoints:
            extra.append(key)

    # Print results by service
    for service in ['auth', 'sessions', 'cases', 'knowledge', 'agent', 'data', 'jobs', 'protection']:
        if service not in spec_by_service:
            continue

        service_endpoints = spec_by_service[service]
        service_impl = [k for k in service_endpoints if k in impl_endpoints]
        service_missing = [k for k in service_endpoints if k not in impl_endpoints]

        print(f"\n📦 {service.upper()} Service")
        print(f"   Spec: {len(service_endpoints)} endpoints")
        print(f"   Implemented: {len(service_impl)} / {len(service_endpoints)}")

        if service_missing:
            print(f"   ❌ Missing {len(service_missing)} endpoints:")
            for endpoint in sorted(service_missing)[:5]:  # Show first 5
                print(f"      - {endpoint}")
            if len(service_missing) > 5:
                print(f"      ... and {len(service_missing) - 5} more")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✅ Implemented: {len(implemented)} / {len(spec_endpoints)} ({len(implemented)*100//len(spec_endpoints)}%)")
    print(f"❌ Missing: {len(missing)} endpoints")
    print(f"➕ Extra (not in spec): {len(extra)} endpoints")

    if missing:
        print(f"\n❌ MISSING ENDPOINTS ({len(missing)}):")
        for endpoint in sorted(missing):
            info = spec_endpoints[endpoint]
            print(f"   {endpoint}")
            print(f"      Summary: {info['summary']}")
            print(f"      Tags: {', '.join(info['tags'])}")

    if extra:
        print(f"\n➕ EXTRA ENDPOINTS (not in spec, {len(extra)}):")
        for endpoint in sorted(extra)[:10]:  # Show first 10
            info = impl_endpoints[endpoint]
            print(f"   {endpoint}")
            print(f"      Service: {info['service']}")
            print(f"      File: {info['file']}")
        if len(extra) > 10:
            print(f"   ... and {len(extra) - 10} more")

    print("\n" + "=" * 80)

    if missing:
        print("❌ COMPLIANCE CHECK FAILED - Missing endpoints from spec")
        return 1
    else:
        print("✅ COMPLIANCE CHECK PASSED - All spec endpoints implemented")
        return 0

if __name__ == '__main__':
    sys.exit(main())
