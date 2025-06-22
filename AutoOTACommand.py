#coding: utf-8

import struct

OTA_CMD_READ = 0x00
OTA_CMD_PROGRAM = 0x01
OTA_CMD_ERASE = 0x02
OTA_CMD_VERIFY = 0x03
OTA_CMD_REBOOT = 0x04
OTA_CMD_CONFIRM = 0x05

class AutoOTABaseCommand():
    def __init__(self, **kwargs) -> None:
        """
        Initialize the base command for AutoOTA.
        :param kwargs: Additional parameters for the command.
        """
        self.command = 0xff
        self.name = "BaseCommand"
        self.description = "Base command for AutoOTA"
        self.has_result = False
        self.kwargs = kwargs
    
    def cmd_validate(self) -> bool:
        """
        Validate the command and its parameters.
        This method should be overridden by subclasses to implement specific validation logic.
        """
        return True
    
    def cmd_to_bytes(self) -> bytes:
        """
        Convert the command and its parameters to a byte representation.
        This method should be overridden by subclasses to implement specific conversion logic.
        """
        raise NotImplementedError("Subclasses must implement cmd_to_bytes method.")
    
    def cmd_get_iobuf(self) -> bytes | None:
        """
        Get the input/output buffer for the command.
        This method should be overridden by subclasses to implement specific buffer logic.
        """
        return None
    
    def cmd_need_result(self) -> bool:
        """
        Check if the command requires a result.
        :return: True if the command has a result, False otherwise.
        """
        return self.has_result

    def cmd_set_result(self, iobuf: bytes) -> None:
        """
        Set the result of the command based on the input/output buffer.
        This method should be overridden by subclasses to implement specific result setting logic.
        :param iobuf: The input/output buffer containing the result data.
        """
        raise NotImplementedError("Subclasses must implement cmd_set_result method.")
    
    def __repr__(self) -> str:
        """
        Return a string representation of the command.
        This method should be overridden by subclasses to implement specific representation logic.
        """
        classname = self.__class__.__name__
        params = ' '.join(f"{k}={v}" for k, v in self.kwargs.items())
        return f"<{classname} command={self.name} ({self.command:#02x}) {params}>"

class AutoOTAReadCommand(AutoOTABaseCommand):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.command = OTA_CMD_READ
        self.name = "ReadCommand"
        self.description = "Command to read data from the device"
        self.has_result = True
        self.read_result = None
    
    def cmd_validate(self):
        if self.kwargs.get('address') is None:
            raise ValueError("ReadCommand requires 'address' parameter.")
        if not isinstance(self.kwargs['address'], int):
            raise TypeError("The 'address' parameter must be an integer.")
        if self.kwargs.get('length') is None:
            raise ValueError("ReadCommand requires 'length' parameter.")
        if not isinstance(self.kwargs['length'], int) or self.kwargs['length'] <= 0:
            raise TypeError("The 'length' parameter must be a positive integer.")
        return True
    
    def cmd_to_bytes(self) -> bytes:
        # Convert the command to bytes
        return bytes([self.command]) + struct.pack('<I', self.kwargs['address']) + struct.pack('<I', self.kwargs['length'])
    
    def cmd_set_result(self, iobuf) -> None:
        self.read_result = iobuf

class AutoOTAProgramCommand(AutoOTABaseCommand):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.command = OTA_CMD_PROGRAM
        self.name = "ProgramCommand"
        self.description = "Command to program data to the device"
    
    def cmd_validate(self):
        if self.kwargs.get('address') is None:
            raise ValueError("ProgramCommand requires 'address' parameter.")
        if not isinstance(self.kwargs['address'], int):
            raise TypeError("The 'address' parameter must be an integer.")
        if self.kwargs.get('data') is None:
            raise ValueError("ProgramCommand requires 'data' parameter.")
        if not isinstance(self.kwargs['data'], bytes):
            raise TypeError("The 'data' parameter must be of type bytes.")
        return True
    
    def cmd_to_bytes(self) -> bytes:
        # Convert the command to bytes
        return bytes([self.command]) + struct.pack('<I', self.kwargs['address'])
    
    def cmd_get_iobuf(self) -> bytes:
        """
        Get the input/output buffer for the command.
        This method returns the data to be programmed as a byte array.
        """
        if 'data' in self.kwargs:
            return self.kwargs['data']
        return None

class AutoOTAEraseCommand(AutoOTABaseCommand):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.command = OTA_CMD_ERASE
        self.name = "EraseCommand"
        self.description = "Command to erase data on the device"
    
    def cmd_validate(self):
        if self.kwargs.get('address') is None:
            raise ValueError("EraseCommand requires 'address' parameter.")
        if not isinstance(self.kwargs['address'], int):
            raise TypeError("The 'address' parameter must be an integer.")
        if self.kwargs.get('length') is None:
            raise ValueError("EraseCommand requires 'length' parameter.")
        if not isinstance(self.kwargs['length'], int) or self.kwargs['length'] <= 0:
            raise TypeError("The 'length' parameter must be a positive integer.")
        return True
    
    def cmd_to_bytes(self) -> bytes:
        # Convert the command to bytes
        return bytes([self.command]) + struct.pack('<I', self.kwargs['address']) + struct.pack('<I', self.kwargs['length'])

class AutoOTAVerifyCommand(AutoOTABaseCommand):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.command = OTA_CMD_VERIFY
        self.name = "VerifyCommand"
        self.description = "Command to verify data on the device (SHA-256 hash)"
    
    def cmd_validate(self):
        if self.kwargs.get('address') is None:
            raise ValueError("VerifyCommand requires 'address' parameter.")
        if not isinstance(self.kwargs['address'], int):
            raise TypeError("The 'address' parameter must be an integer.")
        if self.kwargs.get('length') is None:
            raise ValueError("VerifyCommand requires 'length' parameter.")
        if not isinstance(self.kwargs['length'], int) or self.kwargs['length'] <= 0:
            raise TypeError("The 'length' parameter must be a positive integer.")
        return True
    
    def cmd_to_bytes(self) -> bytes:
        # Convert the command to bytes
        return bytes([self.command]) + struct.pack('<I', self.kwargs['address']) + struct.pack('<I', self.kwargs['length'])

class AutoOTARebootCommand(AutoOTABaseCommand):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.command = OTA_CMD_REBOOT
        self.name = "RebootCommand"
        self.description = "Command to reboot the device"
    
    def cmd_to_bytes(self) -> bytes:
        # Convert the command to bytes
        return bytes([self.command])

class AutoOTAConfirmCommand(AutoOTABaseCommand):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.command = OTA_CMD_CONFIRM
        self.name = "ConfirmCommand"
        self.description = "Command to commit the OTA operation and reboot the device"
    
    def cmd_to_bytes(self) -> bytes:
        # Convert the command to bytes
        return bytes([self.command])
