"""Constants for the Person Check-in (Grafana) integration."""

DOMAIN = "person_checkin"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_USE_SSL = "use_ssl"
CONF_VERIFY_SSL = "verify_ssl"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_HA_URL = "ha_url"
CONF_HA_TOKEN = "ha_token"
CONF_DASHBOARD_UID = "dashboard_uid"
CONF_DASHBOARD_TITLE = "dashboard_title"
CONF_DATASOURCE_UID = "datasource_uid"

DEFAULT_PORT = 3000
DEFAULT_USE_SSL = False
DEFAULT_VERIFY_SSL = True

CREATE_NEW_DASHBOARD = "__create_new__"

DATASOURCE_TYPE = "yesoreyeram-infinity-datasource"
DATASOURCE_NAME = "Person Check-in (Home Assistant)"

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}_locations"
MAX_HISTORY_POINTS = 10000

LOCATIONS_VIEW_URL = "/api/person_checkin/locations"
LATEST_VIEW_URL = "/api/person_checkin/latest"

TRACKED_DOMAIN = "person"
