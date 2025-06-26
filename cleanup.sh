#!/bin/bash

set -e

# Script created using AI - use at your own risk

echo "Removing iSCSI targets and backing stores..."

targetcli <<EOF
cd /

# Remove LUNs and targets
/iscsi delete iqn.2025-05.com.example:target1
/iscsi delete iqn.2025-05.com.example:target2
/iscsi delete iqn.2025-05.com.example:target3

# Remove backing stores
/backstores/fileio delete file1
/backstores/fileio delete file2
/backstores/fileio delete file3
/backstores/fileio delete partfile
/backstores/fileio delete file4

# Save configuration
saveconfig
EOF

echo "iSCSI targets and backing stores have been removed."
