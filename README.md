# Person Check-in (Grafana)

Custom Home Assistant-integration (HACS) der sporer dine `person.*`-entiteters lokation og
viser dem live på et Grafana-dashboard (kort + historik-tabel), ved at skrive direkte til
den PostgreSQL-database din Grafana-instans allerede bruger.

Integrationen har sit eget ikon (`custom_components/person_checkin/brand/icon.png`), som
Home Assistant siden 2026.3.0 kan vise direkte fra integrationens egen mappe — ingen
separat godkendelse i det centrale brands-repository er nødvendig. Kører du en ældre
version af Home Assistant, vises et generisk ikon i stedet.

## Sådan virker det

1. Integrationen lytter på state-ændringer for alle `person.*`-entiteter i Home Assistant.
2. Ved ændring i lokation (lat/lon) slås en menneskelæsbar adresse op via
   [Nominatim](https://nominatim.openstreetmap.org) (OpenStreetMap), og punktet (person,
   koordinater, adresse, GPS-nøjagtighed, status, tidspunkt) skrives direkte ind i en tabel
   (`person_checkin_locations`) i din PostgreSQL-database — tabellen oprettes automatisk
   første gang. Adresseopslag er best-effort: fejler det (netværk, rate-limit), skrives
   punktet stadig, blot uden adresse. Har personen ikke flyttet sig mere end ~100 meter
   siden sidste punkt, genbruges den tidligere opslåede adresse i stedet for at spørge
   Nominatim igen (overholder deres grænse på ca. 1 opslag/sekund).
3. Integrationen logger ind i Grafana med et **Service Account Token** (Editor-rolle) og
   bruger det til at søge/oprette/opdatere **dashboards** — det er alt et Editor-token må.
   Data source-administration kræver Admin-rolle i Grafana, så den PostgreSQL-datasource i
   Grafana der peger på databasen, skal allerede findes (oprettet én gang som Admin), og du
   angiver dens UID i opsætningsguiden.
4. Integrationen opretter derefter et **Geomap**-panel (kort med markører for seneste
   kendte position pr. person) og et tabelpanel med historik, enten på et nyt dashboard
   eller føjet til et eksisterende du vælger.
5. Hvis skrivning til PostgreSQL fejler midlertidigt (fx netværksudfald mellem VM'erne),
   holdes op til 500 punkter i hukommelse og forsøges skrevet igen hvert minut.

Da din Grafana kører i Docker på en anden VM og allerede bruger PostgreSQL, undgår denne
løsning at skulle sætte en ekstra tidsserie-database (InfluxDB o.lign.) op — Home Assistant
skriver direkte i den database Grafana i forvejen kender.

## Forudsætninger

- En kørende Grafana-server (IP på den anden VM).
- Et **Grafana Service Account** med rollen **Editor**, og et token genereret til det:
  1. Grafana → **Administration → Users and access → Service accounts**.
  2. **Add service account** → giv det et navn (fx `person-checkin`) → rolle **Editor**.
  3. Åbn service accounten → **Add service account token** → kopiér tokenet (vises kun én
     gang).
  Editor-rollen er nok til dashboards, men *ikke* til at administrere datasources — det
  kræver Admin i Grafana, hvorfor punktet nedenfor er nødvendigt.
- En **PostgreSQL-datasource allerede oprettet i Grafana** (som Admin, én gang), der peger
  på samme database som Home Assistant skal skrive til. Find dens UID under
  **Connections → Data sources** → klik datasourcen → UID'et står i browserens adresse-
  linje (`.../datasources/edit/<uid>`). Det UID skal du bruge i opsætningsguidens sidste
  trin.
- PostgreSQL-databasen skal være net-tilgængelig fra din Home Assistant-server (samme VM
  som Grafana, eller en du kan nå på netværket).
- En PostgreSQL-bruger/adgangskode (kan være en anden end den Grafana-datasourcen bruger)
  med rettigheder til at oprette tabel/index og indsætte rækker i den valgte database
  (`CREATE TABLE`, `INSERT`).

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

1. **Grafana-forbindelse**: IP/hostname, port (default 3000), HTTP/HTTPS og
   Service Account Token. Integrationen tester login med det samme.
2. **PostgreSQL-database**: IP/hostname, port (default 5432), database-navn, brugernavn,
   adgangskode og SSL-tilstand. Integrationen tester forbindelsen og opretter tabellen.
3. **Vælg dashboard**: vælg et eksisterende dashboard som lokations-panelerne skal føjes
   til, eller vælg "➕ Opret nyt dashboard" og giv det et navn — samt UID'et på den
   PostgreSQL-datasource i Grafana panelerne skal bruge (se Forudsætninger ovenfor).

Når guiden er gennemført, kan du åbne dashboardet i Grafana og se personernes placeringer.

> **Vigtigt:** Gennemfør opsætningsguiden mens du tilgår Home Assistant via dens
> **lokale IP-adresse/hostname** (fx `http://192.168.1.x:8123`) — **ikke** via en
> ekstern/public adresse (fx Nabu Casa remote access). Starter du guiden over en
> ekstern forbindelse, kan flowet miste sin tilstand undervejs, hvilket viser sig som
> fejlen **"Invalid flow specified"** når du kommer til PostgreSQL-trinnet. Det er ikke
> en fejl i integrationen — luk guiden, tilgå Home Assistant lokalt, og prøv igen.

## Status-sensor

Integrationen opretter en diagnostik-sensor, **`sensor.<navn>_status`**, der viser om den
rent faktisk virker:

- **`ok`** — seneste forsøg på at skrive en lokation til PostgreSQL lykkedes (sættes også
  med det samme når opsætningen gennemføres, da det kræver en vellykket forbindelse).
- **`error`** — seneste skrivning fejlede (se attributten `last_error` for detaljer).
- **`unknown`** — ingen skrivninger er forsøgt endnu.

Sensoren har derudover attributterne `last_success`, `last_error`, `last_error_time` og
`pending_points` (antal punkter der afventer genforsøg pga. midlertidige fejl). Den findes
under **Indstillinger → Enheder & tjenester → Person Check-in → Diagnostik**.

## Begrænsninger

- Kun `person.*`-entiteter spores (ikke rå `device_tracker.*`).
- Kun én Grafana-/PostgreSQL-forbindelse pr. Home Assistant-installation understøttes i
  denne version.
- Paneler på et **eksisterende** dashboard fra før v0.4.0 viser ikke adressen — kolonnen
  findes i databasen, men panelernes SQL skal opdateres manuelt (tilføj `address` til
  `SELECT`) for at vise den. Nye dashboards oprettet fra opsætningsguiden inkluderer den
  automatisk.
- Denne integration er ikke testet mod en levende Grafana/PostgreSQL-instans som del af
  udviklingen af denne kode – test opsætningen i dit eget miljø, og opret gerne et issue
  hvis noget ikke matcher din Grafana-version.
