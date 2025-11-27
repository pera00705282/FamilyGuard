# Staging / Sandbox Validation Plan

Ovaj dokument definiše korake i scenarije koje treba proći pre nego što alat bude smatran spremnim za produkciju (real money). Cilj je dokazati da bot, dashboard i sigurnosni mehanizmi funkcionišu korektno u kontrolisanom okruženju (testnet/sandbox berze).

---

## 1. Okruženje i priprema

1. **Berze/Testnet nalozi**
   - Binance Testnet (https://testnet.binancefuture.com/)
   - Kraken Demo / Sandbox (https://demo-futures.kraken.com/)
   - (Opcionalno) Coinbase Advanced Trade sandbox.

2. **API ključevi**
   - Koristiti isključivo sandbox/testnet API ključeve.
   - Ključeve upisati u `config/config.yaml` preko `scripts/secure_config_manager.py --auto` (ili kroz `CRYPTO_TOOL_CONFIG_B64` + enkriptovani store).

3. **Pokretanje alata**
   - `python scripts/bootstrap_tool.py --run-bot --run-dashboard --auto-config --skip-tests`
   - Uveriti se da Dashboard radi (`http://HOST:8000/health` i `/api/status`).

4. **Monitoring/Logovi**
   - Osigurati da `crypto_trading.log` i dashboard `/api/logs` prate sve akcije.
   - Ako se koristi dodatni monitoring (Prometheus/Grafana), povezati i tamo.

5. **Automatizovani staging run**
   - Preporučeno: `python scripts/run_staging_plan.py --duration 900 --auto-config`
   - Skripta pokreće bot + dashboard, vrši health provere i čuva završni status u `staging_status.json`.

---

## 2. Test scenariji

### 2.1. Osnovno spajanje i trgovanje
1. Pokrenuti bot na testnetu sa minimalnim pozicijama (npr. `BTC/USDT`, `ETH/USDT`).
2. Potvrditi da se strategije izvršavaju (videti signale na dashboardu).
3. Simulirati hvatanje cene (manualno ili kroz testnet order book) i proveriti da se pozicija otvara i zatvara bez greške.

### 2.2. Rate limit i greške
1. Namerno poslati više requestova (npr. učestalo osvežavanje) da se uhvati rate-limit odgovor.
2. Potvrditi da bot loguje rate-limit warning i nastavlja bez pada.

### 2.3. Stop Loss / Take Profit
1. Otvoriti poziciju sa definisanim SL/TP.
2. Pomaknuti cenu (ili simulirati) tako da se SL/TP okine.
3. Potvrditi da se pozicija zatvara i dashboard/logovi beleže event.

### 2.4. Restart & Recovery
1. Zaustaviti bot (Ctrl+C) dok postoje otvorene pozicije.
2. Ponovo pokrenuti `bootstrap_tool.py --run-bot --auto-config`.
3. Proveriti da se stanje (pozicije, balansi, PnL) učitava ispravno iz `config/config.yaml` i/ili persistence sloja (`load_state`).

### 2.5. Dashboard funkcionalnost
1. Potvrditi da `/api/status`, `/api/config`, `/ws/status` prikazuju ažurne informacije tokom trgovanja.
2. Testirati upozorenja/alert kanale (ako su konfigurirani).

### 2.6. Sigurnosni scenariji
1. Proveriti da `config/config.yaml` ne curi (i da `secure_config_manager` može ponovo enkriptovati stanje sa `--encrypt-store --delete-plain`).
2. Ako je dashboard izložen vanjenetwork, obavezno dodati auth (npr. osnovni API token) pre produkcije.

---

## 3. Izveštavanje i kriterijumi

Za svaki scenario:
- Zabeležiti *datum, vreme, berzu/testnet*, korišćene pare i parametre.
- Snapshot dashboarda i logova.
- Da li je scenario PASS/FAIL + kratko objašnjenje.

**Minimalni kriterijum za “spreman za produkciju”:**
1. Svi scenariji iz sekcije 2 su PASS (uključujući restart & recovery).
2. Nema otvorenih sigurnosnih problema (tajne, dashboard auth, log leakage).
3. Automatizovani testovi prolaze (`pytest`) i prikrivaju ključne module (strategije, portfolio, risk).
4. Postoji dokumentovan runbook za incident response (gašenje bota, obnova tajni, kontakt plan).

---

## 4. Dalji koraci

1. Automatizovati staging test kroz CI pipeline (npr. GitHub Actions koji pokreće simulirane scenarije sa mock berzama).
2. Integrisati notifikacije (Slack/Telegram) za kritične evente pre produkcije.
3. Nakon uspešnog staging testiranja, pripremiti “go-live checklist” koja uključuje ručni review config-a, budžet i sve interne dozvole.

---

Kada svi koraci iz ovog plana budu završeni i dokumentovani, možemo dati preporuku za prelazak na real money režim. 

