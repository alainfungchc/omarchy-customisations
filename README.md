# Omarchy Customisations

Scripts to reapply customisations after Omarchy base updates.

When Omarchy updates overwrite config files, run these scripts to restore personal tweaks.

## Scripts

### `scripts/fix-waybar-vpn.py`

Adds VPN toggle button to waybar. Modifies:
- `~/.config/waybar/config.jsonc` - adds custom/vpn module
- `~/.config/waybar/style.css` - adds styling
- `~/.config/waybar/scripts/vpn-toggle.sh` - creates toggle script

```bash
python scripts/fix-waybar-vpn.py
```

Safe to run multiple times (idempotent). Creates `.bak` backups before modifying files.
