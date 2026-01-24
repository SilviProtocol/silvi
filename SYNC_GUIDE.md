# PostgreSQL to Fuseki Sync Guide

## ✅ Problem Fixed!

The issue was that the `fuseki_config.json` file was missing. This file has now been created with your PostgreSQL and Fuseki credentials.

## Current Fuseki Status

After the test sync:
- **Total Triples (Named Graphs)**: 389,536 triples
- **Total Triples (Default Graph)**: 6,215 triples
- **Unique Entities**: 3,407 entities

The test sync successfully pushed 253 records (users + countries) = 116,292 new triples.

## How to Sync Data from PostgreSQL to Fuseki

### Option 1: Using the Web UI (Recommended)

1. Start your Flask app:
   ```bash
   python app.py
   ```

2. Navigate to: http://localhost:5001

3. Click on **"PostgreSQL Monitor"** (under the PostgreSQL integration card)

4. On the PostgreSQL Monitor page, you can:
   - **Sync All Tables**: Click "Sync All Tables to Fuseki" button
   - **Sync Individual Table**: Click the sync button next to any table in the list
   - **View Fuseki Stats**: See real-time triple count and entity count

### Option 2: Using Command Line

#### Test Connections Only
```bash
python3 scripts/postgres_to_fuseki_sync.py --test
```

#### Sync Specific Tables
```bash
# Sync just the species table
python3 scripts/postgres_to_fuseki_sync.py --tables species

# Sync multiple tables
python3 scripts/postgres_to_fuseki_sync.py --tables users countries species

# Sync with custom batch size
python3 scripts/postgres_to_fuseki_sync.py --tables species --batch-size 500
```

#### Sync All Tables
```bash
python3 scripts/postgres_to_fuseki_sync.py
```

## Important Notes

### Large Tables (species, geohash_species_tiles)

Your database has some very large tables:
- `geohash_species_tiles`: 5,786,835 rows
- `species`: 67,927 rows

For these tables:
- Use smaller batch sizes (e.g., 500-1000)
- Consider syncing during off-peak hours
- Monitor memory usage

### Named Graphs

The sync creates data in **named graphs** with timestamps. For example:
- `http://treekipedia.org/countries/20251215_205202_batch_1`
- `http://treekipedia.org/users/20251215_205230_batch_1`

To query ALL data (including named graphs), use:
```sparql
SELECT * WHERE {
  GRAPH ?g { ?s ?p ?o }
}
LIMIT 100
```

### Configuration Files

The sync uses two configuration sources:
1. **fuseki_config.json** - Main configuration (credentials, endpoints)
2. **.env file** - Environment variables (also contains Fuseki config)

Both are now properly configured.

## Accessing Fuseki

- **Web UI**: http://167.172.143.162:3030
- **SPARQL Endpoint**: http://167.172.143.162:3030/treekipedia/sparql
- **Update Endpoint**: http://167.172.143.162:3030/treekipedia/update
- **Dataset**: treekipedia

**Credentials**:
- Username: `treekipedia`
- Password: `treekipedia@silvi`

## Example SPARQL Queries

### Count all triples
```sparql
SELECT (COUNT(*) as ?count) WHERE {
  GRAPH ?g { ?s ?p ?o }
}
```

### Find all species
```sparql
SELECT * WHERE {
  GRAPH ?g {
    ?species a <http://treekipedia.org/ontology/Species> .
    ?species ?property ?value .
  }
}
LIMIT 100
```

### Find all users
```sparql
SELECT * WHERE {
  GRAPH ?g {
    ?user a <http://treekipedia.org/ontology/Users> .
    ?user <http://treekipedia.org/property/username> ?username .
  }
}
```

## Troubleshooting

### If sync fails:

1. **Check connections**:
   ```bash
   python3 scripts/postgres_to_fuseki_sync.py --test
   ```

2. **Check Fuseki is running**:
   ```bash
   curl http://167.172.143.162:3030/$/ping
   ```

3. **Check PostgreSQL is accessible**:
   ```bash
   psql -h 167.172.143.162 -U postgres -d treekipedia -c "SELECT version();"
   ```

4. **View logs**:
   Check the console output for detailed error messages.

## Next Steps

Now that the basic sync is working, you can:

1. **Sync your main species data**:
   ```bash
   python3 scripts/postgres_to_fuseki_sync.py --tables species --batch-size 1000
   ```

2. **Set up automated syncs**: Create a cron job or scheduled task to sync data regularly

3. **Query your data**: Use the Fuseki web UI or SPARQL endpoint to query your biodiversity data

4. **Integrate with your application**: Update your app to query Fuseki for species data

## Support

For issues or questions:
- Check the logs in the console output
- Review the PostgreSQL Monitor page for connection status
- Use the test mode to verify connections before syncing
