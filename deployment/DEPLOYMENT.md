# Treekipedia Production Deployment Guide

## QUick Start (Docker)

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Edit .env with your copnfiguration
nano .env

#3. Start with Docker Compose
docker-compose up -d

# 4. Check logs
docker-compose logs -f web
```

Access at: http://localhost:5001

## Manual Deployment (Linux Server)

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Apache Jena Fuseki
- Nginx (recommended)

### Step 1: Clone & Setup

```bash
# Clone repository
git clone <your-repo-url> /var/www/treekipedia
cd /var/www/treekipedia

# Create virtual environment
python3 -m venv myenv
source myenv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-occurrence.txt
pip install gunicorn
```

### Step 2: Configure

```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

### Step 3: Database Setup

```bash
# Create PostgreSQL database
sudo -u postgres createdb treekipedia

# Run migrations if any
python scripts/migrate.py
```

### Step 4: Start Service

#### Option A: Systemd (Recommended)

```bash
# Copy service file
sudo cp deployment/treekipedia.service /etc/systemd/system/

# Edit paths in service file
sudo nano /etc/systemd/system/treekipedia.service

# Enable and start
sudo systemctl enable treekipedia
sudo systemctl start treekipedia
sudo systemctl status treekipedia
```

### Option B: Direct Start

```bash
./start-production.sh
```

### Step 5: Nginx Configuration (Optional)

```nginx
server {
    listen 80;
    server_name treekipedia.yourdomain.com;

    client_max_body_size 2G;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
    }

    location /static {
        alias /var/www/treekipedia/static;
        expires 30d;
    }
}
```

## Environment Variables

See `.env.example` for all available configuration options.

### Required Variables
- `SECRET_KEY` - Flask secret key
- `POSTGRES_*` - Database credentials
- `FUSEKI_*` - Triplestore configuration

### Optional Variables
- `AWS_*` - For S3 occurrence data storage
- `MAX_UPLOAD_SIZE_MB` - File upload limit (default: 2048)

## Monitoring

### Health Check
```bash
curl http://localhost:5001/api/system-status
```

### Logs
```bash
# Application logs
tail -f logs/error.log
tail -f logs/access.log

# Docker logs
docker-compose logs -f
```

## Backup

### Database
```bash
pg_dump treekipedia > backup_$(date +%Y%m%d).sql
```

### Occurrence Data
```bash
tar -czf occurrence_backup_$(date +%Y%m%d).tar.gz data/occurrences/
```

### Ontologies
```bash
tar -czf ontology_backup_$(date +%Y%m%d).tar.gz generated_ontologies/
```

## Security Checklist

- [ ] Change default `SECRET_KEY`
- [ ] Use string database passwords
- [ ] Enable HTTPS (use Let's Encrypt)
- [ ] Configure firewall (ufw/iptables)
- [ ] Secure service account credentials
- [ ] Regular backups
- [ ] Monitor logs
- [ ] Keep dependencies updated

## Troubleshooting

### Application won't start
```bash
# Check logs
journalctl -u treekipedia -n 50

# Test configuration
python -c "from app import create_app; app = create_app(); print('OK')"
```

### Database connection fails
```bash
# Test PostgreSQL connection
psql -h localhost -U postgres -d treekipedia
```

### High memory usage
```bash
# Reduce gunicorn workers
export WORKERS=2

# Restart service
sudo systemctl restart treekipedia
```

# Scaling

### Horizontal Scaling
Use multiple gunicorn workers and load balancer (Nginx/HAProxy)

### Database Optimization
- Enable connection pooling
- Add appropriate indexes
- Regular VACUUM

## Caching
- Add Redis for session storage
- Enable CDN for static assets

## Updates

```bash
# Pull latest code
git pull origin main

# Update dependencies
pip install -r requirements.txt --upgrade

# Restart service
sudo systemctl restart treekipedia