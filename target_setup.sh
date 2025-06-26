#!/bin/bash

set -e

# Check if targetcli is installed
if ! command -v targetcli &> /dev/null; then
    echo "Error: targetcli is not installed."
    echo "Please install it using your system's package manager:"
    echo "  On Debian/Ubuntu: sudo apt install targetcli-fb"
    echo "  On RHEL/CentOS/Fedora: sudo dnf install targetcli"
    echo "  On Arch: sudo pacman -S targetcli-fb"
    exit 1
fi

# Directory for backing files
BACKING_DIR="/tmp/iscsi_test"
MNT_DIR="/mnt/iscsi_tmp"
mkdir -p "$BACKING_DIR" "$MNT_DIR"

echo "Creating and formatting test files..."

# Target 1
dd if=/dev/zero of=$BACKING_DIR/testfile1.img bs=1M count=10
dd if=/dev/zero of=$BACKING_DIR/testfile2.img bs=1M count=10
mkdir -p $BACKING_DIR/testdir
dd if=/dev/zero of=$BACKING_DIR/testdir/testfile3.img bs=1M count=10

mkfs.ext4 -F "$BACKING_DIR/testfile1.img"
mkfs.ext4 -F "$BACKING_DIR/testfile2.img"
mkfs.ext4 -F "$BACKING_DIR/testdir/testfile3.img"

for FILE in "$BACKING_DIR/testfile1.img" "$BACKING_DIR/testfile2.img" "$BACKING_DIR/testdir/testfile3.img"; do
    LOOP=$(losetup --find --show "$FILE")
    mount "$LOOP" "$MNT_DIR"
    echo "$(head -c 32 /dev/urandom | sha256sum)" > "$MNT_DIR/test.txt"
    mkdir -p "$MNT_DIR/data"
    echo "$(head -c 32 /dev/urandom | sha256sum)" > "$MNT_DIR/data/note.txt"
    umount "$MNT_DIR"
    losetup -d "$LOOP"
done

# Target 2 - Partitioned image
PART_IMG="$BACKING_DIR/partitioned.img"
dd if=/dev/zero of=$PART_IMG bs=1M count=100
parted -s $PART_IMG mklabel msdos
parted -s $PART_IMG mkpart primary ext4 1MiB 50MiB
parted -s $PART_IMG mkpart primary ext4 50MiB 99MiB

LOOP_DEV=$(losetup --find --partscan --show $PART_IMG)

mkfs.ext4 "${LOOP_DEV}p1"
mkfs.ext4 "${LOOP_DEV}p2"

for PART in "${LOOP_DEV}p1" "${LOOP_DEV}p2"; do
    mount "$PART" "$MNT_DIR"
    echo "$(head -c 32 /dev/urandom | sha256sum)" > "$MNT_DIR/test.txt"
    mkdir -p "$MNT_DIR/data"
    echo "$(head -c 32 /dev/urandom | sha256sum)" > "$MNT_DIR/data/note.txt"
    umount "$MNT_DIR"
done

losetup -d "$LOOP_DEV"

# Target 3
dd if=/dev/zero of=$BACKING_DIR/testfile6.img bs=1M count=10
mkfs.ext4 -F "$BACKING_DIR/testfile6.img"

LOOP=$(losetup --find --show "$BACKING_DIR/testfile6.img")
mount "$LOOP" "$MNT_DIR"
echo "$(head -c 32 /dev/urandom | sha256sum)" > "$MNT_DIR/test.txt"
mkdir -p "$MNT_DIR/data"
echo "$(head -c 32 /dev/urandom | sha256sum)" > "$MNT_DIR/data/note.txt"
umount "$MNT_DIR"
losetup -d "$LOOP"

echo "Setting up iSCSI targets with targetcli..."

targetcli <<EOF
cd /

# Target 1
/backstores/fileio create file1 $BACKING_DIR/testfile1.img
/backstores/fileio create file2 $BACKING_DIR/testfile2.img
/backstores/fileio create file3 $BACKING_DIR/testdir/testfile3.img
/iscsi create iqn.2025-05.com.example:target1
cd /iscsi/iqn.2025-05.com.example:target1/tpg1/luns
create /backstores/fileio/file1
create /backstores/fileio/file2
create /backstores/fileio/file3
cd ../acls

# Target 2
/backstores/fileio create partfile $PART_IMG
/iscsi create iqn.2025-05.com.example:target2
cd /iscsi/iqn.2025-05.com.example:target2/tpg1/luns
create /backstores/fileio/partfile
cd ../acls

# Target 3
/backstores/fileio create file4 $BACKING_DIR/testfile6.img
/iscsi create iqn.2025-05.com.example:target3
cd /iscsi/iqn.2025-05.com.example:target3/tpg1/luns
create /backstores/fileio/file4

/iscsi/iqn.2025-05.com.example:target1/tpg1/ set attribute authentication=0 demo_mode_write_protect=0 generate_node_acls=1
/iscsi/iqn.2025-05.com.example:target2/tpg1/ set attribute authentication=0 demo_mode_write_protect=0 generate_node_acls=1
/iscsi/iqn.2025-05.com.example:target3/tpg1/ set attribute authentication=0 demo_mode_write_protect=0 generate_node_acls=1

cd /
saveconfig
EOF

echo "Done. iSCSI targets created with test files and hash contents."
