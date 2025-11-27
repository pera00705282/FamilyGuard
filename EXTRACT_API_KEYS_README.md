# Izvlačenje API Ključeva - Uputstvo

## 📋 Pregled

Ovaj dokument objašnjava kako su API ključevi izvučeni iz zaštićenog foldera `C:\Users\Milan Jeremic\Desktop\API menjacnice` i integrisani u FamilyGuard tool.

## 🔐 Zaštićeni Folder

Folder `API menjacnice` sadrži:
- **Zaštićene fajlove** (`.protected`) u `secure/` folderu
- **Encryption key** u `keys/encryption-key.json`
- **Utility skripte** za enkripciju/dekripciju

### Podržani Exchange-ovi

Izvučeni su ključevi za:
- ✅ **Binance** - uspešno izvučen
- ✅ **Coinbase** - uspešno izvučen  
- ✅ **Kraken** - uspešno izvučen

## 🛠️ Kako Funkcioniše

### 1. Skripta za Izvlačenje

Kreirana je PowerShell skripta `extract_api_keys.ps1` koja:
1. Učitava encryption utilities iz `API menjacnice` foldera
2. Dekriptuje zaštićene fajlove za Binance, Coinbase i Kraken
3. Parsira dekriptovani sadržaj i izvlači API ključeve
4. Formatira ih u YAML format za FamilyGuard
5. Čuva u `config/config.yaml`

### 2. Format Dekriptovanih Ključeva

Dekriptovani fajlovi imaju format:
```
API key name: <actual_api_key>
Private key: <actual_secret>
```

Skripta automatski parsira ovaj format i izvlači samo ključeve.

### 3. Sigurnosne Mere

- ✅ **Sandbox mode** je automatski omogućen (`sandbox: true`)
- ✅ **Live trading** je onemogućen (`enable_live_trading: false`)
- ✅ Konfiguracija je validirana pre čuvanja

## 📝 Korišćenje

### Automatsko Izvlačenje

```powershell
cd "C:\Users\Milan Jeremic\Desktop\FamilyGuard"
.\extract_api_keys.ps1
```

### Ručno Izvlačenje (za pojedinačne exchange-ove)

```powershell
cd "C:\Users\Milan Jeremic\Desktop\API menjacnice"
.\decrypt-secrets.ps1 -Name "Binance"
.\decrypt-secrets.ps1 -Name "Coinbase"
.\decrypt-secrets.ps1 -Name "Kraken"
```

### Privremeno Otkrivanje (sa automatskim re-zaštitom)

```powershell
cd "C:\Users\Milan Jeremic\Desktop\API menjacnice"
.\reveal-secret.ps1 -Name "Binance" -ExposureSeconds 60
```

## ⚠️ Važne Napomene

1. **Sandbox Mode**: Svi exchange-ovi su podešeni na sandbox mode za sigurnost
2. **Live Trading**: Onemogućen je dok se ne testira u sandbox-u
3. **Backup**: Originalni zaštićeni fajlovi ostaju netaknuti
4. **Encryption Key**: Ne dijelite `encryption-key.json` fajl!

## 🔄 Ažuriranje Ključeva

Ako treba da ažurirate API ključeve:

1. Ažurirajte zaštićene fajlove u `API menjacnice/secure/`
2. Pokrenite `extract_api_keys.ps1` ponovo
3. Proverite da li je `config/config.yaml` ispravno ažuriran

## 📂 Struktura Fajlova

```
FamilyGuard/
├── extract_api_keys.ps1          # Skripta za izvlačenje
├── config/
│   └── config.yaml                # Generisana konfiguracija sa API ključevima
└── EXTRACT_API_KEYS_README.md      # Ovaj dokument

API menjacnice/
├── secure/
│   ├── Binance.protected
│   ├── Coinbase.protected
│   └── Kraken.protected
├── keys/
│   └── encryption-key.json
├── encryption-utils.ps1
├── decrypt-secrets.ps1
└── reveal-secret.ps1
```

## ✅ Provera Konfiguracije

Nakon izvlačenja, proverite da li je konfiguracija validna:

```powershell
$env:PYTHONPATH="src"
python -c "from crypto_trading.utils.config import load_config; config = load_config('config/config.yaml'); print('✅ Konfiguracija validna!'); print(f'Exchange-ovi: {list(config.exchanges.keys())}')"
```

## 🎯 Rezultat

API ključevi su uspešno izvučeni i integrisani u FamilyGuard tool. Konfiguracija je spremna za korišćenje u **sandbox mode-u** za testiranje.

---

**Napomena**: Ova skripta je kreirana za automatsko izvlačenje i formatiranje API ključeva. Uvek proverite konfiguraciju pre korišćenja u produkciji!

