#!/bin/bash
# Setup script that doesn't require Git authentication
# Run this on your DigitalOcean droplet

set -e

echo "=== Ceefax Station Website - Setup (No Git) ==="
echo ""

# Step 1: Update and install
echo "[1/8] Installing dependencies..."
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv nginx sqlite3 certbot python3-certbot-nginx ufw wget unzip

# Step 2: Create directory structure
echo "[2/8] Creating directories..."
mkdir -p /root/ceefax_station
cd /root/ceefax_station

# Step 3: Download repository as ZIP (no auth needed)
echo "[3/8] Downloading repository..."
wget -q https://github.com/thaum-labs/ceefax_station/archive/refs/heads/main.zip -O repo.zip
unzip -q repo.zip
mv ceefax_station-main/* .
mv ceefax_station-main/.* . 2>/dev/null || true
rm -rf ceefax_station-main repo.zip

# Step 4: Setup Python environment
echo "[4/8] Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r ceefax/requirements.txt

# Step 5: Create .env file
echo "[5/8] Creating .env file..."
cat > .env << 'EOF'
CEEFAXWEB_HOST=127.0.0.1
CEEFAXWEB_PORT=8088
CEEFAXWEB_DB=/root/ceefax_station/ceefaxweb/ceefaxweb.sqlite3
CEEFAXWEB_UPLOAD_TOKEN=XjouK8GEhhczBsidV70PbThv3iNlmGBawAAmYx0BsaI
EOF
chmod 600 .env

# Step 6: Create systemd service
echo "[6/8] Creating systemd service..."
cat > /etc/systemd/system/ceefaxweb.service << 'EOF'
[Unit]
Description=Ceefax Station Web Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/ceefax_station
Environment="PATH=/root/ceefax_station/venv/bin"
EnvironmentFile=/root/ceefax_station/.env
ExecStart=/root/ceefax_station/venv/bin/python -m ceefaxweb
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ceefaxweb

# Step 7: Configure Nginx
echo "[7/8] Configuring Nginx..."
cat > /etc/nginx/sites-available/ceefaxstation << 'EOF'
server {
    listen 80;
    server_name ceefaxstation.com www.ceefaxstation.com;

    location / {
        proxy_pass http://127.0.0.1:8088;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

ln -sf /etc/nginx/sites-available/ceefaxstation /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

# Step 8: Configure firewall and start
echo "[8/8] Configuring firewall and starting service..."
ufw --force enable
ufw allow OpenSSH
ufw allow 'Nginx Full'
systemctl start ceefaxweb
sleep 2

echo ""
echo "=== Setup Complete ==="
echo ""
systemctl status ceefaxweb --no-pager
echo ""
echo "Next: Configure DNS in Namecheap, then run:"
echo "certbot --nginx -d ceefaxstation.com -d www.ceefaxstation.com"

