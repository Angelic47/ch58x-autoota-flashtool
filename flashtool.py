#!/usr/bin/env python3
"""
flashtool.py - minimal CLI framework for PlatformIO AutoOTA-capable flash devices

Usage:
    flashtool.py <mode> [options]

Modes (choose **exactly one**):
    info     Read the device info **and** OTA info
    devinfo  Read only the device info
    otainfo  Read only the OTA info
    read     Read flash memory
    write    Write flash memory
    erase    Erase flash memory
    verify   Verify flash with SHA-256 output
    reboot   Reboot the device
    commit   Commit the OTA, switch flash bank and reboot the device
    flash    Perform a full OTA operation (info + erase + write + verify + commit)

Common options:
    --address <int>   Start address (hex or decimal). Required by read / write / erase / verify.
    --length  <int>   Data length. Required by read / erase / verify.
    --file    <path>  Path to use as input/output depending on the mode.
    --bank-a  <path>  Path to use as input/output for the OTA bank A for flash operations.
    --bank-b  <path>  Path to use as input/output for the OTA bank B for flash operations.

BLE transport options (choose **one**):
    --name <str>      BLE peripheral advertised name
    --mac  <str>      BLE peripheral MAC address (colon-separated)
    --write-no-rsp    Flag to disable write response for BLE operations (optional, may speed up operations, but may cause issues)

BLE AES-CMAC key (optional, only needed for OTA commands):
    --aes-key <hex>  AES-CMAC key for OTA operations (32 characters hex string)

Example:
    ./flashtool.py info --name "Test Device"
    ./flashtool.py read --address 0x00001000 --length 256 --name "Test Device" --aes-key 0123456789ABCDEFFEDCBA9876543210
    ./flashtool.py write --address 0x00001000 --file firmware.bin --mac AA:BB:CC:DD:EE:FF --aes-key 0123456789ABCDEFFEDCBA9876543210
    ./flashtool.py flash --address 0x00001000 --bank-a bank_a.bin --bank-b bank_b.bin --mac AA:BB:CC:DD:EE:FF --aes-key 0123456789ABCDEFFEDCBA9876543210
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Callable, Dict

from bleak import BleakError
from AutoOTAHelper import AutoOTADevice, AutoOTAController
from AutoOTACommand import AutoOTAReadCommand, AutoOTAProgramCommand, AutoOTAEraseCommand, AutoOTAVerifyCommand, AutoOTARebootCommand, AutoOTAConfirmCommand
from ProgressBarHelper import make_progress_callback, DosSpinner
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(name)s/%(levelname)s]: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("flashtool")

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def print_hex_view(data: bytes) -> None:
    """Print a hex view of the provided byte data."""
    # Print the header
    header = "   " + " ".join(f"{i:02X}" for i in range(16))
    print(header)
    print("-" * len(header))

    # Print the data in rows
    for i in range(0, len(data), 16):
        row_data = data[i:i+16]
        row_str = " ".join(f"{byte:02X}" for byte in row_data)
        print(f"{i:02X}: {row_str}")

# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

global g_device, g_controller  # Global variables to hold device and controller instances
g_device = None
g_controller = None

async def connect_ble(args: argparse.Namespace) -> None:
    """Connect to the BLE device based on provided arguments."""
    global g_device, g_controller
    if g_device is not None and g_controller is not None:
        return g_device, g_controller
    
    write_rsp = None if not args.write_no_rsp else False

    if args.name:
        logger.info(f"Connecting to BLE device with name: {args.name}")
        g_device = AutoOTADevice(name=args.name, write_resp=write_rsp)
    elif args.mac:
        logger.info(f"Connecting to BLE device with MAC: {args.mac}")
        g_device = AutoOTADevice(address=args.mac, write_resp=write_rsp)
    else:
        logger.error("No BLE device name or MAC address provided.")
        logger.error("Use --name or --mac to specify the device.")
        sys.exit(1)

    try:
        await g_device.connect()
        g_controller = AutoOTAController(g_device, aes_key=bytes.fromhex(args.aes_key) if args.aes_key else None)
    except Exception as e:
        logger.error(f"Failed to connect to BLE device: {e}")
        sys.exit(1)
    logger.info(f"Connected to BLE device ({g_device.client.address}) successfully.")
    return g_device, g_controller

async def print_device_info(controller: AutoOTAController) -> dict:
    """Print device information."""
    device_info = None
    try:
        device_info = await controller.read_device_info()
    except Exception as e:
        logger.error(f"Failed to read device information: {e}")
        sys.exit(1)
    logger.info("Device Information:")
    for key, value in device_info["values"].items():
        logger.info(f"    - {device_info["descriptions"][key].name}: {value if value is not None else 'N/A'}")
    return device_info

async def print_ota_info(controller: AutoOTAController) -> dict:
    """Print OTA information."""
    flash_flags = None
    try:
        flash_flags = await controller.read_ota_eeprom_info()
    except Exception as e:
        logger.error(f"Failed to read OTA information: {e}")
        sys.exit(1)
    logger.info("Flash OTA Information:")

    bank = flash_flags["values"]['ota_flash_bank']
    bank = bank if bank is not None else "N/A"
    bank_readable = flash_flags["values"]['ota_flash_bank_readable']
    bank_readable = bank_readable if bank_readable is not None else "N/A"

    flash_mode = flash_flags["values"]['ota_flash_mode']
    flash_mode = flash_mode if flash_mode is not None else "N/A"
    flash_mode_readable = flash_flags["values"]['ota_flash_mode_readable']
    flash_mode_readable = flash_mode_readable if flash_mode_readable is not None else "N/A"

    boot_reason = flash_flags["values"]['ota_boot_reason']
    boot_reason = boot_reason if boot_reason is not None else "N/A"
    boot_reason_readable = flash_flags["values"]['ota_boot_reason_readable']
    boot_reason_readable = boot_reason_readable if boot_reason_readable is not None else "N/A"

    logger.info(f"    - Current Flash Bank: {bank_readable} (0x{bank})")
    logger.info(f"    - Current Status Flags: {flash_mode_readable} (0x{flash_mode})")
    logger.info(f"    - Boot Reason: {boot_reason_readable} (0x{boot_reason})")

    return flash_flags


async def do_cmd_info(args: argparse.Namespace, disconnect: bool = True) -> None:
    """Perform **info** (device + OTA info read)."""
    """Perform **info** (device + OTA info read)."""
    device, controller = await connect_ble(args)
    await print_device_info(controller)
    await print_ota_info(controller)
    if disconnect:
        await device.disconnect()


async def do_cmd_devinfo(args: argparse.Namespace, disconnect: bool = True) -> None:
    """Perform **devinfo** (device-only info read)."""
    device, controller = await connect_ble(args)
    logger.info("Reading device information...")
    await print_device_info(controller)
    if disconnect:
        await device.disconnect()


async def do_cmd_otainfo(args: argparse.Namespace, disconnect: bool = True) -> None:
    """Perform **otainfo** (OTA-only info read)."""
    device, controller = await connect_ble(args)
    logger.info("Reading OTA Information...")
    await print_ota_info(controller)
    if disconnect:
        await device.disconnect()


async def do_cmd_read(args: argparse.Namespace, disconnect: bool = True) -> None:
    """Perform **read** operation (dump flash to file)."""
    device, controller = await connect_ble(args)
    logger.info(f"Reading flash memory from address 0x{args.address:X} with length {args.length} bytes...")
    flash_dump_file = None
    flash_dump = None
    if args.filepath is not None:
        if args.filepath.is_file():
            logger.error(f"File {args.filepath} already exists. Please choose a different file name.")
            sys.exit(1)
        else:
            logger.info(f"Creating file {args.filepath} for flash dump.")
            try:
                flash_dump_file = open(args.filepath, "wb")
            except Exception as e:
                logger.error(f"Failed to create file {args.filepath}: {e}")
                sys.exit(1)
    else:
        logger.info("No output file specified, will print flash dump to console.")
        flash_dump = bytearray()
    
    # Create read command (512 bytes is the default chunk size)
    process_length = 0
    remain_length = args.length
    address = args.address
    progress_callback = make_progress_callback(size_total=args.length, desc="Flash Read")
    progress_callback(process_length, args.length)  # Initialize progress bar

    while True:
        chunk_length = min(remain_length, 512)
        read_cmd = AutoOTAReadCommand(address=address, length=chunk_length)
        try:
            await controller.send_command(read_cmd)
        except Exception as e:
            logger.error(f"Failed to read flash memory: {e}")
            if flash_dump_file:
                flash_dump_file.close()
            sys.exit(1)

        read_chunk = read_cmd.read_result

        # Write to file or buffer
        if flash_dump_file:
            flash_dump_file.write(read_chunk)
        else:
            flash_dump.extend(read_chunk)

        # Update address and remaining length
        address += chunk_length
        remain_length -= chunk_length
        process_length += chunk_length

        # Update progress bar
        progress_callback(process_length, args.length)

        if remain_length <= 0:
            break
    if flash_dump_file:
        flash_dump_file.close()
        logger.info(f"Flash memory read complete. Data saved to {args.filepath}.")
    else:
        print_hex_view(flash_dump)
    del progress_callback  # Clean up progress callback to save memory
    if disconnect:
        await device.disconnect()

async def do_cmd_write(args: argparse.Namespace, disconnect: bool = True) -> None:
    """Perform **write** operation (flash data from file)."""
    device, controller = await connect_ble(args)
    if args.length:
        logger.info(f"Writing flash memory to address 0x{args.address:X} with length {args.length} bytes from file {args.filepath}...")
    else:
        logger.info(f"Writing flash memory to address 0x{args.address:X} from file {args.filepath}...")
    if not args.filepath.is_file():
        logger.error(f"File {args.filepath} does not exist. Please provide a valid file.")
        sys.exit(1)
    flash_data = None
    try:
        with open(args.filepath, "rb") as f:
            flash_data = f.read()
    except Exception as e:
        logger.error(f"Failed to read file {args.filepath}: {e}")
        sys.exit(1)
    
    # Create write command (512 bytes is the default chunk size)
    process_length = 0
    remain_length = min(len(flash_data), args.length) if args.length else len(flash_data)
    address = args.address
    progress_callback = make_progress_callback(size_total=remain_length, desc="Flash Write")
    progress_callback(process_length, remain_length)  # Initialize progress bar
    while True:
        chunk_length = min(remain_length, 512)
        write_cmd = AutoOTAProgramCommand(address=address, data=flash_data[process_length:process_length + chunk_length])
        try:
            await controller.send_command(write_cmd)
        except Exception as e:
            logger.error(f"Failed to write flash memory: {e}")
            sys.exit(1)

        # Update address and remaining length
        address += chunk_length
        remain_length -= chunk_length
        process_length += chunk_length

        # Update progress bar
        progress_callback(process_length, len(flash_data))

        if remain_length <= 0:
            break
    if disconnect:
        await device.disconnect()
    logger.info(f"Flash memory write complete.")
    logger.info(f"Data written to address 0x{args.address:X} with length {process_length} bytes.")

async def do_cmd_erase(args: argparse.Namespace, disconnect: bool = True) -> None:
    """Perform **erase** operation (erase flash region)."""
    device, controller = await connect_ble(args)
    logger.info(f"Erasing flash memory from address 0x{args.address:X} with length {args.length} bytes...")
    erase_cmd = AutoOTAEraseCommand(address=args.address, length=args.length)
    try:
        await controller.send_command(erase_cmd)
    except Exception as e:
        logger.error(f"Failed to perform erase operation: {e}")
        sys.exit(1)
    logger.info("Erase command sent successfully, waiting for completion...")
    # Wait for the erase operation to complete
    spinner = DosSpinner()
    while True:
        check = await controller.read_ota_status()
        if check["success"]:
            break
        elif check["busy"]:
            spinner.spin()
        else:
            logger.error(f"Erase operation failed with status code: {check['code']}")
            sys.exit(1)
    if disconnect:
        await device.disconnect()
    logger.info("Erase operation completed successfully.")


async def do_cmd_verify(args: argparse.Namespace, disconnect: bool = True) -> None:
    """Perform **verify** operation (SHA-256 over flash vs. file)."""
    device, controller = await connect_ble(args)
    if not args.filepath.is_file():
        logger.error(f"File {args.filepath} does not exist. Please provide a valid file.")
        sys.exit(1)
    
    logger.info(f"Verifying flash memory from address 0x{args.address:X} with length {args.length} bytes against file {args.filepath}...")
    try:
        with open(args.filepath, "rb") as f:
            flash_data = f.read()
    except Exception as e:
        logger.error(f"Failed to read file {args.filepath}: {e}")
        sys.exit(1)
    
    length = min(len(flash_data), args.length) if args.length else len(flash_data)
    if length <= 0:
        logger.error("Length must be greater than 0 for verification.")
        sys.exit(1)

    verify_cmd = AutoOTAVerifyCommand(address=args.address, length=args.length)
    try:
        await controller.send_command(verify_cmd)
    except Exception as e:
        logger.error(f"Failed to perform verify operation: {e}")
        sys.exit(1)

    logger.info("Verify command sent successfully, waiting for completion...")
    # Wait for the verify operation to complete
    spinner = DosSpinner()
    while True:
        check = await controller.read_ota_status()
        if check["success"]:
            break
        elif check["busy"]:
            spinner.spin()
        else:
            logger.error(f"Verify operation failed with status code: {check['code']}")
            sys.exit(1)
    logger.info("Verify operation completed successfully.")

    sha256_result = await controller.read_io_buffer()
    logger.info(f"Response  SHA256: {sha256_result.hex()}")
    if disconnect:
        await device.disconnect()

    flash_data = flash_data[:length]  # Ensure we only hash the relevant part
    # Calculate SHA-256 of the flash_data
    digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
    digest.update(flash_data)
    calculated_sha256 = digest.finalize()
    logger.info(f"Localfile SHA256: {calculated_sha256.hex()}")

    #Compare the calculated SHA-256 with the result from the device
    if calculated_sha256 == sha256_result:
        logger.info("SHA-256 verification successful.")
    else:
        logger.error("SHA-256 verification failed!")
        sys.exit(1)

async def do_cmd_reboot(args: argparse.Namespace) -> None:
    """Perform **reboot** operation (simple MCU reboot)."""
    device, controller = await connect_ble(args)
    logger.info("Rebooting the device...")
    reboot_cmd = AutoOTARebootCommand()
    try:
        await controller.send_command(reboot_cmd)
    except BleakError as e:
        logger.error(f"Failed to send reboot command: {e}")
        sys.exit(1)
    except Exception as e:
        logger.info("Seems like the device rebooted successfully (Connection lost).")
    await device.disconnect()
    logger.info("Reboot command requested successfully.")


async def do_cmd_commit(args: argparse.Namespace) -> None:
    """Perform **commit** operation (finalise OTA + reboot)."""
    device, controller = await connect_ble(args)
    logger.info("Committing OTA operation and rebooting the device...")
    commit_cmd = AutoOTAConfirmCommand()
    try:
        await controller.send_command(commit_cmd)
    except BleakError as e:
        logger.error(f"Failed to send commit command: {e}")
        sys.exit(1)
    except Exception as e:
        logger.info("Seems like the device rebooted successfully (Connection lost).")
    await device.disconnect()
    logger.info("Commit command requested successfully. Device should reboot and switch to the new firmware.")

async def do_cmd_flash(args: argparse.Namespace) -> None:
    """This is a convenience command that combines several operations."""
    """Perform **flash** operation (info + erase + write + verify + commit)."""
    device, controller = await connect_ble(args)
    logger.info("Performing flash operation (info + erase + write + verify + commit)...")

    if not args.bank_a.is_file() or not args.bank_b.is_file():
        logger.error("Both --bank-a and --bank-b must be specified and must be valid files.")
        sys.exit(1)
    
    # Step 1: Read device and OTA info
    try:
        await print_device_info(controller)
    except:
        logger.warning("Failed to read all device information (may not implemented by the device).")
        logger.warning("Continuing with the flash operation anyway.")
    
    flash_flags = await print_ota_info(controller)

    if flash_flags["values"]['ota_flash_bank'] == "a5a5a5a5":
        # Device is bank A, we need to write to bank B
        args.address = 0x00037000
        args.length = 0x00036000
        args.filepath = args.bank_b
    elif flash_flags["values"]['ota_flash_bank'] == "5a5a5a5a":
        # Device is bank B, we need to write to bank A
        args.address = 0x00001000
        args.length = 0x00036000
        args.filepath = args.bank_a
    else:
        logger.error("Unknown OTA flash bank state. Cannot determine which bank to write to.")
        sys.exit(1)

    # Step 2: Erase flash memory
    await do_cmd_erase(args, disconnect=False)

    # Step 3: Write flash memory from file
    await do_cmd_write(args, disconnect=False)

    # Step 4: Verify flash memory
    args.length = Path(args.filepath).stat().st_size
    await do_cmd_verify(args, disconnect=False)

    # Step 5: Commit OTA operation
    await do_cmd_commit(args)

    logger.info("Flash operation completed successfully.")

# ---------------------------------------------------------------------------
# Command routing helper
# ---------------------------------------------------------------------------

COMMAND_TABLE: Dict[str, Callable[[argparse.Namespace], asyncio.Future]] = {
    "info": do_cmd_info,
    "devinfo": do_cmd_devinfo,
    "otainfo": do_cmd_otainfo,
    "read": do_cmd_read,
    "write": do_cmd_write,
    "erase": do_cmd_erase,
    "verify": do_cmd_verify,
    "reboot": do_cmd_reboot,
    "commit": do_cmd_commit,
    "flash": do_cmd_flash,
}


# ---------------------------------------------------------------------------
# Argument parsing utilities
# ---------------------------------------------------------------------------

def _int_auto(value: str) -> int:
    """Accept 0xNN (hex) or decimal ints from CLI."""
    return int(value, 0)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="CLI utility for flashing and maintaining PlatformIO AutoOTA-capable devices.",
        epilog="See the README for protocol details.",
    )

    # BLE transport selection - mutually exclusive, at least one required
    ble_group = p.add_mutually_exclusive_group(required=True)
    ble_group.add_argument("--name", help="BLE peripheral advertised name")
    ble_group.add_argument("--mac", help="BLE peripheral MAC address (AA:BB:CC:DD:EE:FF)")

    # Flags for BLE operations
    p.add_argument("--write-no-rsp", action="store_true", help="Disable write response for BLE operations (optional, may speed up operations, but may cause issues)")
    
    # AES-CMAC key for OTA operations (optional, only needed for OTA commands, defaults to None)
    p.add_argument("--aes-key", type=str, help="AES-CMAC key for OTA operations (hex string, 32 characters). Optional, defaults to None.")

    # Mode - first positional arg, restricted to the literal keys in COMMAND_TABLE
    p.add_argument(
        "mode",
        choices=list(COMMAND_TABLE.keys()),
        help="Flash utility mode. Use --help for details.",
    )

    # Optional / conditional arguments
    p.add_argument("--address", type=_int_auto, help="Start address for flash.")
    p.add_argument("--length", type=_int_auto, help="Length in bytes. Required by read/erase/verify, optional for write (limits write size).")
    p.add_argument("--file", dest="filepath", type=Path, help="Path to input/output file.")
    p.add_argument("--bank-a", type=Path, help="Path to OTA bank A file (for flash operations).")
    p.add_argument("--bank-b", type=Path, help="Path to OTA bank B file (for flash operations).")

    return p


def _validate_args(args: argparse.Namespace) -> None:
    """Ensure address/length/file are supplied when required by *mode*."""

    def need(name: str, desc: str = None, cmdarg: str = None) -> None:  # tiny helper
        if getattr(args, name) is None:
            if cmdarg is not None:
                name = cmdarg
            if desc is None:
                sys.exit(f"error: {name} is required for {args.mode} mode")
            else:
                sys.exit(f"error: {desc} (--{name}) is required for {args.mode} mode")
    def check_aes_key() -> None:
        if len(args.aes_key) != 32 or not all(c in "0123456789abcdefABCDEF" for c in args.aes_key):
            sys.exit("error: --aes-key must be a 32-character hex string (16 bytes)")

    if args.mode in {"read", "write", "erase", "verify", "commit", "reboot", "commit", "flash"}:
        need("aes_key", "AES-CMAC key for OTA operations")
        check_aes_key()
    if args.mode in {"read", "write", "erase", "verify"}:
        need("address", "Start address for flash")
    if args.mode in {"read", "erase", "verify"}:
        need("length", "Length in bytes")
    if args.mode in {"write", "verify"}:
        need("filepath", "Path to firmware file", "file")
    if args.mode in {"flash"}:
        need("bank_a", "Path to OTA bank A file", "bank-a")
        need("bank_b", "Path to OTA bank B file", "bank-b")


# ---------------------------------------------------------------------------
# Main entry-point
# ---------------------------------------------------------------------------

async def _async_main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    _validate_args(args)

    # Dispatch to the selected command coroutine
    cmd = COMMAND_TABLE[args.mode]
    await cmd(args)


def main() -> None:  # noqa: D401
    """Synchronously bridge into the asyncio realm."""
    try:
        asyncio.run(_async_main())
    except KeyboardInterrupt:
        logger.warning("Interrupted by user - exiting…")


if __name__ == "__main__":
    main()
