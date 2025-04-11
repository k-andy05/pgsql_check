#!/usr/bin/env python3

import os
import subprocess
import hashlib
import shutil
import sys
from pathlib import Path


# Find OS type
def get_os_info():
    if os.path.exists("/etc/centos-release"):
        return "centos"
    elif os.path.exists("/etc/os-release"):
        with open("/etc/os-release", "r") as f:
            os_file = f.readline()
            if "Ubuntu" in os_file:
                return "ubuntu"
    return None


# Self-explanatory function
def is_postgresql_installed():
    result = shutil.which("psql")
    if result:
        print("Postgresql is on device.")
        return True
    else:
        print(f"Postgresql is not found on device.")
        return False


# Will try and execute CLI input as an array of separate words
def run_cli(command_array):
    try:
        print(f"Running {' '.join(command_array)}...")
        subprocess.run(command_array, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e}")
        sys.exit(1)


# Self-explanatory function
def install_postgresql(specific_os):
    if specific_os == "ubuntu":
        run_cli(["sudo", "apt", "update"])
        run_cli(["sudo", "apt", "-y", "install", "postgresql"])
    else:
        version = input("What version of postgresql do you want to install?: ")
        run_cli(["sudo", "yum", "-y", "install", "https://download.postgresql.org/pub/repos/yum/reporpms/EL-7-x86_64/pgdg-redhat-repo-latest.noarch.rpm"])
        run_cli(["sudo", "yum", "-y", "install", f"postgresql{version}-server"])
        run_cli(["sudo", f"/usr/pgsql-{version}/bin/postgresql-{version}-setup", "initdb"])
        run_cli(["sudo", "systemctl", "enable", f"postgresql-{version}"])
        run_cli(["sudo", "systemctl", "start", f"postgresql-{version}"])


# returns a hash value of a directory
def hash_dir(file_path_):
    path = Path(file_path_)
    hash_obj = hashlib.new('sha256')
    for root, dirs, files in os.walk(path, topdown=True):
        dirs.sort()
        files.sort()
        for name in files:
            file_path = Path(root) / name
            rel_path = file_path.relative_to(path)
            hash_obj.update(str(rel_path).encode())
            with open(file_path, 'rb') as f:
                while chunk := f.read(65536):
                    hash_obj.update(chunk)
        if not files and not dirs:
            hash_obj.update(str(Path(root).relative_to(path)).encode())
    return hash_obj.hexdigest()

def get_suffix(path_str):
    path = Path(path_str).resolve()
    parts = path.parts
    if "postgresql" in parts:
        index = parts.index("postgresql")
        trimmed = Path(*parts[index:])
        return trimmed
    else:
        return path


# Checks hashes between two directories
def check_hashes(backup_raw, postgresql_raw):
    # I need to just get it from postgresql downwards
    backup = get_suffix(backup_raw)
    postgresql = get_suffix(postgresql_raw)
    print("Checking hashes...")
    backup_hexdigest = hash_dir(backup)
    postgresql_hexdigest = hash_dir(postgresql)
    if backup_hexdigest != postgresql_hexdigest:
        print("A postgresql file has been tampered with! Restoring from backup now...")
        run_cli(["sudo", "rsync", "-a", f"{backup_raw}", "/etc/"])
        print("Backup succesfully copied over!")


# Creates a backup of a directory
def create_backup(backup_path, postgresql_path):
    print(f"Creating backup at {backup_path}...")
    run_cli(["sudo", "rsync", "-a", f"{postgresql_path}", f"{backup_path}"])
    print("Backup successfully made!")


def remove_postgres(os_type):
    if os_type == "ubuntu":
        try:
            run_cli(["sudo", "systemctl", "stop", "postgresql"])
        except Exception as e:
            pass
        try:
            run_cli(["sudo", "apt", "--purge", "remove", "postgresql\*", "-y"])
        except Exception as e:
            pass
        try:
            run_cli(["sudo", "apt", "autoremove", "y"])
        except Exception as e:
            pass
        try:
            run_cli(["sudo", "apt", "autoclean"])
        except Exception as e:
            pass
        try:
            run_cli(["sudo", "rm", "-rf", "/etc/postgresql"])
        except Exception as e:
            pass
        try:
            run_cli(["sudo", "rm", "-rf", "/var/lib/postgresql"])
        except Exception as e:
            pass
        try:
            run_cli(["sudo", "rm", "-rf", "/var/log/postgresql"])
        except Exception as e:
            pass
        try:
            run_cli(["sudo", "rm", "-rf", "/etc/postgresql-common"])
        except Exception as e:
            pass
        try:
            run_cli(["sudo", "deluser", "postgres"])
        except Exception as e:
            pass
        try:
            run_cli(["sudo", "delgroup", "postgres"])
        except Exception as e:
            pass
    elif os_type == "centos":
        try:
            run_cli(["sudo", "systemctl", "stop", "postgresql*"])
        except Exception as e:
            pass
        try:
            run_cli(["sudo", "yum", "-y", "remove", "postgresql*"])
        except Exception as e:
            pass
        try:
            run_cli(["sudo", "rm", "-rf", "/var/lib/pgsql"])
        except Exception as e:
            pass
        try:
            run_cli(["sudo", "rm", "-rf", "/var/log/pgsql"])
        except Exception as e:
            pass
        try:
            run_cli(["sudo", "rm", "-rf", "/etc/init.d/postgresql*"])
        except Exception as e:
            pass
        try:
            run_cli(["sudo", "userdel", "postgres"])
        except Exception as e:
            pass
        try:
            run_cli(["sudo", "groupdel", "postgres"])
        except Exception as e:
            pass


def main():
    # Check OS system and set values accordingly
    os_type = get_os_info()
    if not os_type:
        print("Only CentOS7 and Ubuntu 20.04 are supported")
        return
    if os_type == "ubuntu":
        postgresql_path = "/etc/postgresql"
    else:
        postgresql_path = "/var/lib/pgsql"

    # Check if postgresql exists and install if needed
    if not is_postgresql_installed():
        try:
            install_postgresql(os_type)
            print("Installation of postgresql is successful!")
            return
        except subprocess.CalledProcessError as e:
            print(f"Installation failed: {e}")
            sys.exit(1)


    if not os.path.exists("/etc/postgresql"):
        remove_postgres(os_type)

    # Ask if user wants to create a backup file
    answer = input("Would you like to add a backup file? Currently there is none listed. (y/n) ").strip().lower()
    # If they want a backup file (new or changed), create file if needed, then create backup and write path to file
    if answer == "y":
        backup_path = input("Path to backup: ")
        create_backup(backup_path, postgresql_path)
        run_cli(["bash", "-c", f"echo {backup_path} | sudo tee /etc/pgsql_check/data.txt"])
        return
    # If backup isn't wanted to change, then user still needs to configure pgsql or if backup exists check hashes
    elif answer == "n":
        if os.path.exists("/etc/pgsql_check/data.txt"):
            with open("/etc/pgsql_check/data.txt", "r") as f:
                backup_path = f.readline().strip()
            check_hashes(backup_path, postgresql_path)
            return
        else:
            print("Finish setting up postgresql config files before making a backup.")
            return


if __name__ == '__main__':
    main()
