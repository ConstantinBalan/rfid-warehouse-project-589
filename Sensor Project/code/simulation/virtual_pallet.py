"""
Virtual Pallet for UWB-RFID Indoor Positioning System.

This module provides the VirtualPallet class for simulating pallets in a warehouse
environment, including position tracking and tag management.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional
import time
import uuid
import json

@dataclass
class PositionRecord:
    position: Tuple[float, float, float]
    timestamp: float
    
class VirtualPallet:
    def __init__(self, 
                 pallet_id: Optional[str] = None,
                 position: Tuple[float, float, float] = (0, 0, 0),
                 dimensions: Tuple[float, float, float] = (1.2, 0.8, 0.144),  # Standard EUR pallet
                 content_type: str = "generic",
                 weight: float = 0.0):
        """
        Initialize a virtual pallet.
        
        Args:
            pallet_id: Unique identifier for the pallet
            position: Initial position (x, y, z) in meters
            dimensions: Pallet dimensions (width, length, height) in meters
            content_type: Type of content on the pallet
            weight: Weight of the pallet including content in kg
        """
        self.pallet_id = pallet_id if pallet_id else str(uuid.uuid4())
        self.position = position
        self.dimensions = dimensions
        self.content_type = content_type
        self.weight = weight
        
        # For tracking movement history
        self.position_history: List[PositionRecord] = [
            PositionRecord(position, time.time())
        ]
        
        # For attaching tags
        self.tag_ids: List[str] = []
    
    def attach_tag(self, tag_id: str):
        """
        Attach an RFID/UWB tag to the pallet.
        
        Args:
            tag_id: ID of the tag to attach
        """
        if tag_id not in self.tag_ids:
            self.tag_ids.append(tag_id)
    
    def detach_tag(self, tag_id: str) -> bool:
        """
        Detach a tag from the pallet.
        
        Args:
            tag_id: ID of the tag to detach
            
        Returns:
            True if tag was detached, False if tag not found
        """
        if tag_id in self.tag_ids:
            self.tag_ids.remove(tag_id)
            return True
        return False
    
    def move_to(self, position: Tuple[float, float, float], 
                timestamp: Optional[float] = None) -> bool:
        """
        Move pallet to a new position.
        
        Args:
            position: New position (x, y, z)
            timestamp: Timestamp for the movement, defaults to current time
            
        Returns:
            bool: True if move was successful
        """
        if timestamp is None:
            timestamp = time.time()
        
        # Update position
        self.position = position
        
        # Add to history
        self.position_history.append(PositionRecord(position, timestamp))
        
        # Limit history size to avoid memory issues in long simulations
        if len(self.position_history) > 1000:
            self.position_history = self.position_history[-1000:]
            
        return True
    
    def check_collision(self, obstacles: List, other_pallets: List['VirtualPallet']) -> bool:
        """
        Check if pallet collides with obstacles or other pallets.
        
        Args:
            obstacles: List of obstacles to check against
            other_pallets: List of other pallets to check against
            
        Returns:
            bool: True if collision is detected
        """
        x, y, z = self.position
        w, l, h = self.dimensions
        
        # Check collision with obstacles
        for obstacle in obstacles:
            ox, oy, oz = obstacle.position
            ow, ol, oh = obstacle.dimensions
            
            # Simple box collision check
            if (x < ox + ow and x + w > ox and
                y < oy + ol and y + l > oy and
                z < oz + oh and z + h > oz):
                return True
        
        # Check collision with other pallets
        for other in other_pallets:
            # Skip self
            if other.pallet_id == self.pallet_id:
                continue
                
            ox, oy, oz = other.position
            ow, ol, oh = other.dimensions
            
            # Simple box collision check
            if (x < ox + ow and x + w > ox and
                y < oy + ol and y + l > oy and
                z < oz + oh and z + h > oz):
                return True
        
        return False
    
    def get_position_history(self, time_range: Optional[Tuple[float, float]] = None) -> List[Dict]:
        """
        Get position history within a time range.
        
        Args:
            time_range: Optional tuple of (start_time, end_time)
            
        Returns:
            List of position records
        """
        if time_range is None:
            return [{"position": r.position, "timestamp": r.timestamp} 
                    for r in self.position_history]
        
        start_time, end_time = time_range
        return [{"position": r.position, "timestamp": r.timestamp} 
                for r in self.position_history 
                if start_time <= r.timestamp <= end_time]
    
    def get_velocity(self, window_size: int = 2) -> Tuple[float, float, float]:
        """
        Calculate current velocity based on recent position history.
        
        Args:
            window_size: Number of recent position records to consider
            
        Returns:
            Tuple of velocity components (vx, vy, vz) in m/s
        """
        if len(self.position_history) < 2:
            return (0.0, 0.0, 0.0)
        
        # Get the most recent positions
        recent = self.position_history[-window_size:]
        
        # Calculate velocity
        p1 = recent[0].position
        t1 = recent[0].timestamp
        p2 = recent[-1].position
        t2 = recent[-1].timestamp
        
        # Avoid division by zero
        if t2 == t1:
            return (0.0, 0.0, 0.0)
        
        # Calculate velocity components
        dt = t2 - t1
        vx = (p2[0] - p1[0]) / dt
        vy = (p2[1] - p1[1]) / dt
        vz = (p2[2] - p1[2]) / dt
        
        return (vx, vy, vz)
    
    def to_json(self) -> Dict:
        """
        Convert pallet to JSON-serializable dict.
        
        Returns:
            Dictionary representation of the pallet
        """
        return {
            "pallet_id": self.pallet_id,
            "position": self.position,
            "dimensions": self.dimensions,
            "content_type": self.content_type,
            "weight": self.weight,
            "tag_ids": self.tag_ids,
            # Only include the latest 10 positions to keep the size reasonable
            "position_history": [
                {"position": r.position, "timestamp": r.timestamp}
                for r in self.position_history[-10:]
            ]
        }
    
    @classmethod
    def from_json(cls, data: Dict) -> 'VirtualPallet':
        """
        Create pallet from JSON dict.
        
        Args:
            data: Dictionary with pallet data
            
        Returns:
            VirtualPallet instance
        """
        pallet = cls(
            pallet_id=data["pallet_id"],
            position=tuple(data["position"]),
            dimensions=tuple(data["dimensions"]),
            content_type=data["content_type"],
            weight=data["weight"]
        )
        
        # Restore tags
        for tag_id in data["tag_ids"]:
            pallet.attach_tag(tag_id)
        
        # Restore position history if available
        if "position_history" in data:
            pallet.position_history = [
                PositionRecord(
                    position=tuple(entry["position"]),
                    timestamp=entry["timestamp"]
                )
                for entry in data["position_history"]
            ]
        
        return pallet
