# Binance WebSocket Client

Asinhroni WebSocket klijent za Binance API sa podrškom za više tržišnih parova, keširanje i rate limiting.

## Instalacija

```bash
pip install -r requirements.txt
```

## Brzi početak

```python
import asyncio
from crypto_trading.exchanges.websocket.binance_websocket import BinanceWebSocketClient

async def on_ticker(ticker):
    print(f"Ticker update: {ticker.symbol} - Bid: {ticker.bid}, Ask: {ticker.ask}")

async def main():
    client = BinanceWebSocketClient(
        cache_ttl=5,  # 5 sekundi keširanja
        max_requests_per_second=10  # 10 zahteva u sekundi
    )
    
    # Registrujemo callback za ticker podatke
    client.on_ticker(on_ticker)
    
    # Povezujemo se i pretplaćujemo na BTC/USDT ticker
    await client.connect()
    await client.subscribe('btcusdt@ticker')
    
    # Čekamo 30 sekundi
    await asyncio.sleep(30)
    
    # Zatvaramo konekciju
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

## API Reference

### BinanceWebSocketClient

Glavna klasa za rad sa Binance WebSocket API-jem.

#### Inicijalizacija

```python
client = BinanceWebSocketClient(
    api_key="your_api_key",  # Opciono za privatne podatke
    api_secret="your_api_secret",  # Opciono za privatne podatke
    cache_ttl=5,  # Vreme keširanja u sekundama
    max_requests_per_second=10  # Maksimalan broj zahteva u sekundi
)
```

#### Metode

##### connect()
Povezuje se sa WebSocket serverom.

##### disconnect()
Prekida vezu sa WebSocket serverom i oslobađa resurse.

##### subscribe(channels: Union[str, List[str]])
Pretplaćuje se na jedan ili više kanala.

Primeri kanala:
- `btcusdt@ticker` - Ticker podaci za BTC/USDT
- `btcusdt@depth` - Order book podaci
- `btcusdt@trade` - Trade podaci
- `user_data` - Privatni korisnički podaci (zahteva API ključ)

##### on_ticker(callback: Callable[[TickerUpdate], Awaitable[None]])
Registruje callback funkciju koja će biti pozvana prilikom dobijanja novih ticker podataka.

##### on_orderbook(callback: Callable[[OrderBookUpdate], Awaitable[None]])
Registruje callback za ažuriranja order book-a.

##### on_trade(callback: Callable[[Trade], Awaitable[None]])
Registruje callback za trgovinske podatke.

## Napredna upotreba

### Keširanje

Klijent automatski kešira podatke kako bi se smanjio broj nepotrebnih ažuriranja. Vreme keširanja može se podesiti prilikom inicijalizacije.

```python
# Keširaj podatke 10 sekundi
client = BinanceWebSocketClient(cache_ttl=10)
```

### Rate Limiting

Da biste izbegli prekoračenje limita zahteva, klijent automatski ograničava broj zahteva u sekundi.

```python
# Maksimalno 5 zahteva u sekundi
client = BinanceWebSocketClient(max_requests_per_second=5)
```

### Rukovanje greškama

Sve greške se loguju i mogu se uhvatiti koristeći standardne Python mehanizme za obradu izuzetaka.

```python
try:
    await client.connect()
    await client.subscribe('btcusdt@ticker')
    while True:
        await asyncio.sleep(1)
except Exception as e:
    print(f"Došlo je do greške: {e}")
finally:
    await client.disconnect()
```

## Primeri

### Praćenje više parova

```python
async def main():
    client = BinanceWebSocketClient()
    
    async def print_ticker(ticker):
        print(f"{ticker.symbol}: {ticker.last}")
    
    client.on_ticker(print_ticker)
    
    await client.connect()
    await client.subscribe([
        'btcusdt@ticker',
        'ethusdt@ticker',
        'bnbusdt@ticker'
    ])
    
    await asyncio.sleep(30)
    await client.disconnect()
```

### Rad sa order book podacima

```python
async def on_orderbook(book):
    print(f"Order book update for {book.symbol}")
    print(f"Best bid: {book.bids[0][0]} @ {book.bids[0][1]}")
    print(f"Best ask: {book.asks[0][0]} @ {book.asks[0][1]}")

async def main():
    client = BinanceWebSocketClient()
    client.on_orderbook(on_orderbook)
    
    await client.connect()
    await client.subscribe('btcusdt@depth')
    
    await asyncio.sleep(30)
    await client.disconnect()
```

## Podrška

Za sva pitanja i probleme, molimo otvorite tiket u repozitorijumu projekta.
