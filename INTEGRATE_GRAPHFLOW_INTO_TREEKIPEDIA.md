# 🔗 Integrate GraphFlow into Treekipedia at `/admin`

## The Right Way: Proxy GraphFlow Through Express

This gives you the **full GraphFlow UI** at `https://treekipedia.silvi.earth/admin` without code duplication.

---

## Step 1: Install Proxy Middleware (1 minute)

```bash
cd treekipedia/backend
npm install http-proxy-middleware
```

---

## Step 2: Add Proxy to Express (2 minutes)

Edit `treekipedia/backend/server.js`:

```javascript
// Add near the top with other imports
const { createProxyMiddleware } = require('http-proxy-middleware');

// Add BEFORE your other routes (important!)
// This proxies /admin to GraphFlow on :5002
app.use('/admin', createProxyMiddleware({
  target: 'http://localhost:5002',
  changeOrigin: true,
  pathRewrite: {
    '^/admin': '/', // Remove /admin prefix when forwarding to GraphFlow
  },
  onProxyReq: (proxyReq, req, res) => {
    // Log proxy requests (optional)
    console.log(`[PROXY] ${req.method} ${req.url} → http://localhost:5002${req.path}`);
  },
  onError: (err, req, res) => {
    console.error('[PROXY ERROR]', err);
    res.status(500).json({
      error: 'GraphFlow admin portal is not available',
      message: 'Make sure GraphFlow is running on port 5002'
    });
  }
}));

// Your existing routes come after...
app.use('/api/species', speciesRoutes);
// etc...
```

---

## Step 3: Start GraphFlow as Background Service (5 minutes)

Make GraphFlow auto-start on your server:

### On Mac/Local (for testing):

```bash
cd "/Users/djimoserodio/Documents/Treekipedia vibes/silvi-open/graphflow-extracted/silvi-open-graphflow"

# Keep it running in background (use tmux or screen)
tmux new -s graphflow
source venv/bin/activate
PORT=5002 python3 app.py

# Detach: Ctrl+B then D
# Reattach later: tmux attach -t graphflow
```

### On Digital Ocean (production):

```bash
# SSH to server
ssh your_user@167.172.143.162

# Copy GraphFlow to server
cd /opt
sudo mkdir graphflow
# (scp files from local machine)

# Create systemd service
sudo nano /etc/systemd/system/graphflow.service
```

Paste this service file:

```ini
[Unit]
Description=Treekipedia GraphFlow Admin Portal
After=network.target postgresql.service fuseki.service

[Service]
Type=simple
User=postgres
WorkingDirectory=/opt/graphflow
Environment="PATH=/opt/graphflow/venv/bin"
EnvironmentFile=/opt/graphflow/.env
ExecStart=/opt/graphflow/venv/bin/python3 /opt/graphflow/app.py

Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable graphflow
sudo systemctl start graphflow
sudo systemctl status graphflow
```

---

## Step 4: Restart Your Treekipedia Backend

```bash
cd treekipedia/backend
npm start  # or pm2 restart treekipedia-backend
```

---

## Step 5: Test!

Now GraphFlow appears seamlessly at `/admin`:

**Local**:
- http://localhost:3000/admin (Next.js will proxy to Express)
- http://localhost:5001/admin (Express proxies to GraphFlow)

**Production**:
- https://treekipedia.silvi.earth/admin (Full GraphFlow UI!)

---

## What This Gives You

✅ **Full GraphFlow UI** - All features, exactly as designed
✅ **Single domain** - No separate ports for users
✅ **Same authentication** - Can add auth middleware before proxy
✅ **Clean URLs** - `/admin` instead of `:5002`
✅ **No code duplication** - GraphFlow stays separate but integrated

---

## Next.js Integration (Optional)

If you want `/admin` to work from Next.js frontend:

Edit `treekipedia/frontend/next.config.js`:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/admin/:path*',
        destination: 'http://localhost:5001/admin/:path*', // Proxy to Express
      },
    ];
  },
};

module.exports = nextConfig;
```

Now `/admin` works from Next.js too!

---

## Add Admin Link to Treekipedia Nav (Optional)

Edit `treekipedia/frontend/components/SpeciesHeader.tsx` or your nav component:

```typescript
// Add admin link to navigation
{user?.isAdmin && (
  <a
    href="/admin"
    className="text-emerald-300 hover:text-emerald-100 transition-colors"
  >
    Admin
  </a>
)}
```

---

## Security: Protect /admin Route

Add authentication middleware before the proxy:

```javascript
// Middleware to check if user is admin
const requireAdmin = (req, res, next) => {
  // Check wallet address or JWT token
  const userWallet = req.headers['x-wallet-address'];
  const adminWallets = process.env.ADMIN_WALLETS?.split(',') || [];

  if (!adminWallets.includes(userWallet)) {
    return res.status(403).json({ error: 'Admin access required' });
  }

  next();
};

// Apply auth before proxy
app.use('/admin', requireAdmin, createProxyMiddleware({...}));
```

---

## Environment Variables

Make sure these are set:

### GraphFlow `.env`:
```bash
PORT=5002
POSTGRES_HOST=localhost
POSTGRES_DB=treekipedia
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
FUSEKI_BASE_URL=http://localhost:3030
```

### Treekipedia Backend `.env`:
```bash
GRAPHFLOW_URL=http://localhost:5002
ADMIN_WALLETS=0xYourAdminWallet1,0xYourAdminWallet2
```

---

## Production Deployment Checklist

- [ ] GraphFlow running as systemd service on port 5002
- [ ] Express proxy configured in server.js
- [ ] Nginx NOT blocking /admin path
- [ ] Firewall allows internal 5002 traffic (localhost only)
- [ ] Admin authentication enabled
- [ ] CORS configured correctly
- [ ] GraphFlow .env has production credentials
- [ ] Test: https://treekipedia.silvi.earth/admin loads GraphFlow UI

---

## Troubleshooting

### "Cannot GET /admin"
- Make sure GraphFlow is running: `curl http://localhost:5002`
- Check proxy middleware is BEFORE other routes in server.js
- Restart Express backend

### "502 Bad Gateway"
- GraphFlow not running on port 5002
- Check: `lsof -i :5002`
- Start GraphFlow: `cd /opt/graphflow && source venv/bin/activate && PORT=5002 python3 app.py`

### Styles/Assets Not Loading
- Check pathRewrite in proxy config
- GraphFlow serves static files from `/static/` - proxy must forward this

### CORS Errors
- GraphFlow and Express must both allow CORS
- Add to GraphFlow app.py:
```python
from flask_cors import CORS
CORS(app, origins=['http://localhost:3000', 'https://treekipedia.silvi.earth'])
```

---

## Summary

**Before**: Two separate apps, different ports, confusing UX

**After**: One unified Treekipedia app with admin portal at `/admin`

**Implementation Time**: ~15 minutes

**Code Changes**: ~10 lines in server.js

**Result**: Professional, integrated admin experience! 🎯

---

Ready to implement? Just:

1. `npm install http-proxy-middleware` in backend
2. Add 10 lines to server.js
3. Done!

GraphFlow keeps running independently but appears seamlessly integrated at `/admin`.
