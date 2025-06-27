# iSCSI Target and Initiator Testing Toolkit

This repository contains a script for setting up iSCSI targets locally and another to help automate interacting them. It's intended for development, testing, and educational purposes.

## Contents

- `setup_targets.sh`: A Bash script to create test backing files, format them, populate with sample data, and configure iSCSI targets using `targetcli`.
- `enumscsi.py`: A Python script to discover, log in to, mount, and optionally interact with iSCSI targets from the initiator side.

---
## EnumSCSI
The script's main purpose is to interactively mount and enumerate the iSCSI targets with the `--interact` flag. I was working on an output function that lists and saves the contents of each target to a file but haven't completed it yet. For now just avoid using the `--output` flag. 
