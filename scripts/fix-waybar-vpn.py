#!/usr/bin/env python3
"""
Modify waybar configuration files to add VPN toggle support.

This script:
1. Adds "custom/vpn" module to modules-right in config.jsonc
2. Adds the custom/vpn module definition to config.jsonc
3. Appends VPN styling to style.css
4. Creates the vpn-toggle.sh script

The script is idempotent - safe to run multiple times.
"""

import json
import os
import re
import shutil
import stat
import sys

# Nerd Font icons (verified codepoints)
ICON_LOCK = "\U000F033E"  # nf-md-lock (connected)
ICON_LOCK_OPEN = "\U000F0FC6"  # nf-md-lock_open_outline (disconnected)


def expand_path(path: str) -> str:
    """Expand ~ to home directory."""
    return os.path.expanduser(path)


def backup_file(path: str) -> str:
    """Create a .bak backup of a file. Returns backup path."""
    backup_path = path + ".bak"
    shutil.copy2(path, backup_path)
    return backup_path


def strip_jsonc_comments(content: str) -> str:
    """
    Strip comments from JSONC content to produce valid JSON.
    Handles // line comments and /* block comments */.
    Preserves strings containing comment-like sequences.
    """
    result = []
    i = 0
    in_string = False
    escape_next = False

    while i < len(content):
        char = content[i]

        if escape_next:
            result.append(char)
            escape_next = False
            i += 1
            continue

        if char == '\\' and in_string:
            result.append(char)
            escape_next = True
            i += 1
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            result.append(char)
            i += 1
            continue

        if in_string:
            result.append(char)
            i += 1
            continue

        # Not in string - check for comments
        if content[i:i+2] == '//':
            # Line comment - skip to end of line
            while i < len(content) and content[i] != '\n':
                i += 1
            continue

        if content[i:i+2] == '/*':
            # Block comment - skip to */
            i += 2
            while i < len(content) - 1 and content[i:i+2] != '*/':
                i += 1
            i += 2  # Skip the */
            continue

        result.append(char)
        i += 1

    return ''.join(result)


def remove_trailing_commas(content: str) -> str:
    """Remove trailing commas before ] or } to make valid JSON."""
    content = re.sub(r',(\s*[}\]])', r'\1', content)
    return content


def parse_jsonc(content: str) -> dict:
    """Parse JSONC content (JSON with comments and trailing commas)."""
    stripped = strip_jsonc_comments(content)
    stripped = remove_trailing_commas(stripped)
    return json.loads(stripped)


def modify_config_jsonc(path: str) -> bool:
    """
    Modify config.jsonc to add VPN module.
    Returns True if modifications were made, False if already configured.
    """
    if not os.path.exists(path):
        print(f"ERROR: Config file not found: {path}", file=sys.stderr)
        sys.exit(1)

    with open(path, 'r') as f:
        content = f.read()

    # Parse to validate and check existing configuration
    config = parse_jsonc(content)

    # Check modules-right exists
    if "modules-right" not in config:
        print("ERROR: 'modules-right' not found in config", file=sys.stderr)
        sys.exit(1)

    # Idempotency checks
    has_vpn_in_modules = "custom/vpn" in config.get("modules-right", [])
    has_vpn_definition = "custom/vpn" in config

    if has_vpn_in_modules and has_vpn_definition:
        print(f"config.jsonc: Already configured, skipping")
        return False

    # Backup before making changes
    backup_path = backup_file(path)
    print(f"Backed up: {path} -> {backup_path}")

    modified = False

    # Insert "custom/vpn" after "group/tray-expander" in modules-right
    if not has_vpn_in_modules:
        # Look for "group/tray-expander" specifically and insert after it
        tray_pattern = r'("group/tray-expander"\s*)(,)'
        tray_match = re.search(tray_pattern, content)

        if tray_match:
            # Insert after "group/tray-expander",
            insert_pos = tray_match.end()
            content = content[:insert_pos] + '\n    "custom/vpn",' + content[insert_pos:]
            modified = True
        else:
            # Fallback: find modules-right array and insert at beginning
            modules_pattern = r'("modules-right"\s*:\s*\[)(\s*)'
            modules_match = re.search(modules_pattern, content)
            if modules_match:
                insert_pos = modules_match.end()
                content = content[:insert_pos] + '"custom/vpn",\n    ' + content[insert_pos:]
                modified = True
            else:
                print("ERROR: Could not find modules-right array in config", file=sys.stderr)
                sys.exit(1)

    # Add the custom/vpn module definition before the final closing brace
    if not has_vpn_definition:
        # Find the final closing brace of the root object
        last_brace_pos = content.rfind('}')
        if last_brace_pos == -1:
            print("ERROR: Could not find closing brace in config", file=sys.stderr)
            sys.exit(1)

        # Check if we need a leading comma (JSONC may have trailing commas)
        pre_brace_content = content[:last_brace_pos].rstrip()
        needs_comma = not pre_brace_content.endswith(',')

        vpn_module = '''
  "custom/vpn": {
    "format": "{}",
    "return-type": "json",
    "exec": "~/.config/waybar/scripts/vpn-toggle.sh",
    "on-click": "~/.config/waybar/scripts/vpn-toggle.sh toggle",
    "interval": 5
  }'''

        if needs_comma:
            vpn_module = ',' + vpn_module

        # Insert before the final }
        content = content[:last_brace_pos] + vpn_module + '\n' + content[last_brace_pos:]
        modified = True

    if modified:
        with open(path, 'w') as f:
            f.write(content)

        print(f"Modified: {path}")
        if not has_vpn_in_modules:
            print("  - Added 'custom/vpn' to modules-right")
        if not has_vpn_definition:
            print("  - Added custom/vpn module definition")

    return modified


def modify_style_css(path: str) -> bool:
    """
    Append VPN styling to style.css.
    Returns True if modifications were made, False if already configured.
    """
    if not os.path.exists(path):
        print(f"ERROR: Style file not found: {path}", file=sys.stderr)
        sys.exit(1)

    with open(path, 'r') as f:
        content = f.read()

    # Idempotency check: look for #custom-vpn rule
    if '#custom-vpn' in content:
        print(f"style.css: Already configured, skipping")
        return False

    # Backup
    backup_path = backup_file(path)
    print(f"Backed up: {path} -> {backup_path}")

    css_block = '''
#custom-vpn {
  min-width: 12px;
  margin-left: 7.5px;
  margin-right: 17px;
}
'''

    with open(path, 'a') as f:
        f.write(css_block)

    print(f"Modified: {path}")
    print("  - Appended #custom-vpn styling")
    return True


def get_vpn_script_content() -> str:
    """Generate the VPN toggle script content with verified icon codepoints."""
    return f'''#!/bin/bash
INTERFACE="home"

if ip link show "$INTERFACE" 2>/dev/null | grep -q "state UP"; then
    if [[ "$1" == "toggle" ]]; then
        sudo wg-quick down "$INTERFACE"
    else
        echo '{{"text": "{ICON_LOCK}", "tooltip": "VPN: Connected", "class": "connected"}}'
    fi
else
    if [[ "$1" == "toggle" ]]; then
        sudo wg-quick up "$INTERFACE"
    else
        echo '{{"text": "{ICON_LOCK_OPEN}", "tooltip": "VPN: Disconnected", "class": "disconnected"}}'
    fi
fi
'''


def create_vpn_script(path: str) -> bool:
    """
    Create the vpn-toggle.sh script.
    Returns True if created/updated, False if already exists with correct content.
    """
    scripts_dir = os.path.dirname(path)
    script_content = get_vpn_script_content()

    # Idempotency check: compare with existing file
    if os.path.exists(path):
        with open(path, 'r') as f:
            existing_content = f.read()
        if existing_content == script_content:
            print(f"vpn-toggle.sh: Already configured, skipping")
            return False

    # Create scripts directory if needed
    if not os.path.exists(scripts_dir):
        os.makedirs(scripts_dir)
        print(f"Created directory: {scripts_dir}")

    with open(path, 'w') as f:
        f.write(script_content)

    # Make executable
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print(f"Created: {path}")
    print("  - Made executable")
    print(f"  - Lock icon: U+{ord(ICON_LOCK):04X}")
    print(f"  - Lock open icon: U+{ord(ICON_LOCK_OPEN):04X}")
    return True


def main():
    """Main entry point."""
    config_path = expand_path("~/.config/waybar/config.jsonc")
    style_path = expand_path("~/.config/waybar/style.css")
    script_path = expand_path("~/.config/waybar/scripts/vpn-toggle.sh")

    print("Fixing waybar config for VPN toggle support...\n")

    config_modified = modify_config_jsonc(config_path)
    print()
    style_modified = modify_style_css(style_path)
    print()
    script_modified = create_vpn_script(script_path)

    print()
    if config_modified or style_modified or script_modified:
        print("Done! Restart waybar to apply changes:")
        print("  killall waybar && waybar &")
    else:
        print("Nothing to do - all files already configured.")


if __name__ == "__main__":
    main()
