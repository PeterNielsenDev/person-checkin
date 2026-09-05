# Person Check-in (Grafana)

Custom Home Assistant-integration (HACS) der sporer dine `person.*`-entiteters lokation og
viser dem live på et Grafana-dashboard (kort + historik-tabel), ved at skrive direkte til
den PostgreSQL-database din Grafana-instans allerede bruger.

## Sådan virker det

1. Integrationen lytter på state-ændringer for alle `person.*`-entiteter i Home Assistant.
2. Ved ændring i lokation (lat/lon) skrives et punkt (person, koordinater, GPS-nøjagtighed,
   status, tidspunkt) direkte ind i en tabel (`person_checkin_locations`) i din PostgreSQL-
   database — tabellen oprettes automatisk første gang.
3. Under opsætning opretter integrationen selv (via Grafanas HTTP API, med det
   brugernavn/password du indtaster) en **PostgreSQL-datasource** i Grafana, der peger på
   samme database.
4. Den opretter derefter et **Geomap**-panel (kort med markører for seneste kendte
   position pr. person) og et tabelpanel med historik, enten på et nyt dashboard eller
   føjet til et eksisterende du vælger.
5. Hvis skrivning til PostgreSQL fejler midlertidigt (fx netværksudfald mellem VM'erne),
   holdes op til 500 punkter i hukommelse og forsøges skrevet igen hvert minut.

Da din Grafana kører i Docker på en anden VM og allerede bruger PostgreSQL, undgår denne
løsning at skulle sætte en ekstra tidsserie-database (InfluxDB o.lign.) op — Home Assistant
skriver direkte i den database Grafana i forvejen kender.

## Forudsætninger

- En kørende Grafana-server (IP på den anden VM), med en bruger der har rettigheder til at
  oprette datasources og dashboards (typisk Admin eller Editor).
- PostgreSQL-databasen skal være net-tilgængelig fra din Home Assistant-server (samme VM
  som Grafana, eller en du kan nå på netværket).
- En PostgreSQL-bruger/adgangskode med rettigheder til at oprette tabel/index og indsætte
  rækker i den valgte database (`CREATE TABLE`, `INSERT`).

### Tjekliste: netværk mellem Home Assistant og Postgres/Grafana (samme VLAN)

Kører Postgres i en Docker-container på Grafana-VM'en, skal følgende være i orden, selv når
de to VM'er er på samme VLAN/subnet:

1. **Port-mapping i docker-compose** — containeren skal eksponere `5432` til VM'ens
   netværk, ikke kun Docker's interne netværk:
   ```yaml
   ports:
     - "5432:5432"
   ```
2. **`listen_addresses`** i `postgresql.conf` skal være `*` (eller VM'ens IP) — det er ofte
   allerede standard i de officielle Postgres Docker-images.
3. **`pg_hba.conf`** skal tillade forbindelser fra Home Assistants IP/subnet, fx:
   ```
   host    all    all    192.168.1.0/24    scram-sha-256
   ```
   (juster til jeres faktiske VLAN-subnet). Uden denne linje afvises forbindelsen, selvom
   porten er åben.

## Installation via HACS

1. HACS → tre prikker øverst til højre → "Custom repositories".
2. Tilføj `https://github.com/PeterNielsenDev/person-checkin` som type "Integration".
3. Installer "Person Check-in (Grafana)" og genstart Home Assistant.
4. Gå til **Indstillinger → Enheder & tjenester → Tilføj integration** og søg efter
   "Person Check-in".

## Opsætning (guide i UI)

1. **Grafana-forbindelse**: IP/hostname, port (default 3000), HTTP/HTTPS, brugernavn og
   adgangskode. Integrationen tester login med det samme.
2. **PostgreSQL-database**: IP/hostname, port (default 5432), database-navn, brugernavn,
   adgangskode og SSL-tilstand. Integrationen tester forbindelsen og opretter
   PostgreSQL-datasourcen i Grafana.
3. **Vælg dashboard**: vælg et eksisterende dashboard som lokations-panelerne skal føjes
   til, eller vælg "➕ Opret nyt dashboard" og giv det et navn.

Når guiden er gennemført, kan du åbne dashboardet i Grafana og se personernes placeringer.

## Begrænsninger

- Kun `person.*`-entiteter spores (ikke rå `device_tracker.*`).
- Kun én Grafana-/PostgreSQL-forbindelse pr. Home Assistant-installation understøttes i
  denne version.
- Denne integration er ikke testet mod en levende Grafana/PostgreSQL-instans som del af
  udviklingen af denne kode – test opsætningen i dit eget miljø, og opret gerne et issue
  hvis noget ikke matcher din Grafana-version.
