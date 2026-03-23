#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== G915 X RGB Controller - Install ==="

# Install udev rules
echo "Installing udev rules..."
sudo cp "$SCRIPT_DIR/data/99-g915x.rules" /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger

# Install systemd user service
echo "Installing systemd user service..."
mkdir -p ~/.config/systemd/user
sed "s|PYTHONPATH=.*|PYTHONPATH=$SCRIPT_DIR/src|" \
    "$SCRIPT_DIR/data/g915x-rgb.service" > ~/.config/systemd/user/g915x-rgb.service
systemctl --user daemon-reload
systemctl --user enable g915x-rgb.service
echo "  Service enabled (will apply profile on login)"

# Create desktop entry
echo "Installing desktop entry..."
mkdir -p ~/.local/share/applications
cat > ~/.local/share/applications/g915x-rgb.desktop << EOF
[Desktop Entry]
Name=G915 X RGB Controller
Comment=RGB lighting control for Logitech G915 X
Exec=bash -c 'cd $SCRIPT_DIR && PYTHONPATH=src python3 -m g915x_rgb.app'
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;logitech;g915;
EOF

echo ""
echo "=== Installation complete ==="
echo "  - Run the GUI:  cd $SCRIPT_DIR && PYTHONPATH=src python3 -m g915x_rgb.app"
echo "  - Apply now:     cd $SCRIPT_DIR && PYTHONPATH=src python3 -m g915x_rgb.apply"
echo "  - Service:       systemctl --user status g915x-rgb"
