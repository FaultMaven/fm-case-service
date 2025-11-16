#!/bin/bash

echo "=== Testing fm-case-service endpoints ==="
echo ""

echo "1. Health check:"
curl -s http://localhost:8003/health | python3 -m json.tool
echo ""

echo "2. Create case (auto-generated title):"
CASE1=$(curl -s -X POST http://localhost:8003/api/v1/cases \
  -H "Content-Type: application/json" \
  -H "X-User-ID: user_test123" \
  -d '{"description": "Database connection timeouts", "severity": "high", "category": "performance", "tags": ["database", "timeout"]}')
echo "$CASE1" | python3 -m json.tool
CASE1_ID=$(echo "$CASE1" | python3 -c "import sys, json; print(json.load(sys.stdin)['case_id'])")
echo "Case ID: $CASE1_ID"
echo ""

echo "3. Create case with title:"
CASE2=$(curl -s -X POST http://localhost:8003/api/v1/cases \
  -H "Content-Type: application/json" \
  -H "X-User-ID: user_test123" \
  -d '{"title": "API 500 errors", "description": "Users seeing 500 errors", "severity": "critical", "category": "error", "session_id": "session_abc123"}')
echo "$CASE2" | python3 -m json.tool
CASE2_ID=$(echo "$CASE2" | python3 -c "import sys, json; print(json.load(sys.stdin)['case_id'])")
echo ""

echo "4. Get case by ID:"
curl -s http://localhost:8003/api/v1/cases/$CASE1_ID \
  -H "X-User-ID: user_test123" | python3 -m json.tool
echo ""

echo "5. Update case:"
curl -s -X PUT http://localhost:8003/api/v1/cases/$CASE1_ID \
  -H "Content-Type: application/json" \
  -H "X-User-ID: user_test123" \
  -d '{"status": "investigating", "description": "Updated: Database connection timeouts - investigating connection pool"}' | python3 -m json.tool
echo ""

echo "6. List all cases:"
curl -s "http://localhost:8003/api/v1/cases?page=1&page_size=10" \
  -H "X-User-ID: user_test123" | python3 -m json.tool
echo ""

echo "7. Update case status:"
curl -s -X POST http://localhost:8003/api/v1/cases/$CASE1_ID/status \
  -H "Content-Type: application/json" \
  -H "X-User-ID: user_test123" \
  -d '{"status": "resolved"}' | python3 -m json.tool
echo ""

echo "8. Get cases for session:"
curl -s http://localhost:8003/api/v1/cases/session/session_abc123 \
  -H "X-User-ID: user_test123" | python3 -m json.tool
echo ""

echo "9. Delete case:"
curl -s -X DELETE http://localhost:8003/api/v1/cases/$CASE2_ID \
  -H "X-User-ID: user_test123" -w "\nHTTP Status: %{http_code}\n"
echo ""

echo "10. List cases after delete:"
curl -s "http://localhost:8003/api/v1/cases" \
  -H "X-User-ID: user_test123" | python3 -m json.tool
echo ""

echo "=== All tests completed ==="
