#!/usr/bin/env bash
# Installs dictate as a uv tool, a systemd user service and a GNOME shortcut.
# The default shortcut is <Primary><Shift>d (Ctrl+Shift+D); see scripts/install-shortcut.sh.
#
# Usage: scripts/install.sh [--cuda] [--shortcut '<Primary><Shift>d'] [--force-shortcut] [--no-shortcut]
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
with_cuda=false
install_shortcut=true
shortcut_arguments=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --cuda) with_cuda=true; shift ;;
        --shortcut) shortcut_arguments+=("$2"); shift 2 ;;
        --force-shortcut) shortcut_arguments=(--force "${shortcut_arguments[@]}"); shift ;;
        --no-shortcut) install_shortcut=false; shift ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
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

config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/dictate"
mkdir -p "$config_dir"
if [[ ! -f "$config_dir/config.toml" ]]; then
    cp "$project_dir/config.example.toml" "$config_dir/config.toml"
    echo "Created $config_dir/config.toml"
fi

unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$unit_dir"
cp "$project_dir/systemd/dictate.service" "$unit_dir/dictate.service"
systemctl --user daemon-reload
systemctl --user enable dictate.service
systemctl --user restart dictate.service
echo "Service started. Logs: journalctl --user -u dictate -f"

if $install_shortcut; then
    "$project_dir/scripts/install-shortcut.sh" "${shortcut_arguments[@]}"
fi
