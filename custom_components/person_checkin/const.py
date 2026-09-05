"""Constants for the Person Check-in (Grafana) integration."""

DOMAIN = "person_checkin"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_USE_SSL = "use_ssl"
CONF_VERIFY_SSL = "verify_ssl"
CONF_API_TOKEN = "api_token"
CONF_DASHBOARD_UID = "dashboard_uid"
CONF_DASHBOARD_TITLE = "dashboard_title"
CONF_DATASOURCE_UID = "datasource_uid"

CONF_PG_HOST = "pg_host"
CONF_PG_PORT = "pg_port"
CONF_PG_DATABASE = "pg_database"
CONF_PG_USER = "pg_user"
CONF_PG_PASSWORD = "pg_password"
CONF_PG_SSLMODE = "pg_sslmode"

DEFAULT_PORT = 3000
DEFAULT_USE_SSL = False
DEFAULT_VERIFY_SSL = True
DEFAULT_PG_PORT = 5432
DEFAULT_PG_SSLMODE = "disable"
PG_SSLMODES = ["disable", "allow", "prefer", "require", "verify-ca", "verify-full"]

CREATE_NEW_DASHBOARD = "__create_new__"

DATASOURCE_TYPE = "postgres"

TABLE_NAME = "person_checkin_locations"

# In-memory retry buffer for rows that failed to insert (e.g. Postgres briefly
# unreachable across VMs). Capped so a prolonged outage can't grow memory forever.
MAX_PENDING_POINTS = 500
RETRY_INTERVAL_SECONDS = 60

TRACKED_DOMAIN = "person"
