#!/bin/bash
# Auto-format code script
set -e

echo "🎨 Formatting code with black..."

black .

echo "✅ Code formatted!"

