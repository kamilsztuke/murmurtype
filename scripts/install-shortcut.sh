#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

usage() {
    cat <<'HELP'
Usage: scripts/install-shortcut.sh [--force] [ACCEL...]

Adds or updates the GNOME custom shortcut "MurmurType" that runs `murmurtype toggle`.
Other custom shortcuts are kept; an existing "MurmurType" entry is reused.

GNOME silently ignores a custom shortcut whose keys are already taken, so each ACCEL
is checked against built-in GNOME shortcuts and other custom shortcuts, in the given
order, and the first free one is used. Default: '<Primary><Shift>d' (Ctrl+Shift+D).

ACCEL uses the gsettings format: <Primary> = Ctrl, <Super>, <Alt>, <Shift>, then the
key in lowercase, e.g. '<Super>d', '<Primary><Alt>d', '<Super>backslash'.

Options:
  --force     use the first ACCEL even if a built-in GNOME action uses it: the keys
              are removed from that action, and the command to restore it
              (gsettings reset ...) is printed; other custom shortcuts are never taken
  -h, --help  show this help

Examples:
  scripts/install-shortcut.sh
  scripts/install-shortcut.sh '<Super>d' '<Primary><Shift>d'
  scripts/install-shortcut.sh --force '<Super>d'
HELP
}

force=false
candidates=()
for argument in "$@"; do
    case "$argument" in
        --force) force=true ;;
        -h|--help) usage; exit 0 ;;
        -*) echo "Unknown option: $argument (see --help)" >&2; exit 1 ;;
        *) candidates+=("$argument") ;;
    esac
done
[[ ${#candidates[@]} -gt 0 ]] || candidates=("<Primary><Shift>d")

name="MurmurType"
command="$HOME/.local/bin/murmurtype toggle"
media_keys="org.gnome.settings-daemon.plugins.media-keys"
custom_base="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"
builtin_schemas=(
    org.gnome.desktop.wm.keybindings
    org.gnome.shell.keybindings
    org.gnome.mutter.keybindings
    org.gnome.mutter.wayland.keybindings
    "$media_keys"
)

# '<Primary><Shift>d', '<Shift><Control>D' and '<Ctrl><Shift>d' are the same accelerator.
normalize_accelerator() {
    local accelerator="${1,,}"
    accelerator="${accelerator//<primary>/<control>}"
    accelerator="${accelerator//<ctrl>/<control>}"
    local key="${accelerator##*>}"
    local modifiers
    modifiers=$(grep -o '<[a-z0-9_]*>' <<<"$accelerator" | sort | tr -d '\n' || true)
    echo "$modifiers$key"
}

quoted_items() {
    grep -o "'[^']*'" <<<"$1" | tr -d "'" || true
}

mapfile -t custom_paths < <(quoted_items "$(gsettings get "$media_keys" custom-keybindings)")

target=""
for path in "${custom_paths[@]}"; do
    if [[ "$(gsettings get "$media_keys.custom-keybinding:$path" name)" == "'$name'" ]]; then
        target="$path"
        break
    fi
done

installed_schemas=$(gsettings list-schemas)

# Fills custom_conflicts (other custom shortcuts) and builtin_conflicts ("schema key").
find_conflicts() {
    local wanted
    wanted=$(normalize_accelerator "$1")
    custom_conflicts=()
    builtin_conflicts=()

    local path other
    for path in "${custom_paths[@]}"; do
        [[ "$path" == "$target" ]] && continue
        other=$(gsettings get "$media_keys.custom-keybinding:$path" binding | tr -d "'")
        if [[ -n "$other" && "$(normalize_accelerator "$other")" == "$wanted" ]]; then
            custom_conflicts+=("$(gsettings get "$media_keys.custom-keybinding:$path" name) ($path)")
        fi
    done

    local schema key value accelerator
    for schema in "${builtin_schemas[@]}"; do
        grep -qx "$schema" <<<"$installed_schemas" || continue
        while read -r key; do
            value=$(gsettings get "$schema" "$key")
            [[ "$value" == "["* ]] || continue
            for accelerator in $(quoted_items "$value"); do
                if [[ "$(normalize_accelerator "$accelerator")" == "$wanted" ]]; then
                    builtin_conflicts+=("$schema $key")
                    break
                fi
            done
        done < <(gsettings list-keys "$schema")
    done
}

remove_from_builtin() {
    local binding="$1" wanted schema key remaining accelerator conflict
    wanted=$(normalize_accelerator "$binding")
    for conflict in "${builtin_conflicts[@]}"; do
        read -r schema key <<<"$conflict"
        remaining=""
        for accelerator in $(quoted_items "$(gsettings get "$schema" "$key")"); do
            [[ "$(normalize_accelerator "$accelerator")" == "$wanted" ]] || remaining+="'$accelerator', "
        done
        gsettings set "$schema" "$key" "[${remaining%, }]"
        echo "Removed $binding from $schema $key (restore: gsettings reset $schema $key)"
    done
}

binding=""
for candidate in "${candidates[@]}"; do
    find_conflicts "$candidate"
    if [[ ${#custom_conflicts[@]} -eq 0 && ${#builtin_conflicts[@]} -eq 0 ]]; then
        binding="$candidate"
        break
    fi
    if $force && [[ ${#custom_conflicts[@]} -eq 0 ]]; then
        remove_from_builtin "$candidate"
        binding="$candidate"
        break
    fi
    conflicts=("${custom_conflicts[@]}" "${builtin_conflicts[@]}")
    printf '%s is taken by: %s\n' "$candidate" "$(IFS=,; echo "${conflicts[*]}")" >&2
    $force && { echo "--force does not override other custom shortcuts." >&2; exit 2; }
done

if [[ -z "$binding" ]]; then
    echo "No free shortcut among: ${candidates[*]}. Pass another one, or --force." >&2
    exit 2
fi

if [[ -z "$target" ]]; then
    index=0
    while printf '%s\n' "${custom_paths[@]}" | grep -qx "$custom_base/custom$index/"; do
        index=$((index + 1))
    done
    target="$custom_base/custom$index/"
    custom_paths+=("$target")
    list=$(printf "'%s', " "${custom_paths[@]}")
    gsettings set "$media_keys" custom-keybindings "[${list%, }]"
fi

gsettings set "$media_keys.custom-keybinding:$target" name "$name"
gsettings set "$media_keys.custom-keybinding:$target" command "$command"
gsettings set "$media_keys.custom-keybinding:$target" binding "$binding"
echo "Shortcut $binding -> $command ($target)"
