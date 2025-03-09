"""
UWB Sensor Model for UWB-RFID Indoor Positioning System.

This module provides classes for simulating Ultra-Wideband sensors,
including noise models, range error simulation, and measurement generation.
"""

import numpy as np
import time
from typing import Dict, List, Tuple, Optional, Set
import uuid
import math


class UWBSensor:
    """Base class for a UWB sensor/anchor in the positioning system."""
    
    def __init__(self, 
                 sensor_id: Optional[str] = None,
                 position: Tuple[float, float, float] = (0, 0, 0),
                 range_noise_std: float = 0.1,  # Standard deviation of range noise (meters)
                 max_range: float = 100.0,     # Maximum detection range (meters)
                 detection_probability: float = 0.95,  # Probability of successful detection
                 update_rate: float = 10.0):    # Measurement rate (Hz)
        """
        Initialize UWB sensor/anchor.
        
        Args:
            sensor_id: Unique identifier for the sensor
            position: Position (x, y, z) in meters
            range_noise_std: Standard deviation of Gaussian noise for range measurement
            max_range: Maximum range for reliable detection
            detection_probability: Probability of detection for each measurement
            update_rate: Measurement update rate in Hz
        """
        self.sensor_id = sensor_id if sensor_id else f"uwb_{str(uuid.uuid4())[:8]}"
        self.position = position
        self.range_noise_std = range_noise_std
        self.max_range = max_range
        self.detection_probability = detection_probability
        self.update_rate = update_rate
        
        # Timestamp of the last measurement
        self.last_measurement_time = 0.0
        
    def measure_distance(self, target_position: Tuple[float, float, float], 
                         current_time: Optional[float] = None) -> Optional[float]:
        """
        Measure distance to a target position with simulated noise.
        
        Args:
            target_position: Target (x, y, z) position in meters
            current_time: Current timestamp (default: time.time())
            
        Returns:
            Measured distance in meters or None if out of range/not detected
        """
        if current_time is None:
            current_time = time.time()
            
        # Check measurement rate (return None if too soon since last measurement)
        if current_time - self.last_measurement_time < 1.0 / self.update_rate:
            return None
            
        # Update last measurement time
        self.last_measurement_time = current_time
        
        # Compute true distance
        dx = target_position[0] - self.position[0]
        dy = target_position[1] - self.position[1]
        dz = target_position[2] - self.position[2]
        true_distance = math.sqrt(dx**2 + dy**2 + dz**2)
        
        # Check if target is within range
        if true_distance > self.max_range:
            return None
            
        # Simulate detection probability
        if np.random.random() > self.detection_probability:
            return None
            
        # Add Gaussian noise to the range measurement
        noise = np.random.normal(0, self.range_noise_std)
        measured_distance = true_distance + noise
        
        # Ensure non-negative distance
        return max(0.0, measured_distance)
        
    def get_info(self) -> Dict:
        """
        Get sensor information.
        
        Returns:
            Dictionary with sensor information
        """
        return {
            "sensor_id": self.sensor_id,
            "position": self.position,
            "type": "uwb",
            "properties": {
                "range_noise_std": self.range_noise_std,
                "max_range": self.max_range,
                "detection_probability": self.detection_probability,
                "update_rate": self.update_rate
            }
        }


class UWBSensorNetwork:
    """A network of UWB sensors/anchors for trilateration."""
    
    def __init__(self):
        """Initialize an empty UWB sensor network."""
        self.sensors: Dict[str, UWBSensor] = {}
        
    def add_sensor(self, sensor: UWBSensor) -> str:
        """
        Add a sensor to the network.
        
        Args:
            sensor: UWBSensor instance
            
        Returns:
            ID of the added sensor
        """
        self.sensors[sensor.sensor_id] = sensor
        return sensor.sensor_id
        
    def remove_sensor(self, sensor_id: str) -> bool:
        """
        Remove a sensor from the network.
        
        Args:
            sensor_id: ID of the sensor to remove
            
        Returns:
            True if sensor was removed, False if not found
        """
        if sensor_id in self.sensors:
            del self.sensors[sensor_id]
            return True
        return False
    
    def measure_distances(self, tag_position: Tuple[float, float, float], 
                         current_time: Optional[float] = None) -> Dict[str, float]:
        """
        Measure distances from all sensors to a tag position.
        
        Args:
            tag_position: Tag (x, y, z) position in meters
            current_time: Current timestamp (default: time.time())
            
        Returns:
            Dictionary mapping sensor IDs to measured distances
        """
        if current_time is None:
            current_time = time.time()
            
        measurements = {}
        
        for sensor_id, sensor in self.sensors.items():
            distance = sensor.measure_distance(tag_position, current_time)
            if distance is not None:
                measurements[sensor_id] = distance
                
        return measurements
    
    def get_sensor_positions(self) -> Dict[str, Tuple[float, float, float]]:
        """
        Get positions of all sensors in the network.
        
        Returns:
            Dictionary mapping sensor IDs to positions
        """
        return {sensor_id: sensor.position for sensor_id, sensor in self.sensors.items()}
    
    def get_info(self) -> Dict:
        """
        Get information about the sensor network.
        
        Returns:
            Dictionary with sensor network information
        """
        return {
            "num_sensors": len(self.sensors),
            "sensors": [sensor.get_info() for sensor in self.sensors.values()]
        }
        
    @classmethod
    def create_grid_layout(cls, 
                          width: float, 
                          length: float, 
                          height: float,
                          grid_size: float = 10.0,
                          z_height: float = 3.0,
                          sensor_properties: Optional[Dict] = None) -> 'UWBSensorNetwork':
        """
        Create a grid layout of sensors.
        
        Args:
            width: Width of the area in meters
            length: Length of the area in meters
            height: Height of the area in meters
            grid_size: Size of the grid cells in meters
            z_height: Height at which to place the sensors
            sensor_properties: Properties to apply to all sensors
            
        Returns:
            UWBSensorNetwork instance with grid-arranged sensors
        """
        network = cls()
        
        # Default sensor properties
        if sensor_properties is None:
            sensor_properties = {}
            
        # Calculate number of sensors in each dimension
        nx = max(2, int(width / grid_size) + 1)
        ny = max(2, int(length / grid_size) + 1)
        
        # Create grid of sensors
        for i in range(nx):
            for j in range(ny):
                # Place sensors only at perimeter for efficiency
                if i == 0 or i == nx-1 or j == 0 or j == ny-1:
                    x = i * grid_size
                    y = j * grid_size
                    
                    # Ensure within bounds
                    x = min(width, max(0, x))
                    y = min(length, max(0, y))
                    
                    # Create sensor
                    sensor = UWBSensor(
                        position=(x, y, z_height),
                        **sensor_properties
                    )
                    
                    network.add_sensor(sensor)
        
        # Add center sensors if area is large
        if width > 3 * grid_size and length > 3 * grid_size:
            # Add a center sensor
            sensor = UWBSensor(
                position=(width/2, length/2, z_height),
                **sensor_properties
            )
            network.add_sensor(sensor)
        
        return network