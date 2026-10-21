#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

usage() {
    cat <<'HELP'
Usage: scripts/install.sh [OPTIONS]

Installs MurmurType: the `murmurtype` command (uv tool), the systemd user services
murmurtype and murmurtype-listen, the app launcher and a GNOME shortcut.
Running it again upgrades the installation and keeps ~/.config/murmurtype/config.toml;
pass the same options again (e.g. without --cuda the CUDA libraries are removed).

Options:
  --cuda              also install the CUDA libraries for GPU transcription (~1 GB)
  --listen            enable the device button service (murmurtype-listen);
                      set listen_device and listen_button in the config first,
                      find them with: murmurtype listen --discover
  --dock              pin the MurmurType launcher to the GNOME dock
  --shortcut ACCEL    GNOME shortcut, e.g. '<Super>backslash' (default: '<Primary><Shift>d',
                      i.e. Ctrl+Shift+D); repeat to give fallbacks, the first free one wins
  --force-shortcut    take the shortcut from built-in GNOME actions that already use it
  --no-shortcut       do not add a GNOME shortcut
  -h, --help          show this help

Examples:
  scripts/install.sh --cuda --dock
  scripts/install.sh --shortcut '<Super>d' --force-shortcut

Uninstall with: scripts/uninstall.sh [--purge]
HELP
}

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
with_cuda=false
enable_listener=false
pin_to_dock=false
install_shortcut=true
shortcut_arguments=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --cuda) with_cuda=true; shift ;;
        --listen) enable_listener=true; shift ;;
        --dock) pin_to_dock=true; shift ;;
        --shortcut)
            [[ $# -ge 2 ]] || { echo "--shortcut needs a value, e.g. '<Primary><Shift>d'" >&2; exit 1; }
            shortcut_arguments+=("$2"); shift 2 ;;
        --force-shortcut) shortcut_arguments=(--force "${shortcut_arguments[@]}"); shift ;;
        --no-shortcut) install_shortcut=false; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1 (see --help)" >&2; exit 1 ;;
    esac
done

missing=()
for tool in uv pw-record wl-copy wl-paste ydotool notify-send; do
    command -v "$tool" >/dev/null || missing+=("$tool")
done
if [[ ${#missing[@]} -gt 0 ]]; then
    echo "Missing tools: ${missing[*]}" >&2
    echo "Ubuntu: sudo apt install pipewire-bin wl-clipboard ydotool libnotify-bin (uv: https://docs.astral.sh/uv/)" >&2
    exit 1
fi

if ! systemctl --user is-active --quiet ydotool && ! systemctl is-active --quiet ydotoold; then
    echo "Warning: no running ydotool daemon found; automatic pasting will fail." >&2
fi

package="$project_dir"
$with_cuda && package="$project_dir[cuda]"
uv tool install --force --reinstall --python 3.12 "$package"

config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/murmurtype"
mkdir -p "$config_dir"
if [[ ! -f "$config_dir/config.toml" ]]; then
    cp "$project_dir/config.example.toml" "$config_dir/config.toml"
    echo "Created $config_dir/config.toml"
fi

unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$unit_dir"
cp "$project_dir/systemd/murmurtype.service" "$project_dir/systemd/murmurtype-listen.service" "$unit_dir/"
systemctl --user daemon-reload
systemctl --user enable murmurtype.service
systemctl --user restart murmurtype.service
echo "Service started. Logs: journalctl --user -u murmurtype -f"

if $enable_listener; then
    systemctl --user enable murmurtype-listen.service
    systemctl --user restart murmurtype-listen.service
    echo "Listener started. Logs: journalctl --user -u murmurtype-listen -f"
elif systemctl --user is-enabled --quiet murmurtype-listen.service; then
    systemctl --user restart murmurtype-listen.service
fi

applications_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$applications_dir"
sed "s|@BIN@|$HOME/.local/bin/murmurtype|g" "$project_dir/data/murmurtype.desktop" > "$applications_dir/murmurtype.desktop"
echo "Launcher installed: $applications_dir/murmurtype.desktop"

if $pin_to_dock; then
    favorites=$(gsettings get org.gnome.shell favorite-apps)
    if [[ "$favorites" != *"'murmurtype.desktop'"* ]]; then
        if [[ "$favorites" == "@as []" || "$favorites" == "[]" ]]; then
            gsettings set org.gnome.shell favorite-apps "['murmurtype.desktop']"
        else
            gsettings set org.gnome.shell favorite-apps "${favorites%]}, 'murmurtype.desktop']"
        fi
        echo "Pinned to the dock"
    fi
fi

if $install_shortcut; then
    "$project_dir/scripts/install-shortcut.sh" "${shortcut_arguments[@]}"
fi
