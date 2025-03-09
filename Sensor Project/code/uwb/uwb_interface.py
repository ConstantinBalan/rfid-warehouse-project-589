#!/usr/bin/env python3
"""
UWB Sensor Interface Module

This module provides the interface for communicating with DWM1000/DWM3000 
Ultra-Wideband sensors via SPI on a Raspberry Pi.
"""

import time
import json
import logging
import numpy as np
from typing import Dict, List, Tuple
import spidev
import RPi.GPIO as GPIO

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('uwb_interface')

class UWBSensor:
    """Interface for the DWM1000/DWM3000 UWB sensor modules."""
    
    # DWM1000 Register addresses
    DEV_ID = 0x00
    SYS_CFG = 0x04
    TX_FCTRL = 0x08
    SYS_STATUS = 0x0F
    
    def __init__(self, spi_bus: int = 0, spi_device: int = 0, reset_pin: int = 17, irq_pin: int = 27):
        """
        Initialize UWB sensor interface.
        
        Args:
            spi_bus: SPI bus number
            spi_device: SPI device number
            reset_pin: GPIO pin connected to module reset
            irq_pin: GPIO pin connected to module interrupt
        """
        self.spi_bus = spi_bus
        self.spi_device = spi_device
        self.reset_pin = reset_pin
        self.irq_pin = irq_pin
        self.spi = None
        self.initialized = False
        self.sensor_id = None
        self.sensor_position = None
        
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.reset_pin, GPIO.OUT)
        GPIO.setup(self.irq_pin, GPIO.IN)
        
        logger.info("UWB sensor interface initialized")
    
    def setup(self):
        """Initialize SPI communication and configure UWB sensor."""
        # Initialize SPI
        self.spi = spidev.SpiDev()
        self.spi.open(self.spi_bus, self.spi_device)
        self.spi.max_speed_hz = 1000000  # 1MHz
        self.spi.mode = 0
        
        # Reset device
        self._reset_device()
        
        # Read device ID to verify communication
        device_id = self._read_register(self.DEV_ID, 4)
        if device_id:
            logger.info(f"Connected to UWB device, ID: 0x{device_id.hex()}")
            self.initialized = True
            
            # Configure for ranging
            self._configure_ranging()
            return True
        else:
            logger.error("Failed to communicate with UWB device")
            return False
    
    def _reset_device(self):
        """Reset the UWB module using the reset pin."""
        GPIO.output(self.reset_pin, GPIO.LOW)
        time.sleep(0.1)
        GPIO.output(self.reset_pin, GPIO.HIGH)
        time.sleep(0.5)  # Wait for device to initialize
    
    def _read_register(self, register: int, length: int) -> bytes:
        """
        Read data from a register.
        
        Args:
            register: Register address
            length: Number of bytes to read
            
        Returns:
            Bytes read from register
        """
        try:
            # Create read command (0x80 | register)
            header = bytes([0x80 | register, 0x00])
            
            # Send command and read response
            self.spi.xfer2(list(header))
            result = self.spi.readbytes(length)
            return bytes(result)
        except Exception as e:
            logger.error(f"SPI read error: {e}")
            return None
    
    def _write_register(self, register: int, data: bytes) -> bool:
        """
        Write data to a register.
        
        Args:
            register: Register address
            data: Bytes to write
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create write command
            header = bytes([register & 0x7F, 0x00])
            
            # Send command and data
            self.spi.xfer2(list(header) + list(data))
            return True
        except Exception as e:
            logger.error(f"SPI write error: {e}")
            return False
    
    def _configure_ranging(self):
        """Configure the device for ranging measurements."""
        # Example configuration - would need to be adapted for specific sensor model
        # Set pulse repetition frequency and data rate
        self._write_register(self.SYS_CFG, bytes([0x20, 0x44]))
        # Configure transmit frame control
        self._write_register(self.TX_FCTRL, bytes([0x0C, 0x00, 0x00, 0x00]))
        logger.info("UWB sensor configured for ranging")
    
    def measure_distance(self, target_id: str) -> float:
        """
        Measure distance to another UWB device.
        
        Args:
            target_id: ID of the target device
            
        Returns:
            Measured distance in meters
        """
        if not self.initialized:
            logger.error("UWB sensor not initialized")
            return None
            
        # In a real implementation, this would perform two-way ranging
        # with the target device. For simulation, we'll return a random value.
        # This should be replaced with actual ranging code.
        
        # Simulate ranging delay
        time.sleep(0.05)
        
        # Return simulated distance (3-15 meters with some noise)
        distance = 3.0 + np.random.rand() * 12.0
        noise = np.random.normal(0, 0.05)  # 5cm standard deviation noise
        
        logger.debug(f"Measured distance to {target_id}: {distance+noise:.3f}m")
        return distance + noise
    
    def set_sensor_position(self, position: Tuple[float, float, float], sensor_id: str):
        """
        Set the fixed position of this sensor.
        
        Args:
            position: (x, y, z) coordinates of the sensor
            sensor_id: Unique identifier for this sensor
        """
        self.sensor_position = position
        self.sensor_id = sensor_id
        logger.info(f"Sensor {sensor_id} position set to {position}")
    
    def get_sensor_info(self) -> Dict:
        """
        Get sensor information.
        
        Returns:
            Dictionary with sensor information
        """
        return {
            "id": self.sensor_id,
            "position": self.sensor_position,
            "initialized": self.initialized
        }
    
    def close(self):
        """Close SPI connection and clean up GPIO."""
        if self.spi:
            self.spi.close()
        GPIO.cleanup([self.reset_pin, self.irq_pin])
        logger.info("UWB sensor interface closed")


# Example usage
if __name__ == "__main__":
    # Create sensor interface
    sensor = UWBSensor()
    
    try:
        # Initialize sensor
        if sensor.setup():
            # Set sensor position (x, y, z) in meters
            sensor.set_sensor_position((0.0, 0.0, 2.5), "uwb_sensor_1")
            
            # Perform ranging
            for i in range(10):
                distance = sensor.measure_distance("uwb_sensor_2")
                print(f"Distance: {distance:.3f}m")
                time.sleep(1)
    finally:
        # Clean up
        sensor.close()
