#!/bin/bash
# =============================================================================
# UW-Madison Salary Explorer — EC2 Setup Script
# Run this on a fresh Amazon Linux 2023 or Ubuntu 22.04 instance
# =============================================================================
set -e

APP_DIR="/opt/wiscdata"
APP_USER="wiscdata"
DOMAIN="wiscdata.com"

echo "=== 1. System packages ==="
if command -v dnf &> /dev/null; then
    # Amazon Linux 2023
    sudo dnf update -y
    sudo dnf install -y python3.11 python3.11-pip nginx git certbot python3-certbot-nginx
    PYTHON=python3.11
elif command -v apt &> /dev/null; then
    # Ubuntu 22.04
    sudo apt update && sudo apt upgrade -y
    sudo apt install -y python3 python3-pip python3-venv nginx git certbot python3-certbot-nginx
    PYTHON=python3
fi

echo "=== 2. Create app user and directory ==="
sudo useradd --system --shell /bin/false $APP_USER 2>/dev/null || true
sudo mkdir -p $APP_DIR
sudo chown $APP_USER:$APP_USER $APP_DIR

echo "=== 3. Clone repo and install dependencies ==="
sudo -u $APP_USER git clone https://github.com/mjzenz/wi-public-finance.git $APP_DIR/app \
    || echo "Repo already exists, pulling latest..."
cd $APP_DIR/app
sudo -u $APP_USER git pull origin master 2>/dev/null || true

# Create virtual environment
sudo -u $APP_USER $PYTHON -m venv $APP_DIR/venv
sudo -u $APP_USER $APP_DIR/venv/bin/pip install --upgrade pip
sudo -u $APP_USER $APP_DIR/venv/bin/pip install -r requirements.txt

echo "=== 4. Install systemd service ==="
sudo cp $APP_DIR/app/deploy/wiscdata.service /etc/systemd/system/wiscdata.service
sudo systemctl daemon-reload
sudo systemctl enable wiscdata
sudo systemctl start wiscdata

echo "=== 5. Configure Nginx ==="
sudo cp $APP_DIR/app/deploy/nginx-wiscdata.conf /etc/nginx/conf.d/wiscdata.conf
# Remove default config if present
sudo rm -f /etc/nginx/conf.d/default.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

echo "=== 6. SSL Certificate (Let's Encrypt) ==="
echo "Run this after DNS is pointed to this server:"
echo "  sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN"
echo ""
echo "Certbot will auto-renew via systemd timer."

echo ""
echo "=== Setup complete ==="
echo "App running at http://$DOMAIN (HTTPS after certbot)"
echo ""
echo "To update data files:"
echo "  scp new_salary_file.xlsx ec2-user@$DOMAIN:/opt/wiscdata/app/data/"
echo "  sudo systemctl restart wiscdata"
