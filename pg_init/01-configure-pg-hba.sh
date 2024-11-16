#!/bin/bash
set -e

# Write the new pg_hba.conf
cat > "$PGDATA/pg_hba.conf" << EOC
# TYPE  DATABASE        USER            ADDRESS                 METHOD

# IPv4 local connections:
host    all             all             127.0.0.1/32            trust
host    all             all             172.16.0.0/12           trust
host    all             all             192.168.0.0/16          trust
host    all             all             0.0.0.0/0               trust

# IPv6 local connections:
host    all             all             ::1/128                 trust

# Allow replication connections
host    replication     all             127.0.0.1/32            trust
EOC

# Set proper permissions
chmod 600 "$PGDATA/pg_hba.conf"