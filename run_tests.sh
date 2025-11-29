#!/bin/bash
set -e

# Build and run tests
docker-compose build
docker-compose up --exit-code-from app

# Check test results
if [ $? -eq 0 ]; then
    echo "All tests passed!"
else
    echo "Some tests failed."
    exit 1
fi