#!/bin/bash

# Build the package using hatch
echo "Building package with hatch..."
hatch build

# Uninstall existing edgartools
echo "Uninstalling existing edgartools..."
pip uninstall -y edgartools

# Install the latest build
echo "Installing latest build..."
latest_wheel=$(ls -tr dist/*.whl | tail -n1)
pip install "$latest_wheel"

echo "Reinstalled using: $latest_wheel"

# Open python
python
