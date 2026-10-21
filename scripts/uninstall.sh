#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Removes what scripts/install.sh set up: the systemd user service, the uv tool and
# the GNOME shortcut. The config is kept unless --purge is given. The Whisper model
# stays in the shared Hugging Face cache, which other programs may also use.
#
# Usage: scripts/uninstall.sh [--purge]
set -euo pipefail

purge=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --purge) purge=true; shift ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

unit_file="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/murmurtype.service"
if [[ -f "$unit_file" ]]; then
    systemctl --user disable --now murmurtype.service || true
    rm "$unit_file"
    systemctl --user daemon-reload
    echo "Removed service $unit_file"
fi

if uv tool list 2>/dev/null | grep -q '^murmurtype '; then
    uv tool uninstall murmurtype
fi

name="MurmurType"
media_keys="org.gnome.settings-daemon.plugins.media-keys"
mapfile -t custom_paths < <(gsettings get "$media_keys" custom-keybindings | grep -o "'[^']*'" | tr -d "'" || true)
remaining=()
for path in "${custom_paths[@]}"; do
    if [[ "$(gsettings get "$media_keys.custom-keybinding:$path" name)" == "'$name'" ]]; then
        dconf reset -f "$path"
        echo "Removed shortcut $path"
    else
        remaining+=("$path")
    fi
done
if [[ ${#remaining[@]} -ne ${#custom_paths[@]} ]]; then
    if [[ ${#remaining[@]} -eq 0 ]]; then
        gsettings set "$media_keys" custom-keybindings "[]"
    else
        list=$(printf "'%s', " "${remaining[@]}")
        gsettings set "$media_keys" custom-keybindings "[${list%, }]"
    fi
fi

config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/murmurtype"
if [[ -d "$config_dir" ]]; then
    if $purge; then
        rm -r "$config_dir"
        echo "Removed $config_dir"
    else
        echo "Kept $config_dir (use --purge to remove it)"
    fi
fi

echo "Built-in GNOME shortcuts taken over with --force are not restored automatically;"
echo "use the 'gsettings reset ...' command printed by install-shortcut.sh."
