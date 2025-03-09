"""
RFID Reader Model for UWB-RFID Indoor Positioning System.

This module provides classes for simulating RFID readers and tags,
including detection models and signal strength simulation.
"""

import numpy as np
import time
import math
import uuid
from typing import Dict, List, Tuple, Optional, Set


class RFIDTag:
    """
    Represents an RFID tag that can be attached to objects.
    """
    
    def __init__(self, 
                 tag_id: Optional[str] = None,
                 tag_type: str = "passive",  # "passive" or "active"
                 transmit_power: float = 0.0,  # dBm for active tags
                 position_offset: Tuple[float, float, float] = (0, 0, 0)):
        """
        Initialize RFID tag.
        
        Args:
            tag_id: Unique identifier for the tag
            tag_type: Type of tag ("passive" or "active")
            transmit_power: Transmit power in dBm (for active tags)
            position_offset: Offset from the parent object position
        """
        self.tag_id = tag_id if tag_id else f"rfid_{str(uuid.uuid4())[:8]}"
        self.tag_type = tag_type
        self.transmit_power = transmit_power if tag_type == "active" else 0.0
        self.position_offset = position_offset
        
    def get_info(self) -> Dict:
        """
        Get tag information.
        
        Returns:
            Dictionary with tag information
        """
        return {
            "tag_id": self.tag_id,
            "tag_type": self.tag_type,
            "transmit_power": self.transmit_power,
            "position_offset": self.position_offset
        }


class RFIDReader:
    """
    Represents an RFID reader that can detect RFID tags.
    """
    
    def __init__(self, 
                 reader_id: Optional[str] = None,
                 position: Tuple[float, float, float] = (0, 0, 0),
                 read_range: float = 5.0,  # Maximum read range in meters
                 frequency: float = 915.0,  # MHz
                 transmit_power: float = 30.0,  # dBm
                 antenna_gain: float = 6.0,  # dBi
                 detection_threshold: float = -80.0,  # dBm
                 polarization_loss: float = 3.0,  # dB
                 update_rate: float = 1.0):  # Hz
        """
        Initialize RFID reader.
        
        Args:
            reader_id: Unique identifier for the reader
            position: Position (x, y, z) in meters
            read_range: Maximum read range in meters
            frequency: Operating frequency in MHz
            transmit_power: Transmit power in dBm
            antenna_gain: Antenna gain in dBi
            detection_threshold: RSSI threshold for tag detection
            polarization_loss: Loss due to antenna polarization mismatch
            update_rate: Measurement update rate in Hz
        """
        self.reader_id = reader_id if reader_id else f"reader_{str(uuid.uuid4())[:8]}"
        self.position = position
        self.read_range = read_range
        self.frequency = frequency
        self.transmit_power = transmit_power
        self.antenna_gain = antenna_gain
        self.detection_threshold = detection_threshold
        self.polarization_loss = polarization_loss
        self.update_rate = update_rate
        
        # Last measurement time
        self.last_measurement_time = 0.0
        
        # Currently detected tags
        self.detected_tags: Set[str] = set()
    
    def detect_tag(self, tag: RFIDTag, tag_position: Tuple[float, float, float], 
                  current_time: Optional[float] = None) -> Optional[Dict]:
        """
        Detect a tag and calculate signal strength.
        
        Args:
            tag: RFIDTag instance
            tag_position: Position of the tag (x, y, z) in meters
            current_time: Current timestamp (default: time.time())
            
        Returns:
            Detection information or None if not detected
        """
        if current_time is None:
            current_time = time.time()
            
        # Check measurement rate (return None if too soon since last measurement)
        if current_time - self.last_measurement_time < 1.0 / self.update_rate:
            return None
            
        # Compute tag absolute position by applying offset
        absolute_position = (
            tag_position[0] + tag.position_offset[0],
            tag_position[1] + tag.position_offset[1],
            tag_position[2] + tag.position_offset[2]
        )
        
        # Compute distance between reader and tag
        dx = absolute_position[0] - self.position[0]
        dy = absolute_position[1] - self.position[1]
        dz = absolute_position[2] - self.position[2]
        distance = math.sqrt(dx**2 + dy**2 + dz**2)
        
        # Check if tag is within read range
        if distance > self.read_range:
            # Tag out of range
            if tag.tag_id in self.detected_tags:
                self.detected_tags.remove(tag.tag_id)
            return None
        
        # Calculate free space path loss (in dB)
        # FSPL = 20 * log10(d) + 20 * log10(f) + 20 * log10(4π/c) 
        wavelength = 299792458 / (self.frequency * 1e6)  # c/f, wavelength in meters
        fspl = 20 * math.log10(distance) + 20 * math.log10(self.frequency * 1e6) - 147.55
        
        # Calculate received power
        if tag.tag_type == "passive":
            # For passive tags, we use radar equation (two-way path loss)
            # Forward path loss
            forward_loss = fspl
            # Backward path loss (tag to reader)
            backward_loss = fspl
            
            # Backscatter efficiency
            backscatter_efficiency = -10  # dB, typical value
            
            # Received signal strength
            received_power = (self.transmit_power + self.antenna_gain - forward_loss + 
                             backscatter_efficiency - backward_loss - self.polarization_loss)
        else:
            # For active tags, use standard path loss model
            received_power = tag.transmit_power - fspl + self.antenna_gain - self.polarization_loss
        
        # Add random fluctuation
        fluctuation = np.random.normal(0, 3.0)  # 3 dB standard deviation
        received_power += fluctuation
        
        # Check if received power is above detection threshold
        if received_power < self.detection_threshold:
            # Tag signal too weak
            if tag.tag_id in self.detected_tags:
                self.detected_tags.remove(tag.tag_id)
            return None