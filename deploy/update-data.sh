#!/bin/bash
# =============================================================================
# Update salary data and restart the app
# Run this after uploading a new Excel file to /opt/wiscdata/app/data/
# =============================================================================

echo "Restarting WiscData service..."
sudo systemctl restart wiscdata

echo "Waiting for app to load data..."
sleep 5

if systemctl is-active --quiet wiscdata; then
    echo "App is running."
else
    echo "ERROR: App failed to start. Check logs:"
    echo "  sudo journalctl -u wiscdata -n 50"
fi
