#!/usr/bin/env python3
"""
Biodiversity Ontology Deployment Script - Updated for Apache Jena Fuseki
========================================================================
This script automates the deployment of the Biodiversity Ontology Generator
to a DigitalOcean droplet or any other Ubuntu-based server with Fuseki support.

Usage:
   python deploy.py --host YOUR_DROPLET_IP --user root --key /path/to/ssh_key

Requirements:
  - paramiko (pip install paramiko)
  - scp (pip install scp)   
"""

import argparse
import os
import sys
import time
import paramiko
from scp import SCPClient
from pathlib import Path
import uuid

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Deploy Biodiversity Ontology to a server with Fuseki')
    parser.add_argument('--host', required=True, help='Server IP address or hostname')
    parser.add_argument('--user', default='root', help='SSH username (default: root)')
    parser.add_argument('--port', type=int, default=22, help='SSH port (default: 22)')
    parser.add_argument('--key', help='Path to SSH private key')
    parser.add_argument('--password', help='SSH password (not recommended, use key instead)')
    parser.add_argument('--project-dir', default='.', help='Local project directory (default: current directory)')
    parser.add_argument('--server-dir', default='/var/www/biodiversity-ontology', help='Server directory for deployment')
    parser.add_argument('--domain', help='Domain name for the application (optional)')
    parser.add_argument('--setup-fuseki', action='store_true', default=True, help='Set up Apache Jena Fuseki triple store')
    parser.add_argument('--fuseki-port', type=int, default=3030, help='Port for Fuseki (default: 3030)')
    parser.add_argument('--app-port', type=int, default=8000, help='Port for the application (default: 8000)')
    parser.add_argument('--secret-key', help='Security key for Flask application (will generate if not provided)')
    parser.add_argument('--postgres-host', default='167.172.143.162', help='PostgreSQL host (default: 167.172.143.162)')
    parser.add_argument('--postgres-port', type=int, default=5432, help='PostgreSQL port (default: 5432)')
    parser.add_argument('--postgres-db', default='treekipedia', help='PostgreSQL database name')
    parser.add_argument('--postgres-user', default='postgres', help='PostgreSQL username')
    parser.add_argument('--postgres-password', default='9353jeremic', help='PostgreSQL password')
    return parser.parse_args()

def create_ssh_client(host, port, user, key_filename=None, password=None):
    """Create an SSH client connected to the remote server."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        if key_filename:
            client.connect(host, port=port, username=user, key_filename=key_filename)
        else:
            client.connect(host, port=port, username=user, password=password)
        print(f"✅ Connected to {user}@{host}:{port}")
        return client
    except Exception as e:
        print(f"❌ Failed to connect to {user}@{host}:{port}: {str(e)}")
        sys.exit(1)

def run_ssh_command(client, command, check_error=True):
    """Run a command on the remote server and print output."""
    print(f"🔄 Running: {command}")
    stdin, stdout, stderr = client.exec_command(command)
    exit_status = stdout.channel.recv_exit_status()

    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()

    if out:
        print(f"📤 Output: {out}")
    if err and check_error:
        print(f"⚠️  Error: {err}")

    if check_error and exit_status != 0:
        print(f"❌ Command failed with exit status: {exit_status}")
        if not err:
            err = "Unknown error"
        return False, err

    return True, out

def create_scp_client(ssh_client):
    """Create an SCP client for file transfers."""
    return SCPClient(ssh_client.get_transport())

def deploy_files(ssh_client, scp_client, local_dir, remote_dir, excludes=None):
    """Copy project files to the remote server."""
    if excludes is None:
        excludes = ['.git', '__pycache__', 'env', '.env', '.vscode', '.idea', '.DS_Store', '*.pyc', 'node_modules']

    # Create the remote directory if it doesn't exist
    print(f"📁 Creating remote directory: {remote_dir}")
    run_ssh_command(ssh_client, f"mkdir -p {remote_dir}", check_error=False)

    # Get all files in the project directory
    local_path = Path(local_dir).resolve()

    # Helper function to check if a path should be excluded
    def should_exclude(path):
        rel_path = path.relative_to(local_path)
        for excl in excludes:
            if excl in str(rel_path) or str(rel_path).startswith(excl) or excl in str(path):
                return True
        return False

    files_to_copy = []
    directories_to_create = set()

    for item in local_path.glob('**/*'):
        if item.is_file() and not should_exclude(item):
            rel_path = item.relative_to(local_path)
            remote_path = f"{remote_dir}/{rel_path}"
            directories_to_create.add(str(Path(remote_path).parent))
            files_to_copy.append((str(item), str(rel_path)))

    # Create required directories on the remote
    for directory in sorted(directories_to_create):
        run_ssh_command(ssh_client, f"mkdir -p '{directory}'", check_error=False)

    # Copy each file
    total_files = len(files_to_copy)
    print(f"📋 Copying {total_files} files to {remote_dir}...")

    for i, (local_file, rel_path) in enumerate(files_to_copy):
        try:
            remote_path = f"{remote_dir}/{rel_path}"
            if i % 10 == 0 or i == total_files - 1:  # Show progress every 10 files
                print(f"📄 [{i+1}/{total_files}] Copying {rel_path}")
            scp_client.put(local_file, remote_path)
        except Exception as e:
            print(f"❌ Failed to copy {local_file}: {str(e)}")

def setup_server(ssh_client, args):
    """Set up the server environment."""
    print("\n🛠️  Setting up server environment...")

    # Update and install dependencies
    run_ssh_command(ssh_client, "apt update && apt upgrade -y")
    run_ssh_command(ssh_client, "apt install -y python3 python3-pip python3-venv nginx supervisor default-jre wget curl unzip")

    # Set up a Python virtual environment
    venv_path = f"{args.server_dir}/venv"
    run_ssh_command(ssh_client, f"cd {args.server_dir} && python3 -m venv {venv_path}")

    # Install Python dependencies
    run_ssh_command(ssh_client, f"cd {args.server_dir} && {venv_path}/bin/pip install --upgrade pip")
    run_ssh_command(ssh_client, f"cd {args.server_dir} && {venv_path}/bin/pip install -r requirements.txt")
    run_ssh_command(ssh_client, f"cd {args.server_dir} && {venv_path}/bin/pip install gunicorn psycopg2-binary")

    # Set up proper permissions
    run_ssh_command(ssh_client, f"chmod 755 {args.server_dir}")
    run_ssh_command(ssh_client, f"find {args.server_dir} -name '*.py' -exec chmod 644 {{}} \\;")
    
    # Create necessary directories
    run_ssh_command(ssh_client, f"mkdir -p {args.server_dir}/uploads")
    run_ssh_command(ssh_client, f"mkdir -p {args.server_dir}/metadata")
    run_ssh_command(ssh_client, f"mkdir -p {args.server_dir}/logs")
    run_ssh_command(ssh_client, f"chmod 755 {args.server_dir}/uploads {args.server_dir}/metadata {args.server_dir}/logs")

def create_config_files(ssh_client, args):
    """Create configuration files for the application."""
    print("\n⚙️  Creating configuration files...")

    # Generate secret key if not provided
    secret_key = args.secret_key or str(uuid.uuid4().hex)

    # Create Flask configuration
    flask_config = f"""# Flask Configuration - Auto-generated
import os

class Config:
    SECRET_KEY = '{secret_key}'
    
    # Upload settings
    UPLOAD_FOLDER = '{args.server_dir}/uploads'
    METADATA_DIR = '{args.server_dir}/metadata'
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32MB
    SESSION_EXPIRY = 1800  # 30 minutes
    
    # Fuseki Configuration (Updated from Blazegraph)
    FUSEKI_ENABLED = True
    FUSEKI_BASE_URL = 'http://localhost:{args.fuseki_port}'
    FUSEKI_DATASET = 'treekipedia'
    FUSEKI_SPARQL_ENDPOINT = 'http://localhost:{args.fuseki_port}/treekipedia/sparql'
    FUSEKI_UPDATE_ENDPOINT = 'http://localhost:{args.fuseki_port}/treekipedia/update'
    FUSEKI_DATA_ENDPOINT = 'http://localhost:{args.fuseki_port}/treekipedia/data'
    
    # Legacy Blazegraph (Disabled)
    BLAZEGRAPH_ENABLED = False
    BLAZEGRAPH_ENDPOINT = 'http://localhost:9999/blazegraph/namespace/kb/sparql'
    
    # PostgreSQL Configuration
    POSTGRESQL_ENABLED = True
    POSTGRESQL_CONFIG = {{
        'db_connection': {{
            'host': '{args.postgres_host}',
            'database': '{args.postgres_db}',
            'user': '{args.postgres_user}',
            'password': '{args.postgres_password or "your_password_here"}',
            'port': {args.postgres_port}
        }}
    }}
    
    # Google Sheets (Optional)
    USE_GOOGLE_SHEETS = False
    
    # Logging
    LOG_LEVEL = 'INFO'
"""

    # Write Flask config
    with open("config_temp.py", "w") as f:
        f.write(flask_config)
    
    scp_client = create_scp_client(ssh_client)
    scp_client.put("config_temp.py", f"{args.server_dir}/deployment_config.py")
    os.remove("config_temp.py")

    # Create Fuseki configuration
    fuseki_config = f"""{{
  "service_account_file": "service_account.json",
  "spreadsheet_names": ["Treekipedia Data"],
  "triplestore_type": "fuseki",
  "fuseki": {{
    "base_url": "http://localhost:{args.fuseki_port}",
    "dataset": "treekipedia",
    "sparql_endpoint": "http://localhost:{args.fuseki_port}/treekipedia/sparql",
    "update_endpoint": "http://localhost:{args.fuseki_port}/treekipedia/update",
    "data_endpoint": "http://localhost:{args.fuseki_port}/treekipedia/data"
  }},
  "postgresql": {{
    "enabled": true,
    "db_connection": {{
      "host": "{args.postgres_host}",
      "database": "{args.postgres_db}",
      "user": "{args.postgres_user}",
      "password": "{args.postgres_password or "your_password_here"}",
      "port": {args.postgres_port}
    }}
  }},
  "auto_update_version": true,
  "version_update_user": "Deployment System (Fuseki)"
}}"""

    # Write Fuseki config
    with open("fuseki_config_temp.json", "w") as f:
        f.write(fuseki_config)
    
    scp_client.put("fuseki_config_temp.json", f"{args.server_dir}/fuseki_config.json")
    os.remove("fuseki_config_temp.json")

def setup_fuseki(ssh_client, args):
    """Set up Apache Jena Fuseki triple store."""
    if not args.setup_fuseki:
        return

    print("\n🔥 Setting up Apache Jena Fuseki...")

    # Create directory for Fuseki
    run_ssh_command(ssh_client, "mkdir -p /opt/fuseki")

    # Download Fuseki
    print("📥 Downloading Apache Jena Fuseki...")
    run_ssh_command(ssh_client, "cd /opt/fuseki && wget -q https://archive.apache.org/dist/jena/binaries/apache-jena-fuseki-4.9.0.tar.gz")
    run_ssh_command(ssh_client, "cd /opt/fuseki && tar -xzf apache-jena-fuseki-4.9.0.tar.gz")
    run_ssh_command(ssh_client, "cd /opt/fuseki && mv apache-jena-fuseki-4.9.0/* .")
    run_ssh_command(ssh_client, "cd /opt/fuseki && rm -rf apache-jena-fuseki-4.9.0*")

    # Create Fuseki configuration for treekipedia dataset
    fuseki_dataset_config = f"""@prefix :      <#> .
@prefix tdb2:  <http://jena.apache.org/2016/tdb#> .
@prefix rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix ja:    <http://jena.hpl.hp.com/2005/11/Assembler#> .
@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .
@prefix fuseki: <http://jena.apache.org/fuseki#> .

:service rdf:type fuseki:Service ;
    fuseki:name "treekipedia" ;
    fuseki:serviceQuery "sparql" ;
    fuseki:serviceUpdate "update" ;
    fuseki:serviceUpload "upload" ;
    fuseki:serviceReadWriteGraphStore "data" ;
    fuseki:dataset :dataset .

:dataset rdf:type tdb2:DatasetTDB2 ;
    tdb2:location "/opt/fuseki/databases/treekipedia" .
"""

    # Upload Fuseki dataset configuration
    with open("treekipedia_config.ttl", "w") as f:
        f.write(fuseki_dataset_config)

    scp_client = create_scp_client(ssh_client)
    run_ssh_command(ssh_client, "mkdir -p /opt/fuseki/configuration")
    scp_client.put("treekipedia_config.ttl", "/opt/fuseki/configuration/treekipedia.ttl")
    os.remove("treekipedia_config.ttl")

    # Create databases directory
    run_ssh_command(ssh_client, "mkdir -p /opt/fuseki/databases/treekipedia")
    run_ssh_command(ssh_client, "chown -R root:root /opt/fuseki")
    run_ssh_command(ssh_client, "chmod -R 755 /opt/fuseki")

    # Create systemd service for Fuseki
    fuseki_service = f"""[Unit]
Description=Apache Jena Fuseki Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/fuseki
Environment=JAVA_OPTIONS=-Xmx4g
ExecStart=/opt/fuseki/fuseki-server --config=/opt/fuseki/configuration/treekipedia.ttl --port={args.fuseki_port}
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

    # Upload Fuseki service file
    with open("fuseki_service.tmp", "w") as f:
        f.write(fuseki_service)

    scp_client.put("fuseki_service.tmp", "/etc/systemd/system/fuseki.service")
    os.remove("fuseki_service.tmp")

    # Enable and start Fuseki service
    run_ssh_command(ssh_client, "systemctl daemon-reload")
    run_ssh_command(ssh_client, "systemctl enable fuseki")
    run_ssh_command(ssh_client, "systemctl start fuseki")
    
    # Wait for Fuseki to start
    print("⏳ Waiting for Fuseki to start...")
    time.sleep(10)
    
    # Check Fuseki status
    success, output = run_ssh_command(ssh_client, "systemctl is-active fuseki", check_error=False)
    if "active" in output:
        print("✅ Fuseki started successfully!")
        
        # Test Fuseki endpoint
        success, _ = run_ssh_command(ssh_client, f"curl -s http://localhost:{args.fuseki_port}/$/ping", check_error=False)
        if success:
            print("✅ Fuseki endpoint is responding!")
        else:
            print("⚠️  Fuseki endpoint test failed")
    else:
        print("❌ Fuseki failed to start properly")

def configure_supervisor(ssh_client, args):
    """Configure Supervisor to manage the application."""
    print("\n👮 Setting up Supervisor...")

    # Create log directories
    run_ssh_command(ssh_client, "mkdir -p /var/log/biodiversity-ontology")

    # Create Supervisor configuration
    supervisor_config = f"""[program:biodiversity-ontology]
directory={args.server_dir}
command={args.server_dir}/venv/bin/gunicorn wsgi:application -w 4 -b 127.0.0.1:{args.app_port} --timeout 300 --max-requests 1000
user=root
autostart=true
autorestart=true
stopasgroup=true  
killasgroup=true
stderr_logfile=/var/log/biodiversity-ontology/err.log
stdout_logfile=/var/log/biodiversity-ontology/out.log
environment=PYTHONPATH="{args.server_dir}",FLASK_ENV="production"

[program:fuseki-monitor]
directory=/opt/fuseki
command=/bin/bash -c 'while true; do if ! systemctl is-active --quiet fuseki; then systemctl start fuseki; fi; sleep 30; done'
user=root
autostart=true
autorestart=true
stderr_logfile=/var/log/biodiversity-ontology/fuseki-monitor-err.log
stdout_logfile=/var/log/biodiversity-ontology/fuseki-monitor-out.log
"""

    # Upload Supervisor configuration
    with open("supervisor_config.tmp", "w") as f:
        f.write(supervisor_config)

    scp_client = create_scp_client(ssh_client)
    scp_client.put("supervisor_config.tmp", "/etc/supervisor/conf.d/biodiversity-ontology.conf")
    os.remove("supervisor_config.tmp")

    # Reload Supervisor
    run_ssh_command(ssh_client, "supervisorctl reread")
    run_ssh_command(ssh_client, "supervisorctl update")
    run_ssh_command(ssh_client, "supervisorctl restart biodiversity-ontology")

def configure_nginx(ssh_client, args):
    """Configure Nginx as a reverse proxy."""
    print("\n🌐 Setting up Nginx...")

    # Determine server name
    server_name = args.domain if args.domain else args.host

    # Create Nginx configuration
    nginx_config = f"""server {{
    listen 80;
    server_name {server_name};

    # Main application
    location / {{
        proxy_pass http://127.0.0.1:{args.app_port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 32M;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }}

    # Fuseki admin interface (optional, for debugging)
    location /fuseki/ {{
        proxy_pass http://127.0.0.1:{args.fuseki_port}/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}

    # Static files
    location /static {{
        alias {args.server_dir}/static;
        expires 1d;
        add_header Cache-Control "public";
    }}

    # Health check endpoint
    location /health {{
        access_log off;
        return 200 "healthy\\n";
        add_header Content-Type text/plain;
    }}
}}"""
    
    # Upload Nginx configuration
    with open("nginx_config.tmp", "w") as f:
        f.write(nginx_config)

    scp_client = create_scp_client(ssh_client)
    scp_client.put("nginx_config.tmp", "/etc/nginx/sites-available/biodiversity-ontology")
    os.remove("nginx_config.tmp")

    # Enable the site and restart Nginx
    run_ssh_command(ssh_client, "ln -sf /etc/nginx/sites-available/biodiversity-ontology /etc/nginx/sites-enabled/")
    run_ssh_command(ssh_client, "rm -f /etc/nginx/sites-enabled/default")  # Remove default site
    run_ssh_command(ssh_client, "nginx -t")
    run_ssh_command(ssh_client, "systemctl restart nginx")

def test_deployment(ssh_client, args):
    """Test the deployed application."""
    print("\n🧪 Testing deployment...")

    # Test Fuseki
    success, _ = run_ssh_command(ssh_client, f"curl -s http://localhost:{args.fuseki_port}/$/ping", check_error=False)
    if success:
        print("✅ Fuseki is responding")
    else:
        print("❌ Fuseki test failed")

    # Test Flask application
    success, _ = run_ssh_command(ssh_client, f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:{args.app_port}/", check_error=False)
    if success:
        print("✅ Flask application is responding")
    else:
        print("❌ Flask application test failed")

    # Test Nginx
    success, _ = run_ssh_command(ssh_client, f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost/", check_error=False)
    if success:
        print("✅ Nginx proxy is working")
    else:
        print("❌ Nginx proxy test failed")

def main():
    """Main deployment function."""
    args = parse_args()
    
    print("🚀 Biodiversity Ontology Deployment with Apache Jena Fuseki")
    print("=" * 60)
    print(f"Target: {args.user}@{args.host}:{args.port}")
    print(f"Server Directory: {args.server_dir}")
    print(f"App Port: {args.app_port}")
    print(f"Fuseki Port: {args.fuseki_port}")
    print("=" * 60)

    # Create SSH connection
    ssh_client = create_ssh_client(args.host, args.port, args.user, args.key, args.password)
    scp_client = create_scp_client(ssh_client)

    try:
        # Deploy files
        deploy_files(ssh_client, scp_client, args.project_dir, args.server_dir)
        
        # Setup server environment
        setup_server(ssh_client, args)
        
        # Create configuration files
        create_config_files(ssh_client, args)
        
        # Setup Fuseki
        setup_fuseki(ssh_client, args)
        
        # Configure Supervisor
        configure_supervisor(ssh_client, args)
        
        # Configure Nginx
        configure_nginx(ssh_client, args)
        
        # Test deployment
        test_deployment(ssh_client, args)
        
        print("\n🎉 DEPLOYMENT COMPLETED!")
        print("=" * 40)
        print(f"🌐 Application URL: http://{args.host}")
        print(f"🔥 Fuseki Admin: http://{args.host}/fuseki/")
        print(f"📊 PostgreSQL to Fuseki Monitor: http://{args.host}/postgres-monitor")
        print("\n📋 Next Steps:")
        print("1. Configure PostgreSQL connection if needed")
        print("2. Run initial data sync: postgres_to_fuseki_sync.py")
        print("3. Test ontology generation with sample data")
        print("4. Set up SSL certificate (optional)")
        
    except Exception as e:
        print(f"❌ Deployment failed: {str(e)}")
        sys.exit(1)
    finally:
        ssh_client.close()
        print("🔐 SSH connection closed")

if __name__ == "__main__":
    main()