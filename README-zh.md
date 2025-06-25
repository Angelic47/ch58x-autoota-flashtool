# AutoOTA Flash Tool Utility

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.7%2B-yellow.svg?style=for-the-badge)](https://www.python.org/downloads/)
[![PlatformIO Compatible](https://img.shields.io/badge/PlatformIO-Compatible-blue.svg?style=for-the-badge)](https://platformio.org/)

(English version available in [README.md](README.md))

## ✨ 简介
这是一个轻量级的命令行工具,  专为支持 `PlatformIO AutoOTA` 协议的设备（例如 [ch58x-ota-example](https://github.com/Angelic47/ch58x-ota-example)）设计,  
它支持多种 Flash 操作, 包括读取、写入、擦除、校验、OTA 提交与重启, 致力于提供一种 **简洁、可靠、现代化** 的设备 OTA 升级方式.  

## 🧩 项目背景
WCH 的 CH58x 系列是一款高性能、低功耗的 RISC-V 单片机, 被广泛应用于物联网、智能家居与低功耗嵌入式设备中.  

这款芯片本身性能优越, 但遗憾的是, WCH 官方提供的 OTA 例程存在不少问题:  

* 操作流程繁琐, 功能单一, 缺乏安全校验机制;
* 官方 BootROM 工具需要手动按键进入模式, 无法实现自动升级;
* A/B 分区中的 B 分区无法引导启动, 且整体性能较差;
* 最关键的是: 官方工具及 Flash 操作流程 **并不开源**, 严重限制了自由扩展与二次开发.

以上种种问题让基于 CH58x 的设备 OTA 升级变得异常麻烦, 尤其对于电池供电、无法断电的设备更是难以接受.  
于是 —— 这个项目诞生了.  

本项目完全开源, 旨在提供一个**安全、简洁、可靠且现代化**的 OTA 升级解决方案, 为你解决一切 WCH 官方工具的“难用”之苦.  
它基于 Bleak 构建, 设备端使用了 PlatformIO 构建环境, 具备完整的 Bootloader、A/B 分区切换机制, 并通过 AES-CMAC 保证通信安全,  
你可以直接使用电脑的蓝牙接口进行 OTA, 无需外接硬件或工具链.  

后来, 我也发现这套协议的通用性非常强, 不仅适用于 CH58x, 也可以作为一个独立的 OTA Library 移植到其他任意 BLE 嵌入式设备中.  
为了支持通用开发, 我将 Flash 操作流程封装成一个独立的命令行工具, 方便地用于调试和批量部署.  

> 📁 设备端代码可在 [libota](https://github.com/Angelic47/ch58x-ota-example/tree/main/lib/libota) 中查看与移植. 

---

## 🚀 特性
* **🔄 远程 OTA**: 直接通过 BLE 实现空中固件升级, 无需物理接触
* **🧰 多功能集成**: 支持读写、擦除、校验、重启等通用 flash 操作
* **🧬 A/B 分区机制**: 具备 Bootloader 回退保护, 升级失败可回退, 最大限度杜绝“一键变砖”
* **💤 后台编程支持**: OTA 在设备运行中完成，不中断主要功能
* **🔐 安全机制**: 支持基于 AES-CMAC 的挑战-响应认证机制, 防止中间人和重放攻击
* **🛡️ 可靠的内存安全设计**: 结构清晰，逻辑可审查, 逻辑经过严谨的内存安全性审查
* **📦 PlatformIO 原生兼容**: 方便快速集成与移植, 与现代化嵌入式开发环境无缝衔接
* **🌈 完全开源**: 使用 MIT 协议, 真正开放自由

---

## 📦 安装
您需要一台支持 BLE 的电脑,  
请先确认您的电脑拥有蓝牙能力（**内建或外接蓝牙模块**）, 且**支持 BLE 协议**.  

`Windows` 平台需要系统版本在 `Windows 10 1803` 以上, `Linux` 平台需要安装 `bluez` 等相关系统依赖.  
*该项目默认您的设备具备上述条件, 环境准备不再赘述.*  

使用该项目需要安装`bleak`, `cryptography` 和 `tqdm` 这三个 Python 库,  
建议您使用 `virtualenv` 或 `venv` 来创建一个独立的 Python 环境, 然后在该环境中安装所需的依赖库.  

```bash
# 克隆项目代码
git clone https://github.com/Angelic47/ch58x-autoota-flashtool.git
cd ch58x-autoota-flashtool

# 创建名为 flashtool 的虚拟环境
python -m venv flashtool

# 激活虚拟环境

## Windows
## .\flashtool\Scripts\activate.bat
## 或者使用PowerShell
## .\flashtool\Scripts\Activate.ps1

## Linux / macOS
source flashtool/bin/activate

# 安装所需依赖
pip install bleak cryptography tqdm

# 大功告成
python flashtool.py --help
```

---

## 💡 快速使用示例

```bash
# 读取设备和 OTA 信息
./flashtool.py info --name "Test Device"

# 从地址 0x1000 读取 256 字节
./flashtool.py read --address 0x00001000 --length 256 --name "Test Device" --aes-key 0123456789ABCDEFFEDCBA9876543210

# 向指定地址写入固件
./flashtool.py write --address 0x00001000 --file firmware.bin --mac AA:BB:CC:DD:EE:FF --aes-key 0123456789ABCDEFFEDCBA9876543210

# 执行完整 OTA 流程
./flashtool.py flash --address 0x00001000 --bank-a bank_a.bin --bank-b bank_b.bin --mac AA:BB:CC:DD:EE:FF --aes-key 0123456789ABCDEFFEDCBA9876543210
```

---

## 详细使用说明

以下是该工具的详细使用说明, 包括所有可用命令和参数. 

### 📡 BLE 连接方式（**二选一**）

本工具通过 BLE 与设备建立连接, 您可以选择以下两种方式之一: 

* `--name <str>`: BLE 广播名称
* `--mac <str>`: BLE MAC 地址（推荐, 格式如 `AA:BB:CC:DD:EE:FF`）

可选参数: 

* `--write-no-rsp`: 禁用写响应（可能提升性能, 但存在已知稳定性问题）

---

### 🔐 AES-CMAC 密钥

除 `info` / `devinfo` / `otainfo` 外的所有操作，均需提供 AES-CMAC 密钥进行认证.  
您需要提供 AES-CMAC 密钥进行认证, 否则将无法进行 OTA 操作.

* `--aes-key <hex>`: 32 字符十六进制字符串, 作为 AES-CMAC 密钥, 用于 OTA 操作的认证, 否则将无法进行 OTA 操作.

AES-CMAC 密钥是一个 32 字符的 Hex 字符串, 位于设备端固件编译时的 `platformio.ini` 文件中被定义.  
默认情况下, 该密钥是 `0123456789ABCDEFFEDCBA9876543210`.  

> ⚠️ **强烈建议您在实际部署时替换默认密钥**  
> 防止未经授权的设备操作, 以避免安全风险.    

---

### 🛠️ 完整功能一览

| 功能         | 描述                                                   | 
| ------------- | ---------------------------------------------------- |
| `info`        | 同时读取设备信息和 OTA 信息                                     |
| `devinfo`     | 仅读取设备信息                                              |
| `otainfo`     | 仅读取 OTA 信息                                           |
| `read`        | 从 flash 中读取数据                                        |
| `write`       | 将数据写入 flash                                          |
| `erase`       | 擦除 flash 区域                                          |
| `verify`      | 校验 flash 内容的 SHA-256                                 |
| `reboot`      | 重启设备                                                 |
| `commit`      | 提交 OTA、更换分区并重启                                 |
| `flash`       | 完整 OTA 操作（包含 info + erase + write + verify + commit） |

---

### ⚙️ 通用参数


| 参数                | 描述                                                       |
| ----------------- | -------------------------------------------------------- |
| `--address <int>` | Flash 起始地址（支持十进制或十六进制）, 适用于 `read` / `write` / `erase` / `verify` |
| `--length <int>`  | 操作的数据长度, 适用于 `read` / `erase` / `verify`                  |
| `--file <path>`   | 读/写/校验操作的文件路径                                   |

### 🔧 OTA 相关参数

| 参数                | 描述                                                    |
| ----------------- | -------------------------------------------------------- |
| `--bank-a <path>` | 完整 OTA 操作中 要刷写的 Bank A 文件路径                   |
| `--bank-b <path>` | 完整 OTA 操作中 要刷写的 Bank B 文件路径                   |

## 📜 许可证

本项目采用 [MIT License](LICENSE) 开源发布 .  
你可以自由使用、修改、发布本工具，亦欢迎你将它拓展到更多 BLE OTA 场景中.  
