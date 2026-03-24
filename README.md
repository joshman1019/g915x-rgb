# G915 X RGB Controller

A Linux GUI application for controlling per-key RGB lighting on the **Logitech G915 X** wireless mechanical keyboard.

No existing Linux tool (OpenRGB, g810-led, libratbag) supports the G915 X. This project communicates directly with the keyboard via HID++ 4.2 protocol over hidraw, providing full per-key color control.

## Features

- **Per-key RGB control** for 118 keys (standard keys, modifiers, G-keys, media, logo)
- **GTK4/libadwaita GUI** with interactive keyboard visualization
- **Group coloring** - set colors by key group (F-keys, modifiers, G-keys, etc.)
- **Per-key coloring** - click individual keys to set custom colors
- **Profile system** - save, load, and switch between color profiles
- **systemd service** - automatically applies your profile on login
- **Fast apply** - full profile in ~0.5 seconds

## Screenshot

The GUI shows an interactive keyboard layout where you can click keys to select them, edit colors with color pickers, and apply changes to the keyboard hardware in real-time.

## Requirements

- **Linux** (tested on Arch Linux with KDE Plasma/Wayland)
- **Logitech G915 X** keyboard (USB product ID `046d:c359`)
- **Python 3.11+**
- **GTK4** and **libadwaita** with Python GObject bindings
- User must be in the `input` group (for hidraw access)

### Arch Linux

```bash
# Dependencies (most are pre-installed on a typical desktop)
sudo pacman -S python-gobject gtk4 libadwaita python-cairo

# Add yourself to the input group (log out/in after)
sudo usermod -aG input $USER
```

## Installation

```bash
git clone https://github.com/joshman1019/g915x-rgb.git
cd g915x-rgb
./install.sh
```

The install script:

1. Installs udev rules for hidraw device access
2. Installs a systemd user service to apply your profile on login
3. Creates a desktop entry for the GUI

## Usage

### GUI

```bash
cd g915x-rgb
PYTHONPATH=src python3 -m g915x_rgb.app
```

1. Select or create a profile in the sidebar
2. Use the **Groups** tab to set colors for key groups
3. Click keys on the keyboard visualization, then use **Per-Key** to customize
4. Click **Apply** to send colors to the keyboard
5. Click **Save** to persist the profile

### CLI

```bash
# Apply the last-used profile
PYTHONPATH=src python3 -m g915x_rgb.apply

# Apply a specific profile by name
PYTHONPATH=src python3 -m g915x_rgb.apply "My Profile"
```

### systemd Service

```bash
# Check service status
systemctl --user status g915x-rgb

# Manually trigger profile apply
systemctl --user start g915x-rgb

# Disable auto-apply on login
systemctl --user disable g915x-rgb
```

## How It Works

The G915 X communicates via Logitech's HID++ 4.2 protocol over a USB HID interface. This project:

1. Discovers the keyboard's hidraw device (interface 2, vendor-specific HID++)
2. Queries the **PerKeyBacklightV2** feature (HID++ feature `0x8081`)
3. Sets individual key colors using the feature's set/commit protocol
4. Handles the G915 X's quirks:
   - Standard keys use HID keycode - 3 addressing
   - Modifier keys, G-keys, media keys, and logo use Logitech-specific addresses
   - Special keys require individual commit commands (cannot be batched)

### Key Address Map

| Key Group                      | Address Range     | Notes             |
| ------------------------------ | ----------------- | ----------------- |
| Standard keys (A-Z, 0-9, etc.) | `HID keycode - 3` | Standard offset   |
| Modifiers (Shift, Ctrl, Alt)   | `0x63-0x6F`       | Logitech-specific |
| G-keys (G1-G9)                 | `0xB4-0xBC`       | Logitech-specific |
| Media keys                     | `0x9B-0x9E`       | Logitech-specific |
| Logo                           | `0xD2`            | Logitech-specific |

## Contributing

Contributions welcome! Key areas for improvement:

- **Additional keyboard support** - the HID++ protocol is similar across Logitech keyboards. Adapting for G915, G815, or other models should be straightforward.
- **IFTTT/automation** - auto-switch profiles based on active window (KWin D-Bus integration)
- **Animation effects** - breathing, wave, reactive key effects
- **Backlight key** - address not yet identified
- **Better key layout** - pixel-perfect positioning to match the physical keyboard

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- Protocol research informed by [keyleds](https://github.com/keyleds/keyleds), [g810-led](https://github.com/MatMoul/g810-led), and the Logitech HID++ community
- Built with GTK4, libadwaita, and Cairo
