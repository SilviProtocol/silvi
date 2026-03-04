const express = require('express');
const { Pool } = require('pg');
const { ethers } = require('ethers');
const dotenv = require('dotenv');
const path = require('path');
const cors = require('cors');
const session = require('express-session');

// Load environment variables from ../.env
dotenv.config({ path: path.join(__dirname, '../.env') });

const app = express();
const PORT = process.env.PORT || 3000;

// CORS Configuration
const corsOptions = {
  origin: function (origin, callback) {
    const allowedOrigins = [
      'http://localhost:3001',               // Next.js dev server (custom port)
      'http://localhost:3000',               // Next.js dev server (default)
      'http://localhost:8001',               // Backend dev server
      'http://localhost:8000',               // Alternative port if needed
      'http://167.172.143.162:3001',         // Current frontend deployment (HTTP)
      'https://167.172.143.162:3001',        // Current frontend deployment (HTTPS)
      'http://167.172.143.162',              // Base domain without port (HTTP)
      'https://167.172.143.162',             // Base domain without port (HTTPS)
      'https://treekipedia.silvi.earth',     // Production frontend
      'http://treekipedia.silvi.earth',      // Production frontend (HTTP)
      'https://frontend.silvi.earth',        // Alternative production frontend
      'http://frontend.silvi.earth'          // Alternative production frontend (HTTP)
    ];

    // Allow if origin is in the list or matches Vercel pattern
    if (!origin || allowedOrigins.includes(origin) || /\.vercel\.app$/.test(origin)) {
      callback(null, true);
    } else {
      callback(new Error('Not allowed by CORS'));
    }
  },
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization', 'x-api-key'],
  credentials: true,
  optionsSuccessStatus: 204
};

// Set DEBUG_CORS in .env to 'true' to allow all origins temporarily
const ALLOW_ALL_ORIGINS = process.env.DEBUG_CORS === 'true';

// Apply CORS middleware before other middleware
if (ALLOW_ALL_ORIGINS) {
  console.log('⚠️ WARNING: CORS is configured to allow ALL origins for debugging');
  app.use(cors({ origin: true, credentials: true }));
} else {
  console.log('🔒 CORS is configured with specific allowed origins');
  app.use(cors(corsOptions));
}

// Other middleware
app.use(express.json());

// Session configuration for admin authentication
app.use(session({
  secret: process.env.SESSION_SECRET || 'default-secret-change-this',
  resave: false,
  saveUninitialized: false,
  cookie: {
    secure: process.env.NODE_ENV === 'production', // Use secure cookies in production
    httpOnly: true,
    maxAge: 24 * 60 * 60 * 1000 // 24 hours
  }
}));

// Import auth middleware
const { optionalAuth } = require('./middleware/userAuth');
const { requireAdminAuth } = require('./middleware/adminAuth');

// User auth: sets req.user from Django JWT if Authorization header present
app.use(optionalAuth);

// PostgreSQL Connection
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

// Initialize research queue database table
(async () => {
  try {
    const fs = require('fs');
    const path = require('path');
    
    // Read the research queue schema SQL
    const queueSchemaSQL = fs.readFileSync(
      path.join(__dirname, 'models', 'research-queue.sql'), 
      'utf8'
    );
    
    // Execute the SQL
    await pool.query(queueSchemaSQL);
    console.log('Research queue table initialized successfully');
  } catch (error) {
    console.error('Error initializing research queue table:', error.message);
  }
})();

// Test PostgreSQL Connection
(async () => {
  try {
    const client = await pool.connect();
    console.log('PostgreSQL connected');
    client.release();
  } catch (error) {
    console.error('PostgreSQL connection error:', error.message);
  }
})();

// Ethers.js Connection to Base Sepolia
let provider;
(async () => {
  try {
    const baseSepoliaRpc = process.env.BASE_RPC_URL || `https://base-sepolia.infura.io/v3/${process.env.INFURA_API_KEY}`;
    provider = new ethers.JsonRpcProvider(baseSepoliaRpc);
    
    const blockNumber = await provider.getBlockNumber();
    console.log(`Connected to Base Sepolia (Block #${blockNumber})`);
  } catch (error) {
    console.error('Base Sepolia connection error:', error.message);
  }
})();

// Routes
app.get('/', (req, res) => {
  res.json({ message: 'Treekipedia Backend is running!' });
});

// API info endpoint
app.get('/api', (req, res) => {
  res.json({
    message: 'Welcome to Treekipedia API',
    version: '1.0.0',
    endpoints: [
      '/species - Species search and details',
      '/treederboard - User contributions leaderboard',
      '/research - AI research and NFT minting',
      '/sponsorships - Sponsorship payment tracking and webhooks',
      '/api/embeddings - AlphaEarth habitat embeddings and similarity search',
      '/api/prediction - Species prediction and recommendations (17,924 species, 44,625 habitat clusters)'
    ]
  });
});

// Import routes
const speciesRoutes = require('./controllers/species')(pool);
app.use('/species', speciesRoutes);

const treederboardRoutes = require('./controllers/treederboard')(pool);
app.use('/treederboard', treederboardRoutes);

const research = require('./controllers/research')(pool);
app.use('/research', research.router);

const sponsorshipRoutes = require('./controllers/sponsorship')(pool);
app.use('/sponsorships', sponsorshipRoutes);

const geospatialRoutes = require('./routes/geospatial')(pool);
app.use('/api/geospatial', geospatialRoutes);

const guidesRoutes = require('./routes/guides')(pool);
app.use('/api/guides', guidesRoutes);

const creditsRoutes = require('./routes/credits')(pool);
app.use('/api/credits', creditsRoutes);

const paymentsRoutes = require('./routes/payments')(pool);
app.use('/api/payments', paymentsRoutes);

// GraphFlow Admin Routes (for ontology generation, sync, SPARQL, etc.)
const adminRoutes = require('./routes/admin');
app.use('/api/admin', adminRoutes);

// AlphaEarth Embeddings Routes
const embeddingsRoutes = require('./controllers/embeddings')(pool);
app.use('/api/embeddings', embeddingsRoutes);

// Prediction Routes (species suitability and recommendations)
const predictionRoutes = require('./routes/prediction');
app.use('/api/prediction', predictionRoutes);

// ============================================
// Admin Authentication Endpoints (for monitoring)
// ============================================

// Admin login endpoint (no auth required)
app.post('/admin-api/login', (req, res) => {
  const { password } = req.body;

  // Validate password from environment variable
  if (password === process.env.ADMIN_PASSWORD) {
    // Set session flag
    req.session.isAdminAuthenticated = true;

    return res.json({
      success: true,
      message: 'Authentication successful'
    });
  } else {
    return res.status(401).json({
      success: false,
      message: 'Invalid password'
    });
  }
});

// Admin logout endpoint
app.post('/admin-api/logout', (req, res) => {
  req.session.destroy((err) => {
    if (err) {
      return res.status(500).json({
        success: false,
        message: 'Failed to logout'
      });
    }

    res.clearCookie('connect.sid');
    return res.json({
      success: true,
      message: 'Logged out successfully'
    });
  });
});

// Check authentication status
app.get('/admin-api/check-auth', (req, res) => {
  if (req.session && req.session.isAdminAuthenticated === true) {
    return res.json({
      authenticated: true
    });
  } else {
    return res.json({
      authenticated: false
    });
  }
});

// ============================================
// Admin Monitoring Endpoints
// ============================================

app.get('/admin-api/stats', (req, res) => {
  const stats = {
    serverUptime: process.uptime(),
    memoryUsage: process.memoryUsage(),
    timestamp: new Date().toISOString()
  };
  res.json(stats);
});

// Error log endpoint
app.get('/admin-api/errors', async (req, res) => {
  try {
    // Get the limit parameter, default to 50, max 500
    const limit = Math.min(parseInt(req.query.limit || '50', 10), 500);
    
    // Read the last n lines from server-error.log
    const { exec } = require('child_process');
    exec(`tail -n ${limit} ~/.pm2/logs/server-error.log`, (error, stdout, stderr) => {
      if (error) {
        console.error(`Error reading log file: ${error.message}`);
        return res.status(500).json({ error: 'Failed to read error logs' });
      }
      
      // Parse log entries
      const logEntries = stdout.split('\n')
        .filter(line => line.trim() !== '')
        .map(line => {
          // Basic parsing of log lines
          try {
            // Extract timestamp if present
            const timestamp = new Date().toISOString();
            const cleanLine = line.replace(/^\d+\|server\s+\|/, '').trim();
            
            return { 
              timestamp: timestamp, 
              message: cleanLine 
            };
          } catch (e) {
            return { 
              timestamp: new Date().toISOString(), 
              message: line, 
              parseError: true 
            };
          }
        });
      
      res.json({ 
        logs: logEntries,
        count: logEntries.length,
        limit: limit
      });
    });
  } catch (error) {
    console.error('Error fetching logs:', error);
    res.status(500).json({ error: 'Failed to fetch error logs' });
  }
});

// Simple API call counter middleware
let apiCallStats = {
  total: 0,
  byEndpoint: {},
  byDate: {}
};

app.use((req, res, next) => {
  // Skip counting admin-api calls
  if (!req.path.startsWith('/admin-api')) {
    // Increment total count
    apiCallStats.total++;
    
    // Count by endpoint
    const endpoint = req.path.split('/')[1] || 'root';
    apiCallStats.byEndpoint[endpoint] = (apiCallStats.byEndpoint[endpoint] || 0) + 1;
    
    // Count by date
    const today = new Date().toISOString().split('T')[0];
    apiCallStats.byDate[today] = (apiCallStats.byDate[today] || 0) + 1;
  }
  next();
});

// Endpoint to get API call statistics
app.get('/admin-api/call-stats', (req, res) => {
  res.json(apiCallStats);
});

// Start server
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});

// Error handling
process.on('unhandledRejection', (err) => {
  console.error('Unhandled Rejection:', err);
});

module.exports = { app, pool };