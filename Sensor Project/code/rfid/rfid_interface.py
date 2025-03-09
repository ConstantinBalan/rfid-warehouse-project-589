#!/usr/bin/env python3
"""
RFID Reader Interface Module

This module provides the interface for communicating with RFID readers
to detect tags attached to pallets.
"""

import time
import json
import logging
import serial
from typing import Dict, List, Optional
import os
import random  # For simulation

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('rfid_interface')

class RFIDReader:
    """Interface for RFID readers to detect pallet tags."""
    
    def __init__(self, port: str = None, baud_rate: int = 9600, reader_id: str = None, 
                 simulate: bool = False):
        """
        Initialize RFID reader interface.
        
        Args:
            port: Serial port for the RFID reader (e.g., '/dev/ttyUSB0')
            baud_rate: Serial baud rate
            reader_id: Unique identifier for this reader
            simulate: If True, simulate tag readings instead of using actual hardware
        """
        self.port = port
        self.baud_rate = baud_rate
        self.reader_id = reader_id or f"reader_{os.getpid()}"
        self.simulate = simulate
        self.serial = None
        self.connected = False
        self.known_tags = {}  # Dictionary mapping tag IDs to pallet information
        
        logger.info(f"RFID reader {self.reader_id} initialized")
    
    def connect(self) -> bool:
        """
        Connect to the RFID reader hardware.
        
        Returns:
            True if connection successful, False otherwise
        """
        if self.simulate:
            logger.info(f"Reader {self.reader_id} in simulation mode")
            self.connected = True
            return True
            
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=1.0
            )
            self.connected = True
            logger.info(f"Connected to RFID reader on {self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to RFID reader: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the RFID reader hardware."""
        if self.serial and self.connected and not self.simulate:
            self.serial.close()
        self.connected = False
        logger.info(f"Disconnected from RFID reader {self.reader_id}")
    
    def load_tag_database(self, database_file: str) -> bool:
        """
        Load known tags from a database file.
        
        Args:
            database_file: Path to JSON file with tag information
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(database_file, 'r') as f:
                self.known_tags = json.load(f)
            logger.info(f"Loaded {len(self.known_tags)} tags from database")
            return True
        except Exception as e:
            logger.error(f"Failed to load tag database: {e}")
            return False
    
    def read_tags(self) -> List[Dict]:
        """
        Read all RFID tags currently in range.
        
        Returns:
            List of tag information dictionaries with 'tag_id', 'pallet_id', etc.
        """
        if not self.connected:
            logger.error("Cannot read tags: RFID reader not connected")
            return []
        
        # Actual implementation would read from serial port
        # For simulation, we'll return random tags from the known tags list
        if self.simulate:
            return self._simulate_tag_reading()
        else:
            return self._read_from_hardware()
    
    def _simulate_tag_reading(self) -> List[Dict]:
        """Simulate reading tags (for testing without hardware)."""
        result = []
        
        # If no known tags, create some demo tags
        if not self.known_tags:
            self._create_demo_tags()
        
        # Random number of tags (0-3)
        num_tags = random.randint(0, min(3, len(self.known_tags)))
        
        if num_tags > 0:
            # Select random tags from known tags
            tag_ids = random.sample(list(self.known_tags.keys()), num_tags)
            
            for tag_id in tag_ids:
                tag_info = self.known_tags[tag_id].copy()
                tag_info['tag_id'] = tag_id
                tag_info['timestamp'] = time.time()
                tag_info['reader_id'] = self.reader_id
                tag_info['signal_strength'] = random.uniform(0.5, 1.0)
                result.append(tag_info)
        
        return result
    
    def _read_from_hardware(self) -> List[Dict]:
        """Read tags from actual RFID reader hardware."""
        result = []
        
        try:
            # Clear input buffer
            self.serial.reset_input_buffer()
            
            # Send command to read tags (specific to your RFID reader)
            self.serial.write(b'READ\r\n')
            
            # Wait for response
            time.sleep(0.1)
            
            # Read response
            if self.serial.in_waiting:
                response = self.serial.read_all().decode('utf-8').strip()
                
                # Parse response (format depends on your RFID reader)
                # This is just an example parser and will need to be adapted
                tag_ids = response.split(',')
                
                for tag_id in tag_ids:
                    if tag_id and tag_id in self.known_tags:
                        tag_info = self.known_tags[tag_id].copy()
                        tag_info['tag_id'] = tag_id
                        tag_info['timestamp'] = time.time()
                        tag_info['reader_id'] = self.reader_id
                        result.append(tag_info)
                    elif tag_id:
                        # Unknown tag
                        result.append({
                            'tag_id': tag_id,
                            'timestamp': time.time(),
                            'reader_id': self.reader_id,
                            'pallet_id': 'unknown',
                            'content_type': 'unknown'
                        })
        
        except Exception as e:
            logger.error(f"Error reading from RFID hardware: {e}")
        
        return result
    
    def _create_demo_tags(self):
        """Create demo tags for simulation."""
        self.known_tags = {
            'E2000000123456': {
                'pallet_id': 'PLT-A001',
                'content_type': 'Electronics',
                'weight_kg': 320,
                'destination': 'Warehouse B'
            },
            'E2000000123457': {
                'pallet_id': 'PLT-A002',
                'content_type': 'Food Products',
                'weight_kg': 450,
                'destination': 'Distribution Center'
            },
            'E2000000123458': {
                'pallet_id': 'PLT-A003',
                'content_type': 'Clothing',
                'weight_kg': 280,
                'destination': 'Retail Store'
            },
            'E2000000123459': {
                'pallet_id': 'PLT-A004',
                'content_type': 'Pharmaceuticals',
                'weight_kg': 180,
                'destination': 'Hospital'
            },
            'E200000012345A': {
                'pallet_id': 'PLT-A005',
                'content_type': 'Raw Materials',
                'weight_kg': 620,
                'destination': 'Factory'
            }
        }
        logger.info("Created 5 demo tags for simulation")
    
    def register_tag(self, tag_id: str, pallet_info: Dict) -> bool:
        """
        Register a new tag in the system.
        
        Args:
            tag_id: RFID tag identifier
            pallet_info: Dictionary with pallet information
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.known_tags[tag_id] = pallet_info
            logger.info(f"Registered tag {tag_id} for pallet {pallet_info.get('pallet_id')}")
            return True
        except Exception as e:
            logger.error(f"Failed to register tag: {e}")
            return False


# Example usage
if __name__ == "__main__":
    # Create RFID reader with simulation mode
    reader = RFIDReader(simulate=True)
    
    try:
        # Connect to reader
        reader.connect()
        
        # Read tags 5 times
        for i in range(5):
            tags = reader.read_tags()
            if tags:
                print(f"Read {len(tags)} tags:")
                for tag in tags:
                    print(f"  - {tag['tag_id']}: {tag['pallet_id']} ({tag['content_type']})")
            else:
                print("No tags detected")
            time.sleep(1)
    
    finally:
        # Clean up
        reader.disconnect()
