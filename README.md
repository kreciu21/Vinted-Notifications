# Vinted-Notifications

A real-time notification system for Vinted listings that works across all Vinted country domains. Get instant alerts
when items matching your search criteria are posted.

![Vinted-Notifications](https://github.com/user-attachments/assets/f2788511-5a8a-4a8d-8198-a4135081a3d8)

## 📋 Features

- **Web UI**: Manage everything through an intuitive web interface
- **Multi-Country Support**: Works on all Vinted domains regardless of country
- **Real-Time Notifications**: Get instant alerts for new listings
- **Multiple Search Queries**: Monitor multiple search terms simultaneously
- **Country Filtering**: Filter items by seller's country of origin
- **RSS Feed**: Subscribe to your search results with any RSS reader
- **Discord Integration**: Receive notifications directly in your Discord server

## 📦 Installation

### Prerequisites

- Python 3.11 or higher
- Discord bot token and target channel (for Discord notifications)

### Setup

1. **Clone the repository or download the latest release**

   ```bash
   git clone https://github.com/Fuyucch1/Vinted-Notifications.git
   cd Vinted-Notifications
   ```

   Alternatively, download the [latest release](https://github.com/Fuyucch1/Vinted-Notifications/releases/latest) and
   extract it.

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Initial Configuration**

   The application can be configured through the Web UI after starting. However, you can also change the Web UI port in
   the
   `configuration_values.py` file directly.

4. **Run the application**

   ```bash
   python vinted_notifications.py
   ```

   Once started, access the Web UI at [http://localhost:8000](http://localhost:8000) to complete the setup.

## 🚀 Usage

### Web UI

The Web UI is the easiest way to manage the application. Access it at [http://localhost:8000](http://localhost:8000)
after starting the application.

Features available in the Web UI:

- **Dashboard**: Overview of application status and recent items
- **Queries Management**: Add, remove, and view search queries
- **Items Viewing**: Browse and filter items found by the application
- **Allowlist Management**: Filter items by seller's country
- **Configuration**: Set up the Discord bot, RSS feed, and other settings
- **Logs**: View application logs directly from the web interface

### Discord Setup

Follow these steps to connect the built-in Discord bot and receive notifications on your server:

1. **Create the bot in the Discord Developer Portal**
   1. Go to [https://discord.com/developers/applications](https://discord.com/developers/applications) and create a new application.
   2. Open the **Bot** tab, click **Add Bot**, then copy the **token** – you will paste it into the Web UI later.
   3. Under **Privileged Gateway Intents**, enable **Message Content Intent** only if you also plan to react to plain text messages. Slash commands work without it, but leaving it enabled does not hurt.

2. **Invite the bot to your server**
   1. In the **OAuth2 → URL Generator** tab, select both the `bot` and `applications.commands` scopes so the slash commands can be registered.
   2. Grant at least the **Send Messages** and **Embed Links** permissions.
   3. Open the generated URL in your browser and invite the bot to the server/channel where you want updates.

3. **Collect the Discord channel and optional guild IDs**
   1. In Discord, open **User Settings → Advanced** and enable **Developer Mode**.
   2. Right-click the channel where notifications should appear and choose **Copy Channel ID**.
   3. (Optional) Right-click the server name and choose **Copy Server ID**. Supplying it lets the bot register slash commands instantly for that server instead of waiting for Discord's global sync.

4. **Configure the bot in the Web UI**
   1. Start the application with `python vinted_notifications.py` and open the Web UI.
   2. Navigate to **Configuration → Discord Bot**.
   3. Paste the bot token, channel ID, and (optionally) the guild ID into the corresponding fields.
   4. Toggle **Auto Start** if you want the Discord worker to launch automatically next time.
   5. Click **Save** at the bottom of the configuration page.

5. **Start or stop the Discord worker**
   - The Discord worker starts automatically when the token and channel ID are present and the **Discord** toggle is enabled. You can switch it on or off at any time from the Configuration page.
   - If you prefer managing it manually, set `discord_process_running` to `True`/`False` directly in the database parameters table (e.g. via the built-in Web UI configuration form).

6. **Verify the connection**
   - The logs in the Web UI should show `Discord bot process started` when the worker connects successfully.
   - In Discord, use `/hello` to confirm the bot can respond in the selected channel. If commands do not appear immediately, double-check the guild ID or wait for Discord to propagate global commands (up to 1 hour).

### Discord Commands

Once the Discord worker is running, it exposes the following slash commands in the configured channel (responses are ephemeral so they only appear to the caller):

- `/hello` – Check if the bot is online and view the current application version
- `/add_query query_url [name]` – Add a search query to monitor (the optional `name` becomes the friendly label)
- `/remove_query selector` – Remove a specific query by its number or use `all` to clear them
- `/queries` – List all active queries
- `/add_country country` – Add a country to the allowlist
- `/remove_country country` – Remove a country from the allowlist
- `/clear_allowlist` – Remove every country from the allowlist
- `/allowlist` – Show the current allowlist (or indicate that all countries are allowed)

## 🇵🇱 Jak działa bot Discord i jak go uruchomić

Poniższy poradnik opisuje działanie i konfigurację całego systemu – od pobierania ogłoszeń z Vinted aż po wysyłkę powiadomień na Discordzie.

### Jak działa aplikacja

1. **Proces monitorujący** co kilka sekund odpytuje Vinted, korzystając z biblioteki `pyVinted`. Zapytania i filtry (np. lista krajów) są przechowywane w bazie SQLite.
2. **Warstwa proxy**: jeżeli w konfiguracji włączysz Webshare lub podasz własną listę proxy, każdy request do Vinted zostanie przez nie wysłany. Dzięki temu możesz ominąć limity IP.
3. **Dispatcher** analizuje świeże ogłoszenia i przekazuje je do kolejek wtyczek (Discord, RSS). Każda wtyczka działa w osobnym procesie, więc awaria jednego kanału nie zatrzyma reszty.
4. **Wtyczka Discord** pobiera dane z kolejki, buduje bogate embed-y i publikuje je na wskazanym kanale. Jednocześnie nasłuchuje poleceń slash, aby pozwolić na zarządzanie zapytaniami prosto z Discorda.

### Przygotowanie bota Discord krok po kroku

1. **Utwórz bota w panelu deweloperskim Discorda**
   - Wejdź na [https://discord.com/developers/applications](https://discord.com/developers/applications) i utwórz nową aplikację.
   - W zakładce **Bot** dodaj bota i skopiuj **token**.
   - Włącz **Message Content Intent** tylko wtedy, gdy planujesz analizować zwykłe wiadomości. Do samych komend slash nie jest potrzebne.

2. **Zaproś bota na swój serwer**
   - W zakładce **OAuth2 → URL Generator** zaznacz zakresy `bot` oraz `applications.commands`.
   - Przyznaj uprawnienia **Send Messages** i **Embed Links**.
   - Otwórz wygenerowany link i dodaj bota na wybrany serwer.

3. **Zbierz identyfikatory**
   - W Discordzie włącz tryb deweloperski (`Ustawienia użytkownika → Zaawansowane → Tryb dewelopera`).
   - Kliknij prawym przyciskiem na docelowym kanale i wybierz **Kopiuj identyfikator**.
   - (Opcjonalnie) skopiuj też **ID serwera** – przyspieszy to synchronizację komend slash.

4. **Zainstaluj zależności projektu**
   ```bash
   git clone https://github.com/Fuyucch1/Vinted-Notifications.git
   cd Vinted-Notifications
   pip install -r requirements.txt
   ```

5. **Uruchom aplikację**
   ```bash
   python vinted_notifications.py
   ```
   W tle zostaną utworzone tabele bazy danych, kolejki procesów i serwer Web UI.

6. **Skonfiguruj wszystko w Web UI**
   - Otwórz [http://localhost:8000](http://localhost:8000).
   - Przejdź do zakładki **Configuration → Discord Bot**.
   - Wklej token bota, ID kanału i opcjonalnie ID serwera.
   - Włącz przełącznik **Discord** (automatyczne uruchamianie) i zapisz zmiany.
   - W zakładce **Proxy** możesz włączyć Webshare: podaj login, hasło, host i port otrzymany z [https://proxy.webshare.io/](https://proxy.webshare.io/). Jeżeli opcja jest aktywna, wszystkie zapytania do Vinted będą korzystać z rotujących IP Webshare.

7. **Dodaj zapytania z poziomu Discorda**
   - Po kilku sekundach komendy slash będą dostępne na serwerze.
   - Użyj `/add_query <pełny_link_do_vinted>` aby rozpocząć monitorowanie.
   - Listę aktywnych zapytań sprawdzisz przez `/queries`, a usuniesz `/remove_query`.

8. **Monitoruj działanie**
   - W zakładce **Dashboard** Web UI zobaczysz status procesów (w tym bota Discord).
   - Logi w sekcji **Logs** pokażą komunikaty w stylu `Discord bot process started` lub ewentualne błędy.
   - W razie potrzeby możesz zatrzymać/wznowić proces bezpośrednio przełącznikiem w konfiguracji.

9. **Aktualizacje i kopie zapasowe**
   - Przed aktualizacją zachowaj plik `vinted_notifications.db` – przechowuje on zapytania, konfigurację i allowlisty.
   - Po pobraniu nowej wersji projektu wystarczy podmienić pliki i ponownie uruchomić aplikację.

Masz gotowy system powiadomień Vinted, który działa w czasie rzeczywistym i korzysta z komend slash na Discordzie. Wszystkie elementy (proces monitorujący, proxy, bot Discord, RSS) możesz kontrolować jednym interfejsem Web UI.

### Query Examples

Queries must be added with a whole link. It works with filters.:

   ```
   /add_query https://www.vinted.fr/catalog?search_text=nike%20shoes&price_to=50&currency=EUR&brand_id[]=53
   ```

### RSS Feed

The RSS feed provides an alternative way to receive notifications. After enabling it in the Web UI, access it
at [http://localhost:8001](http://localhost:8001).

## ⚙️ Advanced Configuration

### Proxy Support

The application supports multiple proxy strategies, all configurable from the Web UI:

- **Proxy List** – Provide a semicolon-separated list of proxies (`http://ip:port` or `ip:port`).
- **Proxy List Link** – Point to a URL that returns a newline-separated list of proxies. The app will download and rotate through them automatically.
- **Webshare Rotating Proxy** – Toggle the dedicated Webshare section and supply your username, password, host, port, and protocol (defaults point to `proxy.webshare.io:80`). The integration forwards every request through Webshare's rotating gateway so you benefit from a new exit node on each call without maintaining a long proxy list.

When Webshare is enabled it takes priority over the static lists. You can disable it at any time to fall back to the custom proxy pools.

### Custom Notification Format

You can customize the notification message format:

```python
# In configuration_values.py
MESSAGE = '''\
🆕 Title: {title}
💶 Price: {price}
🛍️ Brand: {brand}
<a href='{image}'>&#8205;</a>
'''
```

## 🔄 Updating

1. Download the latest [release](https://github.com/Fuyucch1/Vinted-Notifications/releases/latest)
2. Back up your `vinted_notifications.db` file
3. Replace all files with the new ones
4. Restart the application

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📜 License

This project is licensed under the [GNU AFFERO GENERAL PUBLIC LICENSE](LICENSE).

## 🙏 Acknowledgements

- Thanks to [@herissondev](https://github.com/herissondev) for maintaining pyVinted, a core dependency of this project.
