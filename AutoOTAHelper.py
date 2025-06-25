#coding: utf-8

import logging
import asyncio
from bleak import BleakClient, BleakScanner, BleakGATTServiceCollection, BleakGATTCharacteristic
from bleak.backends.service import BleakGATTService

from cryptography.hazmat.primitives.cmac import CMAC
from cryptography.hazmat.primitives.ciphers import algorithms
from cryptography.hazmat.backends import default_backend

from AutoOTACommand import AutoOTABaseCommand

class AutoOTADevice():
    def __init__(self, address: str = None, name: str = None, timeout: float = 20.0, write_resp: bool = None) -> None:
        if not address and not name:
            raise ValueError("Either 'address' or 'name' must be provided")
        self.address = address
        self.name = name
        self.client = None
        self.connected = False
        self.timeout = timeout
        self.device_services = None
        self.write_resp_flag = write_resp
        self.logger = logging.getLogger(__name__)
    
    def _ensure_connected(self) -> None:
        if not self.connected or self.client is None:
            raise RuntimeError("Device is not connected")
    
    async def __aenter__(self) -> "AutoOTADevice":
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        tb,
    ) -> bool | None:
        await self.disconnect()
        # Propagate original exception (if any)
        return False
    
    def __repr__(self) -> str:
        state = "connected" if self.connected else "disconnected"
        return f"<AutoOTADevice {self.address} ({state})>"
    
    def __del__(self) -> None:
        if self.client and self.connected:
            try:
                asyncio.run(self.disconnect())
            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")
        self.client = None
        self.connected = False
    
    async def connect(self) -> BleakClient:
        if self.name and not self.address:
            device = None
            self.logger.debug(f"Searching for device by name: {self.name}")
            device = await BleakScanner.find_device_by_name(self.name)
            if not device:
                self.logger.error(f"Device with name '{self.name}' not found")
                raise ValueError(f"Device with name '{self.name}' not found")
            self.logger.debug(f"Connecting to device with name: {self.name}")
            try:
                self.client = BleakClient(device, timeout=self.timeout)
                await self.client.connect()
            except Exception as e:
                self.logger.error(f"Failed to connect to device: {e}")
                raise
            self.logger.debug(f"Connected to device with name: {self.name}, address: {self.client.address}")
            self.connected = True
            return self.client
        elif self.address:
            self.logger.debug(f"Connecting to device with address: {self.address}")
            try:
                self.client = BleakClient(self.address, timeout=self.timeout)
                await self.client.connect()
            except Exception as e:
                self.logger.error(f"Failed to connect to device: {e}")
                raise
            self.logger.debug(f"Connected to device with address: {self.address}")
            self.connected = True
            return self.client

        raise ValueError("Either 'address' or 'name' must be provided")
    
    async def get_services(self) -> BleakGATTServiceCollection:
        self._ensure_connected()
        if not self.device_services:
            try:
                self.device_services = self.client.services
            except Exception as e:
                self.logger.error(f"Failed to get services: {e}")
                raise
        return self.device_services
    
    async def get_services_by_uuid(self, service_uuid: str) -> BleakGATTService:
        self._ensure_connected()
        if not self.device_services:
            await self.get_services()
        
        for service in self.device_services:
            if service.uuid == service_uuid:
                return service
        
        self.logger.error(f"Service with UUID {service_uuid} not found")
        raise ValueError(f"Service with UUID {service_uuid} not found")
    
    async def get_characteristics_with_service(self, service_uuid: str) -> list[BleakGATTCharacteristic]:
        self._ensure_connected()
        service = await self.get_services_by_uuid(service_uuid)
        return service.characteristics
    
    async def get_characteristic_with_service(self, service_uuid: str, 
                                               characteristic_uuid: str) -> BleakGATTCharacteristic:
        self._ensure_connected()
        service = await self.get_services_by_uuid(service_uuid)
        for characteristic in service.characteristics:
            if characteristic.uuid == characteristic_uuid:
                return characteristic
        self.logger.error(f"Characteristic with UUID {characteristic_uuid} not found in service {service_uuid}")
        raise ValueError(f"Characteristic with UUID {characteristic_uuid} not found in service {service_uuid}")

    async def read_characteristic(self, characteristic: BleakGATTCharacteristic) -> bytes:
        self._ensure_connected()
        try:
            return await self.client.read_gatt_char(characteristic)
        except Exception as e:
            self.logger.error(f"Failed to read characteristic {characteristic}: {e}")
            raise
    
    async def write_characteristic(self, characteristic: BleakGATTCharacteristic, data: bytes, write_resp: bool = None) -> None:
        self._ensure_connected()
        try:
            await self.client.write_gatt_char(characteristic, data, response=write_resp)
        except Exception as e:
            self.logger.error(f"Failed to write to characteristic {characteristic}: {e}")
            raise

    async def disconnect(self):
        if self.client:
            await self.client.disconnect()
            self.connected = False

class AutoOTACharacteristicDescription():
    def __init__(self, name: str, uuid: str, is_human_readable: bool = False) -> None:
        self.name = name
        self.uuid = uuid
        self.is_human_readable = is_human_readable
    
    def __repr__(self) -> str:
        return f"<AutoOTACharacteristicDescription name={self.name}, uuid={self.uuid}, is_human_readable={self.is_human_readable}>"

class AutoOTAController():
    _UUID_SERVICE_DEVICE_INFO = '0000180a-0000-1000-8000-00805f9b34fb'
    _UUID_SERVICE_OTA = '0000fff0-0000-1000-8000-00805f9b34fb'

    CHARACTERISTIC_DESCRIPTIONS_DEV_INFO = {
        "system_id": AutoOTACharacteristicDescription("System ID", "00002a23-0000-1000-8000-00805f9b34fb", False),
        "model_number": AutoOTACharacteristicDescription("Model Number", "00002a24-0000-1000-8000-00805f9b34fb", True),
        "serial_number": AutoOTACharacteristicDescription("Serial Number", "00002a25-0000-1000-8000-00805f9b34fb", True),
        "firmware_revision": AutoOTACharacteristicDescription("Firmware Revision", "00002a26-0000-1000-8000-00805f9b34fb", True),
        "hardware_revision": AutoOTACharacteristicDescription("Hardware Revision", "00002a27-0000-1000-8000-00805f9b34fb", True),
        "software_revision": AutoOTACharacteristicDescription("Software Revision", "00002a28-0000-1000-8000-00805f9b34fb", True),
        "manufacturer_name": AutoOTACharacteristicDescription("Manufacturer Name", "00002a29-0000-1000-8000-00805f9b34fb", True),
    }

    CHARACTERISTIC_DESCRIPTIONS_OTA = {
        "ota_main": AutoOTACharacteristicDescription("Main Command & Status Readback", "0000ffe1-0000-1000-8000-00805f9b34fb", False),
        "ota_buffer": AutoOTACharacteristicDescription("Data IO Buffer", "0000ffe2-0000-1000-8000-00805f9b34fb", False),
        "ota_challenge": AutoOTACharacteristicDescription("Authentication Challenge", "0000ffe3-0000-1000-8000-00805f9b34fb", False),
        "ota_token": AutoOTACharacteristicDescription("Authentication Token", "0000ffe4-0000-1000-8000-00805f9b34fb", False),
        "ota_flash_bank": AutoOTACharacteristicDescription("Current Flash Bank", "0000ffe5-0000-1000-8000-00805f9b34fb", False),
        "ota_flash_bank_readable": AutoOTACharacteristicDescription("Current Flash Bank (Human Readable)", "0000ffe6-0000-1000-8000-00805f9b34fb", True),
        "ota_flash_mode": AutoOTACharacteristicDescription("Current Flash Mode", "0000ffe7-0000-1000-8000-00805f9b34fb", False),
        "ota_flash_mode_readable": AutoOTACharacteristicDescription("Current Flash Mode (Human Readable)", "0000ffe8-0000-1000-8000-00805f9b34fb", True),
        "ota_boot_reason": AutoOTACharacteristicDescription("Boot Reason", "0000ffe9-0000-1000-8000-00805f9b34fb", False),
        "ota_boot_reason_readable": AutoOTACharacteristicDescription("Boot Reason (Human Readable)", "0000ffea-0000-1000-8000-00805f9b34fb", True),
    }

    def __init__(self, device: AutoOTADevice, aes_key: bytes | None = None) -> None:
        self.device = device
        self.logger = logging.getLogger(__name__)
        if aes_key == None:
            self.logger.warning("AES key is not set, OTA operations may not be successful")
        elif not isinstance(aes_key, bytes):
            self.logger.error("AES key must be of type 'bytes'")
            raise TypeError("AES key must be of type 'bytes'")
        elif len(aes_key) != 16:
            self.logger.error("AES key must be 16 bytes long")
            raise ValueError("AES key must be 16 bytes long")
        self.aes_key = aes_key
    
    async def read_device_info(self) -> dict:
        self.device._ensure_connected()
        device_info_val = {}
        try:
            service = await self.device.get_services_by_uuid(self._UUID_SERVICE_DEVICE_INFO)
            for char_desc in self.CHARACTERISTIC_DESCRIPTIONS_DEV_INFO:
                char = await self.device.get_characteristic_with_service(service.uuid, self.CHARACTERISTIC_DESCRIPTIONS_DEV_INFO[char_desc].uuid)
                if self.CHARACTERISTIC_DESCRIPTIONS_DEV_INFO[char_desc].is_human_readable:
                    value = await self.device.read_characteristic(char)
                    device_info_val[char_desc] = value.decode('utf-8') if value else None
                else:
                    value = await self.device.read_characteristic(char)
                    device_info_val[char_desc] = value.hex() if value else None
            return {
                "values": device_info_val,
                "descriptions": self.CHARACTERISTIC_DESCRIPTIONS_DEV_INFO
            }
        except Exception as e:
            self.logger.error(f"Failed to read Device Information: {e}")
            raise
    
    async def read_ota_eeprom_info(self) -> dict:
        self.device._ensure_connected()
        ota_info = ["ota_flash_bank", "ota_flash_mode", "ota_boot_reason", 
                    "ota_flash_bank_readable", "ota_flash_mode_readable", 
                    "ota_boot_reason_readable"]
        try:
            service = await self.device.get_services_by_uuid(self._UUID_SERVICE_OTA)
            ota_eeprom_info_val = {}
            ota_eeprom_info_desc = {}
            for char_desc in ota_info:
                char = await self.device.get_characteristic_with_service(service.uuid, self.CHARACTERISTIC_DESCRIPTIONS_OTA[char_desc].uuid)
                if self.CHARACTERISTIC_DESCRIPTIONS_OTA[char_desc].is_human_readable:
                    value = await self.device.read_characteristic(char)
                    ota_eeprom_info_val[char_desc] = value.decode('utf-8') if value else None
                else:
                    value = await self.device.read_characteristic(char)
                    ota_eeprom_info_val[char_desc] = value.hex() if value else None
                ota_eeprom_info_desc[char_desc] = self.CHARACTERISTIC_DESCRIPTIONS_OTA[char_desc]
            return {
                "values": ota_eeprom_info_val,
                "descriptions": ota_eeprom_info_desc
            }
        except Exception as e:
            self.logger.error(f"Failed to read OTA EEPROM info: {e}")
            raise
    
    async def read_ota_status(self) -> dict:
        result = {
            "busy": False,
            "success": False,
            "code": 0,
        }

        self.device._ensure_connected()
        try:
            service = await self.device.get_services_by_uuid(self._UUID_SERVICE_OTA)
            char = await self.device.get_characteristic_with_service(service.uuid, self.CHARACTERISTIC_DESCRIPTIONS_OTA["ota_main"].uuid)
            status_data = await self.device.read_characteristic(char)
            if not status_data:
                self.logger.error("Failed to read OTA status")
                raise RuntimeError("Failed to read OTA status")
            
            # Parse the status data
            result["busy"] = bool(status_data[0])
            result["success"] = (status_data[1] == 0x00 and result["busy"] == False)
            result["code"] = status_data[1]

            return result
        except Exception as e:
            self.logger.error(f"Failed to read OTA status: {e}")
            raise
    
    async def send_command(self, cmd: AutoOTABaseCommand) -> None:
        if self.aes_key is None:
            self.logger.error("AES key is not set, cannot send command due to authentication requirements")
            raise RuntimeError("AES key is not set, cannot send command due to authentication requirements")
        
        self.device._ensure_connected()
        try:
            cmd.cmd_validate()
        except Exception as e:
            self.logger.error(f"Command not valid: {e}")
            raise

        # Convert command to bytes
        cmd_bytes = cmd.cmd_to_bytes()
        cmd_iobuf = cmd.cmd_get_iobuf()

        # Write command to the IO buffer characteristic
        if cmd_iobuf:
            self.logger.debug(f"Writing IO buffer for command {cmd.name}: {cmd_iobuf.hex()}")
            service = await self.device.get_services_by_uuid(self._UUID_SERVICE_OTA)
            char = await self.device.get_characteristic_with_service(service.uuid, self.CHARACTERISTIC_DESCRIPTIONS_OTA["ota_buffer"].uuid)
            await self.device.write_characteristic(char, cmd_iobuf, write_resp=self.device.write_resp_flag)
        
        # Read the authentication challenge
        service = await self.device.get_services_by_uuid(self._UUID_SERVICE_OTA)
        char = await self.device.get_characteristic_with_service(service.uuid, self.CHARACTERISTIC_DESCRIPTIONS_OTA["ota_challenge"].uuid)
        challenge = await self.device.read_characteristic(char)
        if not challenge:
            self.logger.error("Failed to read authentication challenge")
            raise RuntimeError("Failed to read authentication challenge")
        
        # Process the challenge
        # 1. Calculate the CMAC of the command bytes
        cmac = CMAC(algorithms.AES(self.aes_key), backend=default_backend())
        cmac.update(cmd_bytes)
        cmd_bytes_cmac = cmac.finalize()
        self.logger.debug(f"Command CMAC: {cmd_bytes_cmac.hex()}")

        # 2. Calculate the CMAC of the io buffer
        if cmd_iobuf:
            cmac_iobuf = CMAC(algorithms.AES(self.aes_key), backend=default_backend())
            cmac_iobuf.update(cmd_iobuf)
            cmd_iobuf_cmac = cmac_iobuf.finalize()
            self.logger.debug(f"IO Buffer CMAC: {cmd_iobuf_cmac.hex()}")
        else:
            # Placeholder for empty IO buffer CMAC
            cmd_iobuf_cmac = b'\x00' * 16
            self.logger.debug(f"Empty IO Buffer, using placeholder CMAC: {cmd_iobuf_cmac.hex()}")
        
        # 3. Concatenate the command CMAC and IO buffer CMAC and Authentication Challenge
        token = cmd_bytes_cmac + cmd_iobuf_cmac + challenge
        self.logger.debug(f"Token before signature: {token.hex()}")

        # 4. Calculate the CMAC of the token
        cmac_token = CMAC(algorithms.AES(self.aes_key), backend=default_backend())
        cmac_token.update(token)
        token_signature = cmac_token.finalize()
        self.logger.debug(f"Token Signature: {token_signature.hex()}")

        # 5. Write the token to the OTA Token characteristic
        char = await self.device.get_characteristic_with_service(service.uuid, self.CHARACTERISTIC_DESCRIPTIONS_OTA["ota_token"].uuid)
        await self.device.write_characteristic(char, token_signature, write_resp=self.device.write_resp_flag)
        self.logger.debug(f"Token signature sent to device")

        # Write the command bytes to the OTA Main Command characteristic
        char = await self.device.get_characteristic_with_service(service.uuid, self.CHARACTERISTIC_DESCRIPTIONS_OTA["ota_main"].uuid)
        await self.device.write_characteristic(char, cmd_bytes) # must be written with response to confirm command was processed
        self.logger.debug(f"Command {cmd.name} sent to device")

        # Read the result from the IO buffer characteristic if the command requires a result
        if cmd.cmd_need_result():
            self.logger.debug(f"Command {cmd.name} requires result, reading IO buffer")
            char = await self.device.get_characteristic_with_service(service.uuid, self.CHARACTERISTIC_DESCRIPTIONS_OTA["ota_buffer"].uuid)
            self.logger.debug(f"Reading result from characteristic {char.uuid}")
            result_data = await self.device.read_characteristic(char)
            cmd.cmd_set_result(result_data)
            self.logger.debug(f"Command {cmd.name} result: {result_data.hex() if result_data else 'None'}")
    
    async def read_io_buffer(self) -> bytes:
        self.device._ensure_connected()
        try:
            service = await self.device.get_services_by_uuid(self._UUID_SERVICE_OTA)
            char = await self.device.get_characteristic_with_service(service.uuid, self.CHARACTERISTIC_DESCRIPTIONS_OTA["ota_buffer"].uuid)
            return await self.device.read_characteristic(char)
        except Exception as e:
            self.logger.error(f"Failed to read IO buffer: {e}")
            raise