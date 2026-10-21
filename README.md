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
- Użytkownik z dostępem do `/dev/uinput` (zwykle grupa `input`) — potrzebne dla `ydotool`
- Opcjonalnie: karta NVIDIA ze sterownikiem obsługującym CUDA 12

```bash
sudo apt install pipewire-bin wl-clipboard ydotool libnotify-bin
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
3. instaluje i uruchamia usługę `~/.config/systemd/user/murmurtype.service`,
4. dodaje skrót GNOME (Ustawienia → Klawiatura → Skróty własne, pozycja „MurmurType”).
   Istniejące skróty własne zostają nietknięte.

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
| `murmurtype cancel` | przerwij nagranie bez rozpoznawania |
| `murmurtype status` | `idle`, `recording` albo `transcribing` |
| `murmurtype daemon` | uruchamia demona (robi to usługa systemd) |

Typowo: ustaw kursor w polu tekstowym, naciśnij skrót, powiedz zdanie i zamilknij.
Po ok. 2 s ciszy tekst się wklei.

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
| `cli.py` | punkt wejścia; klient gniazda i start demona |
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
systemctl --user disable --now murmurtype
rm ~/.config/systemd/user/murmurtype.service
uv tool uninstall murmurtype
```

Skrót usuń w Ustawienia → Klawiatura → Skróty własne. Konfiguracja zostaje w
`~/.config/murmurtype/`, model w `~/.cache/huggingface/`.
