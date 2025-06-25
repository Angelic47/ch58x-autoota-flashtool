# AutoOTA Flash Tool Utility

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.7%2B-blue.svg)](https://www.python.org/downloads/)
[![PlatformIO Compatible](https://img.shields.io/badge/PlatformIO-Compatible-blue.svg)](https://platformio.org/)

[中文版本请点击这里](README-zh.md)

## ✨ Overview

This is a lightweight command-line tool designed for devices that support the `PlatformIO AutoOTA` protocol (e.g., [ch58x-ota-example](https://github.com/Angelic47/ch58x-ota-example)).  
It supports a variety of Flash operations including reading, writing, erasing, verifying, OTA committing, and rebooting --  
offering a **simple, reliable, and modern** OTA firmware upgrade experience.  

---

## 🧩 Project Background

WCH’s CH58x series is a high-performance, low-power RISC-V MCU widely used in IoT, smart home, and embedded BLE applications.  

While the chip itself is quite capable, the official OTA tools provided by WCH suffer from several limitations:  

* Complicated procedures, limited features, and lack of integrity checks
* BootROM tools require manual button interaction, making automation impossible
* B partition in A/B structure cannot boot; upgrade performance is poor
* Most importantly: **the official tools and Flash operation flows are closed-source**, restricting freedom and extendability

All of the above make OTA updates on CH58x-based devices unnecessarily painful -- especially for battery-powered or physically inaccessible devices.  
And so, this project was born.  

It is **fully open-source**, designed to provide a **secure, streamlined, and developer-friendly** alternative to WCH’s official toolchain.  
Built on top of Bleak (Python BLE stack), the device firmware uses PlatformIO with a complete bootloader, A/B switch logic, and AES-CMAC authentication.  
You can perform OTA directly using your computer’s built-in Bluetooth -- no external programmers required.  

Later, I realized this protocol is highly portable. It can be reused across many other BLE-capable devices as a standalone OTA library.  
To support such generalization, this tool abstracts the OTA Flash logic into a command-line utility -- ideal for debugging and batch deployments.  

> 📁 Device-side implementation is available in [libota](https://github.com/Angelic47/ch58x-ota-example/tree/main/lib/libota)  

---

## 🚀 Features

* 🔄 **Remote OTA**: Upgrade firmware over BLE -- no physical access required
* 🧰 **Multi-function Flash Utility**: Read/write/erase/verify/reboot capabilities
* 🧬 **A/B Partition Boot Logic**: Robust bootloader fallback; avoids bricking after bad updates
* 💤 **Online Programming**: OTA runs in background -- device continues to function normally
* 🔐 **Secure Authentication**: Uses AES-CMAC challenge-response to prevent MITM and replay attacks
* 🛡️ **Memory Safety by Design**: Readable, auditable, and robust codebase
* 📦 **Native PlatformIO Compatibility**: Easily integrates with embedded development pipelines
* 🌈 **Fully Open Source**: Licensed under MIT -- transparent, free, and developer-first

---

## 📦 Installation

To use this tool, make sure your computer supports Bluetooth Low Energy (BLE):  
This can be either **built-in or external** Bluetooth hardware.  

On **Windows**, your system must be **Windows 10 version 1803 or newer**.  
On **Linux**, install the `bluez` stack and ensure your user has permission to access BLE interfaces.  

The tool depends on the following Python libraries: `bleak`, `cryptography`, and `tqdm`.  
It is strongly recommended to use `venv` or `virtualenv` to manage your Python environment.  

```bash
# Clone the project
git clone https://github.com/Angelic47/ch58x-autoota-flashtool.git
cd ch58x-autoota-flashtool

# Create a virtual environment
python -m venv flashtool

# Activate the environment

## Windows (cmd)
flashtool\Scripts\activate.bat

## PowerShell
flashtool\Scripts\Activate.ps1

## Linux / macOS
source flashtool/bin/activate

# Install dependencies
pip install bleak cryptography tqdm

# All set!
python flashtool.py --help
```

---

## 💡 Quick Usage Examples

```bash
# Read device + OTA info
./flashtool.py info --name "Test Device"

# Read 256 bytes from address 0x1000
./flashtool.py read --address 0x00001000 --length 256 --name "Test Device" --aes-key 0123456789ABCDEFFEDCBA9876543210

# Write firmware to address 0x1000
./flashtool.py write --address 0x00001000 --file firmware.bin --mac AA:BB:CC:DD:EE:FF --aes-key 0123456789ABCDEFFEDCBA9876543210

# Perform full OTA process
./flashtool.py flash --address 0x00001000 --bank-a bank_a.bin --bank-b bank_b.bin --mac AA:BB:CC:DD:EE:FF --aes-key 0123456789ABCDEFFEDCBA9876543210
```

---

## 📡 BLE Connection Options (Choose One)

The tool connects to devices over BLE. You may specify either:  

* `--name <str>`: BLE peripheral advertised name
* `--mac <str>`: BLE MAC address (recommended; e.g., `AA:BB:CC:DD:EE:FF`)

Optional:

* `--write-no-rsp`: Disable write-response to potentially improve performance (may cause instability)

---

## 🔐 AES-CMAC Authentication Key

All commands **except** `info`, `devinfo`, and `otainfo` require authentication.  

* `--aes-key <hex>`: 32-character hex string used as AES-CMAC key

This key is defined at build-time inside your firmware's `platformio.ini`.  
By default, the key is: `0123456789ABCDEFFEDCBA9876543210`  

> ⚠️ **It is highly recommended to replace the default key in production**  
> This prevents unauthorized access and improves security.  

---

## 🛠️ Supported Commands

| Command   | Description                                               |
| --------- | --------------------------------------------------------- |
| `info`    | Reads both device info and OTA state                      |
| `devinfo` | Reads only device info                                    |
| `otainfo` | Reads only OTA state                                      |
| `read`    | Reads data from Flash                                     |
| `write`   | Writes data to Flash                                      |
| `erase`   | Erases Flash memory regions                               |
| `verify`  | Verifies Flash content by computing SHA-256 hash          |
| `reboot`  | Reboots the device                                        |
| `commit`  | Commits OTA changes, switches partition, and reboots      |
| `flash`   | Full OTA sequence: info → erase → write → verify → commit |

---

## ⚙️ Common Parameters

| Parameter         | Description                                                                        |
| ----------------- | ---------------------------------------------------------------------------------- |
| `--address <int>` | Start address (decimal or hex), required for `read` / `write` / `erase` / `verify` |
| `--length <int>`  | Data length, required for `read` / `erase` / `verify`                              |
| `--file <path>`   | File path used for reading, writing, or verification                               |

### 🔧 OTA-Specific Parameters

| Parameter         | Description                                        |
| ----------------- | -------------------------------------------------- |
| `--bank-a <path>` | Bank A firmware image path (used in full OTA mode) |
| `--bank-b <path>` | Bank B firmware image path (used in full OTA mode) |

---

## 📜 License

This project is released under the [MIT License](LICENSE).  
You are free to use, modify, and distribute this tool --  
and warmly welcomed to adapt it for broader BLE OTA development scenarios.  
