# MurmurType

Dyktowanie głosowe dla GNOME na Wayland. Naciskasz skrót, mówisz, a rozpoznany tekst
wkleja się w aktywne okno. Rozpoznawanie działa lokalnie (offline) na
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) z modelem `large-v3-turbo`,
który dobrze radzi sobie z polskim.

## Jak to działa

```
skrót GNOME ──► murmurtype toggle ──(gniazdo unix)──► murmurtype daemon (usługa systemd --user)
                                                     │
                                                     ├─ pw-record: nagrywanie 16 kHz mono
                                                     ├─ koniec po ciszy / ponownym skrócie
                                                     ├─ faster-whisper (CPU lub GPU)
                                                     └─ wl-copy + ydotool Ctrl+V
```

- **Demon w tle** trzyma model w pamięci, więc każde dyktowanie startuje od razu.
  Klient `murmurtype toggle` nie importuje Whispera i odpowiada w kilkadziesiąt milisekund.
- **Koniec nagrania** następuje automatycznie po `silence_seconds` ciszy (domyślnie 2 s; `0` wyłącza),
  po ponownym naciśnięciu skrótu albo po `max_seconds`. Jeśli przez
  `no_speech_timeout_seconds` nikt nic nie powie, nagranie jest porzucane.
- **Tekst trafia przez schowek**, a nie przez `ydotool type`. `ydotool` wysyła kody
  klawiszy układu US i psuje polskie znaki (ą, ę, ł…). Wklejenie przez schowek zachowuje
  każdy znak.
- **CPU czy GPU** (`device = "auto"`): model na CPU jest zawsze załadowany. Przed każdym
  dyktowaniem demon sprawdza `nvidia-smi`; gdy wolnego VRAM jest co najmniej
  `cuda_min_free_mb`, ładuje model na GPU, a po `cuda_idle_unload_seconds` bezczynności
  zwalnia pamięć. Dzięki temu nie blokuje karty innym procesom.
- **Powiadomienia** („Słucham…”, „Rozpoznaję…”, „Wklejono”) zastępują się nawzajem
  zamiast piętrzyć.

## Wymagania

- GNOME na Wayland (pod X11 też działa, ale nie było testowane)
- PipeWire (`pw-record`), `wl-clipboard`, `ydotool` z działającym demonem `ydotoold`,
  `libnotify-bin`, [uv](https://docs.astral.sh/uv/)
- Użytkownik w grupie `input` — `ydotool` potrzebuje `/dev/uinput`, a `murmurtype listen`
  odczytuje przyciski z `/dev/input/event*`
- Kompilator C (`build-essential`) — biblioteka `evdev` dla `murmurtype listen` buduje się
  przy instalacji
- Opcjonalnie: karta NVIDIA ze sterownikiem obsługującym CUDA 12

```bash
sudo apt install pipewire-bin wl-clipboard ydotool libnotify-bin build-essential
```

## Instalacja

```bash
scripts/install.sh
```

Z obsługą GPU (doinstaluje cuBLAS i cuDNN 9 z PyPI, ok. 1 GB):

```bash
scripts/install.sh --cuda
```

Skrypt:

1. instaluje `murmurtype` jako narzędzie `uv` (`~/.local/bin/murmurtype`, Python 3.12),
2. kopiuje `config.example.toml` do `~/.config/murmurtype/config.toml`, jeśli go jeszcze nie ma,
3. instaluje i uruchamia usługę `~/.config/systemd/user/murmurtype.service`
   oraz instaluje (bez włączania) `murmurtype-listen.service`,
4. instaluje ikonę aplikacji „MurmurType” (`~/.local/share/applications/murmurtype.desktop`),
5. dodaje skrót GNOME (Ustawienia → Klawiatura → Skróty własne, pozycja „MurmurType”).
   Istniejące skróty własne zostają nietknięte.

Dodatkowe opcje (pełny opis: `scripts/install.sh --help`):

| Opcja | Działanie |
|---|---|
| `--cuda` | obsługa GPU |
| `--dock` | przypina ikonę do docka |
| `--listen` | włącza usługę przycisku (patrz [Przycisk myszy lub pedał](#przycisk-myszy-lub-pedał)) |
| `--shortcut`, `--force-shortcut`, `--no-shortcut` | patrz [Skrót klawiszowy](#skrót-klawiszowy) |

Przy pierwszym uruchomieniu model (~1,6 GB) pobiera się z Hugging Face do
`~/.cache/huggingface`, więc pierwszy start usługi trwa dłużej.

### Skrót klawiszowy

Domyślny skrót to **`Ctrl+Shift+D`**.

GNOME po cichu ignoruje skrót własny, który koliduje z innym, więc instalator najpierw
sprawdza skróty wbudowane GNOME i inne skróty własne. Jeśli skrót jest zajęty, przerywa
i mówi, przez co. Do wyboru:

```bash
scripts/install.sh --shortcut '<Super>backslash'  # inny skrót
scripts/install.sh --force-shortcut               # wymuś domyślny mimo konfliktu
scripts/install.sh --no-shortcut                  # bez skrótu
```

`--shortcut` można podać kilka razy — kandydaci są sprawdzani w podanej kolejności
i wygrywa pierwszy wolny. `--force-shortcut` zabiera skrót tylko kolidującym akcjom
**wbudowanym** GNOME i wypisuje polecenie `gsettings reset …`, które to cofa. Innych
skrótów własnych nie rusza.

Skrót można zmienić później bez reinstalacji (te same zasady, `--force` działa tak samo):

```bash
scripts/install-shortcut.sh                       # Ctrl+Shift+D
scripts/install-shortcut.sh '<Super>backslash'
```

Format zapisu skrótów jest taki jak w `gsettings`: `<Primary>` = Ctrl, `<Super>` = Win,
`<Alt>`, `<Shift>`, a na końcu klawisz małą literą.

#### Jak działa `--force`

`--force` (w `install.sh`: `--force-shortcut`) **przejmuje skrót od wbudowanej akcji
GNOME**: usuwa ten jeden skrót z kolidującej akcji i przypisuje go dyktowaniu. Sama akcja
zostaje i działa dalej pod swoimi pozostałymi skrótami, jeśli jakieś ma. Skrypt wypisuje
polecenie, które przywraca ustawienie domyślne, np.:

```bash
gsettings reset org.gnome.desktop.wm.keybindings show-desktop
```

`--force` nigdy nie przejmuje skrótu od innego **skrótu własnego** (Ustawienia →
Klawiatura → Skróty własne) — wtedy skrypt przerywa i trzeba zwolnić skrót ręcznie.

#### Alternatywy

Globalny skrót GNOME przechwytuje klawisze, zanim dotrą do aplikacji, więc skrót
dyktowania przestaje działać w aplikacjach, które go używają. Konflikty w tabeli dotyczą
domyślnej konfiguracji Ubuntu.

| Skrót | Ergonomia | Konflikt w GNOME | Konflikt w aplikacjach | Instalacja |
|---|---|---|---|---|
| **`Ctrl+Shift+D`** (domyślny) | dwa modyfikatory pod małym palcem | brak | VS Code: panel debugowania; Chrome/Brave/Firefox: zapis wszystkich kart okna jako zakładek (dalej dostępny z menu zakładek) | `scripts/install-shortcut.sh` |
| `Super+D` | najwygodniejszy: kciuk + palec, odpowiednik `Win+H` | „Pokaż pulpit” (zostaje pod `Ctrl+Super+D`, `Ctrl+Alt+D`) | brak | `scripts/install-shortcut.sh --force '<Super>d'` |
| `Ctrl+Alt+D` | wygodny: kciuk na Alt, mały palec na Ctrl | „Pokaż pulpit” (zostaje pod `Super+D`, `Ctrl+Super+D`) | rzadko używany | `scripts/install-shortcut.sh --force '<Primary><Alt>d'` |
| `Super+H` | jak `Win+H` w Windows | „Minimalizuj okno” (bez innego skrótu) | brak | `scripts/install-shortcut.sh --force '<Super>h'` |
| `Super+Alt+D` | dwa modyfikatory obok siebie pod kciukiem, niewygodny | brak | brak | `scripts/install-shortcut.sh '<Super><Alt>d'` |

Przejście na inny skrót zastępuje poprzedni wpis „MurmurType”, więc nie trzeba go
najpierw usuwać. Skrót przejęty wcześniej od GNOME nie wraca sam — przywróć go
poleceniem `gsettings reset …`, które wypisał skrypt.

## Użycie

| Polecenie | Działanie |
|---|---|
| `murmurtype toggle` | start nagrywania; podczas nagrywania — zakończ i rozpoznaj |
| `murmurtype start` / `murmurtype stop` | jawny start / koniec nagrania |
| `murmurtype hold` | start bez wykrywania ciszy — kończy go dopiero `stop` (push-to-talk) |
| `murmurtype cancel` | przerwij nagranie bez rozpoznawania |
| `murmurtype status` | `idle`, `recording` albo `transcribing` |
| `murmurtype listen` | nasłuchuje przycisku urządzenia (robi to usługa `murmurtype-listen`) |
| `murmurtype listen --discover` | pokazuje urządzenia i nazwy naciskanych przycisków |
| `murmurtype daemon` | uruchamia demona (robi to usługa systemd) |

Typowo: ustaw kursor w polu tekstowym, naciśnij skrót, powiedz zdanie i zamilknij.
Po chwili ciszy (`silence_seconds`) tekst się wklei.

### Ikona

Ikona „MurmurType” jest w siatce aplikacji (klawisz `Super`, wpisz „MurmurType” albo
„dyktowanie”). Kliknięcie działa jak skrót. Prawy przycisk na ikonie w docku daje też
„Zacznij dyktowanie”, „Zakończ i wklej” i „Anuluj”. Przypięcie do docka: instalacja
z `--dock` albo prawy przycisk na ikonie → „Przypnij do docka”.

Kliknięcie ikony zabiera fokus z okna, do którego chcesz pisać — kliknij potem z powrotem
w pole tekstowe przed końcem nagrania, bo tekst wkleja się do okna aktywnego **w chwili
wklejenia**.

### Przycisk myszy lub pedał

`murmurtype listen` uruchamia dyktowanie dowolnym przyciskiem dowolnego urządzenia
wejściowego: bocznym przyciskiem myszy, pedałem USB, makropadem. Domyślnie działa
w trybie **„trzymaj i mów”**: nagrywa, dopóki trzymasz przycisk, i rozpoznaje po
puszczeniu. Wykrywanie ciszy jest wtedy wyłączone, więc pauzy w trakcie nie urywają
nagrania.

1. Znajdź urządzenie i przycisk poleceniem `murmurtype listen --discover`
   (opis [niżej](#wyszukiwanie-urządzenia-i-przycisku)).

2. Dopisz je do `~/.config/murmurtype/config.toml`:

   ```toml
   listen_device = "Logitech MX Vertical"
   listen_button = "BTN_EXTRA"
   listen_mode = "hold"        # albo "toggle": naciśnij, żeby zacząć i zakończyć
   listen_exclusive = true     # przycisk służy tylko do dyktowania
   ```

3. Włącz usługę:

   ```bash
   systemctl --user enable --now murmurtype-listen
   ```

#### Wyszukiwanie urządzenia i przycisku

```bash
murmurtype listen --discover
```

Najpierw wypisuje wszystkie urządzenia wejściowe, które mają przyciski lub klawisze:

```
Input devices with buttons:
  /dev/input/event4    Logitech ERGO K860
  /dev/input/event3    Logitech MX Vertical
  /dev/input/event2    Logitech M720 Triathlon
  ...
```

Potem czeka na naciśnięcia i przy każdym wypisuje gotową linię do konfiguracji:

```
listen_device = "Logitech MX Vertical"   listen_button = "BTN_EXTRA"
```

Naciśnij przycisk, którego chcesz używać, skopiuj obie wartości do `config.toml`
i zakończ `Ctrl+C`. Warto nacisnąć go kilka razy i sprawdzić, czy za każdym razem pojawia
się to samo — niektóre urządzenia wysyłają przy jednym przycisku kilka kodów (np. klawisz
z modyfikatorem); wybierz wtedy ten nietypowy, bez modyfikatora.

Na co uważać:

- **Wypisywane jest tylko wciśnięcie** (nie puszczenie ani ruch), więc łatwo znaleźć
  właściwą linię. Wypisują się też klawisze klawiatury — `--discover` niczego nie zapisuje
  ani nie wysyła, pokazuje je tylko w terminalu.
- **Zatrzymaj najpierw usługę przycisku**, jeśli działa z `listen_exclusive = true`:
  `systemctl --user stop murmurtype-listen`. Przejęte urządzenie nie wysyła zdarzeń do
  innych programów, więc `--discover` nie zobaczy jego przycisków. Wirtualne kopie
  „… (murmurtype)” są pomijane na liście.
- **Nie każdy przycisk jest widoczny.** Przyciski obsługiwane w samym urządzeniu — np.
  zmiana DPI w wielu myszach albo przełącznik kanałów Bluetooth — nie trafiają do
  systemu, więc nie da się ich użyć.
- **Mysz na odbiorniku bezprzewodowym** może pojawić się pod swoją nazwą (jak myszy
  Logitech wyżej) albo pod nazwą odbiornika. Jeśli przez jeden odbiornik działa kilka
  urządzeń i wszystkie mają tę samą nazwę, `listen_device` ich nie rozróżni.
- **„No readable input devices”** oznacza brak uprawnień: dodaj użytkownika do grupy
  `input` (`sudo usermod -aG input $USER`) i zaloguj się ponownie.
- Na liście jest też „ydotoold virtual device” — to wirtualna klawiatura, przez którą
  MurmurType wkleja tekst; nie wybieraj jej.

`listen_device` to pełna nazwa urządzenia, jej unikalny fragment albo ścieżka
`/dev/input/eventN` (numery mogą się zmieniać po restarcie, nazwy nie). Po odłączeniu
urządzenia albo uśpieniu odbiornika bezprzewodowego usługa sama łączy się ponownie.

**`listen_exclusive`.** Bez tego przycisk zachowuje też swoją zwykłą funkcję — boczny
przycisk myszy jednocześnie uruchomi dyktowanie i cofnie stronę w przeglądarce. Z `true`
usługa przejmuje urządzenie na wyłączność i przekazuje dalej wszystkie zdarzenia (ruch,
kliknięcia, kółko) przez wirtualną kopię urządzenia „… (murmurtype)”, z wyjątkiem
wybranego przycisku. Jeśli usługa się zatrzyma lub padnie, system od razu oddaje
urządzenie, więc mysz nie zostanie „martwa”. Ustawienia myszy w GNOME (szybkość,
przyspieszenie) obowiązują także kopię. Pedały i makropady zwykle wysyłają klawisze
bez innej funkcji (np. `KEY_F13`–`KEY_F24`), więc tam `listen_exclusive` nie jest potrzebne.

Jakich urządzeń użyć:

| Urządzenie | Uwagi |
|---|---|
| boczny przycisk myszy | najtańsze — mysz już masz; ustaw `listen_exclusive = true` |
| pedał USB (np. PCsensor, iKKEGOL) | ręce wolne, klasyka dyktowania; zaprogramuj go na `F13`–`F24` |
| makropad, Stream Deck | Stream Deck (np. StreamController) może też wywołać `murmurtype toggle` bez `listen` |
| telefon przez GSConnect / KDE Connect | dodaj polecenie `murmurtype toggle`; to raczej pilot, bo mówisz do mikrofonu komputera |
| słuchawki Bluetooth | odradzane: przycisk to „play/pause”, a mikrofon słuchawek przełącza je w tryb rozmowy o gorszym dźwięku |

## Konfiguracja

Plik `~/.config/murmurtype/config.toml`; wszystkie klucze i wartości domyślne są opisane
w [config.example.toml](config.example.toml). Nieznany klucz lub zła wartość zatrzymuje
start usługi z czytelnym błędem w logach. Po zmianie:

```bash
systemctl --user restart murmurtype
```

Najczęściej zmieniane:

- `silence_threshold_db` — próg głośności mowy. W głośnym otoczeniu podnieś (np. `-35`),
  przy cichym mikrofonie obniż (np. `-45`).
- `silence_seconds` — jak długą pauzę uznać za koniec wypowiedzi. `0` wyłącza wykrywanie
  ciszy: nagranie kończy dopiero ponowne naciśnięcie skrótu (albo `max_seconds`). Przydaje
  się przy dłuższym dyktowaniu z przerwami na myślenie.
- `initial_prompt` — podpowiedź dla modelu, np. nazwy własne i żargon, których często
  używasz. Poprawia też interpunkcję, jeśli sam prompt jest poprawnie napisanym zdaniem.
- `model` — `small` lub `medium`, jeśli CPU jest za wolne; `large-v3` dla najlepszej jakości.
- `device` — `cpu` lub `cuda`, żeby wyłączyć automatyczny wybór.
- `listen_*` — przycisk urządzenia, patrz [Przycisk myszy lub pedał](#przycisk-myszy-lub-pedał).
  Po zmianie zrestartuj też `murmurtype-listen`.

## Ograniczenia i pułapki

- **Terminale wklejają na `Ctrl+Shift+V`.** Domyślne `Ctrl+V` nic w nich nie zrobi
  (tekst i tak jest w schowku). Na GNOME z Wayland nie da się łatwo sprawdzić, które
  okno jest aktywne, więc nie ma automatycznego przełączania. Jeśli głównie dyktujesz
  do terminala, ustaw `paste_keys = "ctrl+shift+v"` — w przeglądarkach to „wklej
  bez formatowania”, ale np. w edytorze VS Code otwiera podgląd Markdown.
- **Dyktowanie nadpisuje schowek.** `restore_clipboard = true` przywraca poprzedni tekst
  po wklejeniu (tylko tekst; obrazy i pliki w schowku przepadają). Jest wyłączone domyślnie,
  bo jeśli aplikacja wklei z opóźnieniem, może wkleić już przywróconą starą zawartość.
- **Trzymanie skrótu.** Jeśli klawisze skrótu są jeszcze wciśnięte w chwili wklejania,
  `Super`/`Alt` nałożą się na `Ctrl+V`. Skrót wystarczy nacisnąć i puścić.
- **GPU współdzielone z innymi procesami.** W trybie `auto` model trafia na GPU tylko,
  jeśli jest miejsce. Jeśli inny proces zajmie VRAM, gdy model GPU jest już załadowany,
  to ten inny proces może dostać błąd braku pamięci — ustaw wtedy `device = "cpu"`
  albo skróć `cuda_idle_unload_seconds`.
- **Tryb `auto` i pierwsze dyktowanie na GPU** — załadowanie modelu na kartę trwa kilka
  sekund, więc pierwsze dyktowanie po zwolnieniu VRAM jest wolniejsze.

## Diagnostyka

```bash
journalctl --user -u murmurtype -f
journalctl --user -u murmurtype-listen -f   # przycisk urządzenia
```

W logach widać m.in. powód zakończenia nagrania, długość audio, urządzenie (CPU/GPU)
i czas transkrypcji.

| Objaw | Przyczyna / rozwiązanie |
|---|---|
| „Usługa murmurtype nie działa” | `systemctl --user status murmurtype`; najczęściej błąd w `config.toml` |
| Tekst w schowku, ale się nie wkleja | `ydotoold` nie działa: `systemctl --user status ydotool`; brak dostępu do `/dev/uinput` |
| „Nic nie usłyszałem” | zły mikrofon domyślny (Ustawienia → Dźwięk) albo za wysoki `silence_threshold_db` |
| Nagranie nie kończy się samo | szum tła powyżej progu — podnieś `silence_threshold_db` |
| GPU nigdy nie jest używane | za mało wolnego VRAM (patrz log „Only N MB VRAM free”) lub instalacja bez `--cuda` |
| Przycisk nic nie robi | `journalctl --user -u murmurtype-listen`: „not found” = zła `listen_device`; „matches several devices” = podaj dłuższy fragment nazwy |
| Przycisk dalej robi „wstecz” | ustaw `listen_exclusive = true` |
| Błąd `libcudnn` / `libcublas` | zainstaluj z `--cuda`; demon sam ustawia `LD_LIBRARY_PATH` na biblioteki z PyPI |

## Rozwój

```bash
uv sync
uv run pytest
uv run murmurtype daemon   # demon z bieżącego kodu, w terminalu (zatrzymaj najpierw usługę)
```

Struktura `src/murmurtype/`:

| Moduł | Rola |
|---|---|
| `cli.py` | punkt wejścia: polecenia, start demona i listenera |
| `client.py` | klient gniazda demona |
| `listener.py` | przycisk urządzenia przez `evdev`, wyłączność z wirtualną kopią |
| `daemon.py` | serwer na gnieździe unix, maszyna stanów sesji dyktowania |
| `recorder.py` | nagrywanie przez `pw-record` i wykrywanie ciszy |
| `transcriber.py` | modele Whisper, wybór CPU/GPU, zwalnianie VRAM |
| `cuda.py` | wolna pamięć GPU, ścieżki bibliotek CUDA z PyPI |
| `output.py` | schowek i wklejanie przez `ydotool` |
| `notify.py` | powiadomienia `notify-send` |
| `config.py` | wczytywanie i walidacja `config.toml` |
| `paths.py` | ścieżka gniazda (`$XDG_RUNTIME_DIR/murmurtype.sock`) |

## Odinstalowanie

```bash
scripts/uninstall.sh
```

Skrypt zatrzymuje i usuwa usługi systemd (`murmurtype` i `murmurtype-listen`),
odinstalowuje narzędzie `uv` (`~/.local/bin/murmurtype`), usuwa ikonę aplikacji (także
z docka) i skrót „MurmurType” z GNOME. Pozostałe skróty
własne zostają nietknięte. Można go uruchomić ponownie bez błędów.

Konfiguracja w `~/.config/murmurtype/` zostaje, żeby ponowna instalacja ją zachowała.
Żeby usunąć także ją:

```bash
scripts/uninstall.sh --purge
```

Czego skrypt nie usuwa:

- **Modelu Whisper** w `~/.cache/huggingface/hub/` (ok. 1,6 GB) — to wspólna pamięć
  podręczna Hugging Face, z której mogą korzystać inne programy. Katalog modelu nazywa
  się `models--…faster-whisper-large-v3-turbo` i można go usunąć ręcznie.
- **Skrótów przejętych od GNOME przez `--force`** — przywróć je poleceniem
  `gsettings reset …`, które wypisał instalator.
- **Pakietów systemowych** (`ydotool`, `wl-clipboard` itd.), bo mogą być używane przez
  inne programy.

## Licencja

Copyright (C) 2026 Kamil Sztuke

MurmurType jest wolnym oprogramowaniem na licencji
[GNU General Public License w wersji 3](LICENSE) lub (według Twojego wyboru)
dowolnej późniejszej wersji. Możesz go używać, zmieniać i rozpowszechniać, ale każda
rozpowszechniana wersja pochodna musi być udostępniona na tej samej licencji, razem
z kodem źródłowym. Program jest dostarczany bez jakiejkolwiek gwarancji.
