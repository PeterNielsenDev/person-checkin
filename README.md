# Person Check-in (Grafana)

Custom Home Assistant-integration (HACS) der sporer dine `person.*`-entiteters lokation og
viser dem live på et Grafana-dashboard (kort + historik-tabel).

## Sådan virker det

1. Integrationen lytter på state-ændringer for alle `person.*`-entiteter i Home Assistant
   og gemmer lokation (lat/lon, GPS-nøjagtighed, status) lokalt på disk.
2. Den eksponerer to JSON-endpoints via Home Assistants egen API:
   - `/api/person_checkin/latest` – seneste kendte position pr. person
   - `/api/person_checkin/locations` – fuld historik
3. Under opsætning opretter integrationen selv (via Grafanas HTTP API, med det
   brugernavn/password du indtaster) en datasource i Grafana af typen **Infinity**
   (`yesoreyeram-infinity-datasource`), som peger tilbage på din Home Assistant.
4. Den opretter derefter et **Geomap**-panel (kort med markører) og et tabelpanel med
   historik, enten på et nyt dashboard eller føjet til et eksisterende du vælger.

Grafana er i sig selv ikke en database, så for at kunne vise live/historiske lokationer
uden at du skal sætte InfluxDB eller lignende op separat, bruges Home Assistant selv som
datakilde via Infinity-pluginnet.

## Forudsætninger

- En kørende Grafana-server (lokal IP), med en bruger der har rettigheder til at oprette
  datasources og dashboards (typisk Admin eller Editor).
- **Infinity-datasource pluginnet** skal være installeret i Grafana:
  ```
  grafana-cli plugins install yesoreyeram-infinity-datasource
  ```
  (eller via Grafana UI → Administration → Plugins). Integrationen kan ikke installere
  Grafana-plugins for dig.
- Et **Long-Lived Access Token** fra din Home Assistant-brugerprofil (Profil → nederst →
  "Long-Lived Access Tokens" → Opret token). Dette bruges af Grafana til at hente data fra
  Home Assistant.
- Home Assistant skal være net-tilgængelig fra Grafana-serveren (angiv den URL Grafana kan
  nå HA på, fx `http://192.168.1.50:8123`).

## Installation via HACS

1. HACS → tre prikker øverst til højre → "Custom repositories".
2. Tilføj `https://github.com/PeterNielsenDev/person-checkin` som type "Integration".
3. Installer "Person Check-in (Grafana)" og genstart Home Assistant.
4. Gå til **Indstillinger → Enheder & tjenester → Tilføj integration** og søg efter
   "Person Check-in".

## Opsætning (guide i UI)

1. **Grafana-forbindelse**: IP/hostname, port (default 3000), HTTP/HTTPS, brugernavn og
   adgangskode. Integrationen tester login med det samme.
2. **Forbindelse tilbage til Home Assistant**: den URL Grafana skal bruge for at nå din
   HA-instans, samt dit Long-Lived Access Token.
3. **Vælg dashboard**: vælg et eksisterende dashboard som lokations-panelerne skal føjes
   til, eller vælg "➕ Opret nyt dashboard" og giv det et navn.

Når guiden er gennemført, kan du åbne dashboardet i Grafana og se personernes placeringer.

## Begrænsninger

- Kun `person.*`-entiteter spores (ikke rå `device_tracker.*`).
- Lokationshistorik gemmes lokalt i Home Assistants storage og beholder de seneste ~10.000
  punkter i alt (på tværs af alle personer) – ikke en fuld tidsserie-database.
- Kun én Grafana-forbindelse pr. Home Assistant-installation understøttes i denne version.
- Denne integration er ikke testet mod en levende Grafana-instans som del af udviklingen af
  denne kode – test opsætningen i dit eget miljø, og opret gerne et issue hvis noget ikke
  matcher din Grafana-version.
