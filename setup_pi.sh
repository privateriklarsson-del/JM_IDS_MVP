#!/bin/bash
# JM IDS Checker — Raspberry Pi 5 setup
# Run: chmod +x setup_pi.sh && ./setup_pi.sh

set -e

echo "=== JM IDS Checker — Pi 5 Setup ==="

# System dependencies
echo "Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3-pip python3-venv

# Create venv
echo "Creating virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install Python packages
echo "Installing Python packages..."
pip install -r requirements.txt

# ifcopenshell on ARM64 — pip wheel may not exist, try conda fallback
if ! python3 -c "import ifcopenshell" 2>/dev/null; then
    echo ""
    echo "WARNING: ifcopenshell pip install failed on ARM64."
    echo "Try installing via conda instead:"
    echo "  conda install -c conda-forge ifcopenshell"
    echo ""
    echo "Or build from source:"
    echo "  https://github.com/IfcOpenShell/IfcOpenShell"
    echo ""
fi

# Create ids_files folder
mkdir -p ids_files

echo ""
echo "=== Setup complete ==="
echo ""
echo "Usage:"
echo "  1. Put your .ids files in ids_files/"
echo "  2. source .venv/bin/activate"
echo "  3. streamlit run app.py"
echo ""
echo "Access from other devices on your network:"
echo "  streamlit run app.py --server.address 0.0.0.0"
echo ""
