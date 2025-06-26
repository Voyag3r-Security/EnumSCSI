import subprocess
import os
import time
import re
import argparse
import sys
import shutil
import shlex

# Check for iscsiadm
def check_iscsiadm():
    if not shutil.which("iscsiadm"):
        os_name = platform.system()
        print("Error: 'iscsiadm' is not installed.")
        print("Please install it using your system's package manager:")
        if os_name == "Linux":
            distro = platform.linux_distribution()[0].lower() if hasattr(platform, 'linux_distribution') else ""
            if "ubuntu" in distro or "debian" in distro:
                print("  sudo apt update && sudo apt install open-iscsi")
            elif "centos" in distro or "fedora" in distro or "red hat" in distro:
                print("  sudo dnf install iscsi-initiator-utils")
            elif "arch" in distro:
                print("  sudo pacman -S open-iscsi")
            else:
                print("  Please search for how to install 'iscsiadm' for your Linux distribution.")
        else:
            print("  'iscsiadm' is typically only available on Linux systems.")
        sys.exit(1)

def run_command(command):
    try:
        result = subprocess.check_output(command, stderr=subprocess.STDOUT)
        return result.decode('utf-8')
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.output.decode('utf-8')}")
        return None

def is_valid_ip(ip):
    regex = r"^(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\." \
            r"(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\." \
            r"(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\." \
            r"(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    return re.match(regex, ip) is not None

def write_output(output, filename):
    with open(filename, 'a') as f:
        f.write(output)

def discover_iscsi_targets(target_ip, port):
    command = ["iscsiadm", "-m", "discovery", "-t", "st", "-p", f"{target_ip}:{port}"]
    output = run_command(command)
    if output:
        targets = []
        for line in output.splitlines():
            parts = line.split()
            if len(parts) == 2:
                ip_port, target = parts
                targets.append((ip_port, target))
        return targets
    return []

def login_to_iscsi_target(ip_port, target):
    command = ["iscsiadm", "-m", "node", "--targetname", target, "-p", ip_port, "--login"]
    return run_command(command)

def find_device(before_devices):
    print("Waiting for new iSCSI devices to appear...")
    for _ in range(10):
        time.sleep(1)
        after_devices = {d for d in os.listdir("/dev") if re.match(r"^(sd|nvme|mmcblk)\w+", d)}
        new_devices = after_devices - before_devices
        if new_devices:
            break

    if not new_devices:
        return None

    sorted_devices = sorted(new_devices)
    if len(sorted_devices) == 1:
        base_device = sorted_devices[0]
    else:
        print("\nMultiple new devices detected:")
        for idx, dev in enumerate(sorted_devices, 1):
            print(f"{idx}. /dev/{dev}")
        while True:
            try:
                choice = int(input(f"Select a device (1-{len(sorted_devices)}): "))
                if 1 <= choice <= len(sorted_devices):
                    base_device = sorted_devices[choice - 1]
                    break
            except ValueError:
                print("Please enter a number.")
    
    partitions = [f"/dev/{d}" for d in sorted(os.listdir("/dev")) if d.startswith(base_device) and d != base_device]
    if not partitions:
        return f"/dev/{base_device}"
    
    print("\nAvailable partitions:")
    for idx, part in enumerate(partitions, 1):
        print(f"{idx}. {part}")
    while True:
        try:
            choice = int(input(f"Select a partition to mount (1-{len(partitions)}): "))
            if 1 <= choice <= len(partitions):
                return partitions[choice - 1]
        except ValueError:
            print("Please enter a number.")

def check_device_filesystem(device):
    try:
        subprocess.check_output(["blkid", device], stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError:
        return False

def mount_device(device):
    mount_point = "/mnt/iscsi"
    if not os.path.exists(mount_point):
        os.makedirs(mount_point)
    if not check_device_filesystem(device):
        return None
    command = ["mount", "-o", "ro", device, mount_point]
    result = run_command(command)
    if result is None:
        return None
    return mount_point

def list_contents(mount_point):
    try:
        return os.listdir(mount_point)
    except Exception:
        return []

def logout_iscsi_target(target, ip_port):
    command = ["iscsiadm", "-m", "node", "--targetname", target, "-p", ip_port, "--logout"]
    return run_command(command)

def check_root():
    if os.geteuid() != 0:
        print("This script must be run as root. Exiting.")
        sys.exit(1)

def copy_file(src, dest):
    try:
        shutil.copy(src, dest)
        print(f"Copied {src} to {dest}")
    except Exception as e:
        print(f"Error copying file: {e}")

def interactive_mode(mount_point):
    current_dir = mount_point
    while True:
        print(f"\nCurrent Directory: {current_dir}")
        command_line = input(f"{current_dir}$ ").strip()
        if not command_line:
            continue
        try:
            args = shlex.split(command_line)
        except ValueError as e:
            print(f"Parsing error: {e}")
            continue
        if not args:
            continue
        cmd = args[0].lower()

        if cmd == "exit":
            print("Exiting interactive mode...")
            break
        elif cmd == "ls":
            try:
                print("\n".join(os.listdir(current_dir)) or "Directory is empty.")
            except FileNotFoundError:
                print(f"Directory {current_dir} not found.")
        elif cmd == "cd" and len(args) > 1:
            new_dir = args[1]
            if new_dir == "..":
                current_dir = os.path.dirname(current_dir)
            else:
                new_path = os.path.join(current_dir, new_dir)
                if os.path.isdir(new_path):
                    current_dir = new_path
                else:
                    print(f"Directory {new_dir} not found.")
        elif cmd == "pwd":
            print(current_dir)
        elif cmd == "help":
            print("Commands: ls, cd <dir>, copy <file> <dest>, cat <file>, less <file>, pwd, exit")
        elif cmd == "copy" and len(args) == 3:
            src_file = os.path.join(current_dir, args[1])
            if os.path.exists(src_file):
                copy_file(src_file, args[2])
            else:
                print(f"File {args[1]} does not exist.")
        elif cmd in ("cat", "less") and len(args) == 2:
            filepath = os.path.join(current_dir, args[1])
            if os.path.exists(filepath):
                pager = "less" if cmd == "less" else "cat"
                subprocess.run([pager, filepath])
            else:
                print(f"File {args[1]} does not exist.")
        else:
            print("Unknown command. Use 'help' for a list of commands.")

def cleanup(device, target, ip_port):
    if device:
        run_command(["umount", device])
        print(f"Device {device} unmounted.")
    if target and ip_port:
        logout_result = logout_iscsi_target(target, ip_port)
        if logout_result:
            print(f"Logged out from {target} at {ip_port}")

def select_target(targets):
    print("\nAvailable iSCSI Targets:")
    for idx, (ip_port, target) in enumerate(targets, 1):
        print(f"{idx}. {target} at {ip_port}")
    while True:
        try:
            choice = int(input(f"Select a target (1-{len(targets)}): "))
            if 1 <= choice <= len(targets):
                return targets[choice - 1]
        except ValueError:
            print("Invalid input. Please enter a number.")

def parse_args():
    parser = argparse.ArgumentParser(description="iSCSI Target Discovery and Operations")
    parser.add_argument("target_ip", help="IP address of the iSCSI target")
    parser.add_argument("-o", "--output", help="Output file to save results", default=None)
    parser.add_argument("-p", "--port", type=int, default=3260, help="Port for the iSCSI target (default is 3260)")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--interactive", action="store_true", help="Enable interactive mode for browsing and file copying")
    group.add_argument("--all", action="store_true", help="List contents of all discovered iSCSI targets")

    return parser.parse_args()

def main(target_ip, port, output_file=None, interactive=False, list_all=False):
    check_root()
    check_iscsiadm()
    if not is_valid_ip(target_ip):
        print(f"Invalid IP address format: {target_ip}")
        return

    if output_file:
        with open(output_file, 'w') as f:
            f.write(f"Output for iSCSI target discovery and operations\n\n")

    targets = discover_iscsi_targets(target_ip, port)
    if not targets:
        print("No iSCSI targets found.")
        return

    if list_all:
        for selected_ip_port, selected_target in targets:
            device = None
            try:
                print(f"\nProcessing target: {selected_target} at {selected_ip_port}")
                before_devices = {d for d in os.listdir("/dev") if re.match(r"^(sd|nvme|mmcblk)\w+", d)}
                login_result = login_to_iscsi_target(selected_ip_port, selected_target)
                if not login_result:
                    print("Login failed.")
                    continue

                device = find_device(before_devices)
                if not device:
                    print("No new device found.")
                    continue

                mount_point = mount_device(device)
                if not mount_point:
                    print("Mount failed.")
                    continue

                files = list_contents(mount_point)
                contents_output = f"Files in {mount_point} for target {selected_target}:\n"
                contents_output += "\n".join(files) + "\n" if files else "No files found.\n"
                print(contents_output, end="")
                if output_file:
                    write_output(contents_output, output_file)

            finally:
                cleanup(device, selected_target, selected_ip_port)

    else:
        while True:
            device = None
            selected_target = None
            selected_ip_port = None

            try:
                selected_ip_port, selected_target = select_target(targets)
                print(f"Selected target: {selected_target} at {selected_ip_port}")

                before_devices = {d for d in os.listdir("/dev") if re.match(r"^(sd|nvme|mmcblk)\w+", d)}
                login_result = login_to_iscsi_target(selected_ip_port, selected_target)
                if not login_result:
                    print("Login to target failed.")
                    continue

                device = find_device(before_devices)
                if not device:
                    print("iSCSI device not found.")
                    continue

                mount_point = mount_device(device)
                if not mount_point:
                    print("Failed to mount device.")
                    continue

                if interactive:
                    interactive_mode(mount_point)
                else:
                    files = list_contents(mount_point)
                    contents_output = f"Files in {mount_point}:\n"
                    contents_output += "\n".join(files) + "\n" if files else "No files found.\n"
                    print(contents_output, end="")
                    if output_file:
                        write_output(contents_output, output_file)

                response = input("\nWould you like to choose another iSCSI target? (y/n): ").strip().lower()
                if response != 'y':
                    break

            finally:
                cleanup(device, selected_target, selected_ip_port)

if __name__ == "__main__":
    args = parse_args()
    main(args.target_ip, args.port, args.output, interactive=args.interactive, list_all=args.all)
