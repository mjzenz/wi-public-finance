#!/bin/bash
# =============================================================================
# Update salary data and restart the app
#
# Usage:
#   1. Upload new Excel file to /opt/wiscdata/app/data/
#   2. Run this script
# =============================================================================

APP_DIR="/opt/wiscdata/app"
VENV="/opt/wiscdata/venv/bin/python"

echo "Building cleaned data from Excel files..."
cd $APP_DIR
$VENV build_data.py

if [ $? -ne 0 ]; then
    echo "ERROR: Data build failed. Check the output above."
    exit 1
fi

echo ""
echo "Restarting app..."
sudo systemctl restart wiscdata

sleep 3

if systemctl is-active --quiet wiscdata; then
    echo "App is running. Visit https://wiscdata.com"
else
    echo "ERROR: App failed to start. Check logs:"
    echo "  sudo journalctl -u wiscdata -n 50"
fi
