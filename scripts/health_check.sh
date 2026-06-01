#!/bin/bash

# Check PostgreSQL port
if nc -z localhost 5432 2>/dev/null; then
    echo "✓ PostgreSQL is running on port 5432"
else
    echo "✗ Failed: PostgreSQL port 5432 is not reachable"
    exit 1
fi

# Check Redis port
if nc -z localhost 6379 2>/dev/null; then
    echo "✓ Redis is running on port 6379"
else
    echo "✗ Failed: Redis port 6379 is not reachable"
    exit 1
fi

# Check PostgreSQL database access
if docker exec berp_postgres pg_isready -U recitation -d recitation > /dev/null 2>&1; then
    echo "✓ Database 'recitation' is accessible"
else
    echo "✗ Failed: Database 'recitation' is not accessible"
    exit 1
fi

exit 0
