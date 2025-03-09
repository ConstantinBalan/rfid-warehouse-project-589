#!/usr/bin/env python3
"""
Trilateration Module

This module implements 3D trilateration algorithms to determine the position
of an object using distance measurements from fixed UWB sensors.
"""

import numpy as np
from typing import List, Tuple, Dict, Optional
import logging
from scipy.optimize import minimize

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('trilateration')

class Trilateration:
    """Implementation of 3D trilateration algorithms for UWB positioning."""
    
    def __init__(self, anchor_positions: List[Tuple[float, float, float]]):
        """
        Initialize trilateration with anchor positions.
        
        Args:
            anchor_positions: List of (x, y, z) coordinates for fixed anchor points
        """
        if len(anchor_positions) < 4:
            raise ValueError("At least 4 anchor positions are required for 3D trilateration")
        
        self.anchor_positions = np.array(anchor_positions)
        self.num_anchors = len(anchor_positions)
        logger.info(f"Trilateration initialized with {self.num_anchors} anchors")
    
    def linear_least_squares(self, distances: List[float]) -> Optional[Tuple[float, float, float]]:
        """
        Linear least squares algorithm for trilateration.
        
        Args:
            distances: List of distances from each anchor to the target
            
        Returns:
            (x, y, z) coordinates of the target, or None if calculation fails
        """
        if len(distances) != self.num_anchors:
            logger.error(f"Expected {self.num_anchors} distances, got {len(distances)}")
            return None
        
        try:
            # Create matrix A and vector b for the system of equations
            A = np.zeros((self.num_anchors - 1, 3))
            b = np.zeros(self.num_anchors - 1)
            
            # Reference anchor (first anchor)
            x0, y0, z0 = self.anchor_positions[0]
            r0 = distances[0]
            
            for i in range(1, self.num_anchors):
                xi, yi, zi = self.anchor_positions[i]
                ri = distances[i]
                
                # Fill matrix A and vector b
                A[i-1, 0] = 2 * (xi - x0)
                A[i-1, 1] = 2 * (yi - y0)
                A[i-1, 2] = 2 * (zi - z0)
                
                b[i-1] = (ri**2 - r0**2) - (xi**2 - x0**2) - (yi**2 - y0**2) - (zi**2 - z0**2)
            
            # Solve the system using least squares
            x, residuals, rank, s = np.linalg.lstsq(A, b, rcond=None)
            
            logger.debug(f"Calculated position: {x}, residuals: {residuals}")
            
            # Return the calculated position
            return tuple(x)
        
        except Exception as e:
            logger.error(f"Linear least squares trilateration failed: {e}")
            return None
    
    def nonlinear_optimization(self, distances: List[float], initial_guess: Tuple[float, float, float] = None) -> Optional[Tuple[float, float, float]]:
        """
        Nonlinear optimization approach for trilateration.
        
        Args:
            distances: List of distances from each anchor to the target
            initial_guess: Initial position estimate (x, y, z)
            
        Returns:
            (x, y, z) coordinates of the target, or None if optimization fails
        """
        if len(distances) != self.num_anchors:
            logger.error(f"Expected {self.num_anchors} distances, got {len(distances)}")
            return None
        
        if initial_guess is None:
            # Use centroid of anchors as initial guess
            initial_guess = tuple(np.mean(self.anchor_positions, axis=0))
        
        try:
            # Define objective function to minimize (sum of squared errors)
            def objective(point):
                point = np.array(point)
                error_sum = 0
                
                for i in range(self.num_anchors):
                    anchor = self.anchor_positions[i]
                    measured_dist = distances[i]
                    
                    # Calculate Euclidean distance
                    calc_dist = np.linalg.norm(point - anchor)
                    
                    # Squared error
                    error = (calc_dist - measured_dist) ** 2
                    error_sum += error
                
                return error_sum
            
            # Run optimization
            result = minimize(objective, initial_guess, method='L-BFGS-B')
            
            if result.success:
                logger.debug(f"Optimization successful: {result.x}, error: {result.fun}")
                return tuple(result.x)
            else:
                logger.warning(f"Optimization failed: {result.message}")
                return None
        
        except Exception as e:
            logger.error(f"Nonlinear optimization trilateration failed: {e}")
            return None
    
    def multilateral_algorithm(self, distances: List[float]) -> Optional[Tuple[float, float, float]]:
        """
        Multilateral algorithm for trilateration, combining multiple approaches.
        
        Args:
            distances: List of distances from each anchor to the target
            
        Returns:
            (x, y, z) coordinates of the target, or None if all methods fail
        """
        # First try linear least squares
        lls_result = self.linear_least_squares(distances)
        
        # Then try nonlinear optimization with the LLS result as initial guess
        if lls_result is not None:
            opt_result = self.nonlinear_optimization(distances, lls_result)
            if opt_result is not None:
                return opt_result
        
        # If LLS failed, try optimization with default initial guess
        return self.nonlinear_optimization(distances)
    
    def estimate_position(self, distances: List[float], method: str = 'multi') -> Optional[Tuple[float, float, float]]:
        """
        Estimate position using the specified method.
        
        Args:
            distances: List of distances from each anchor to the target
            method: Trilateration method ('lls', 'nonlinear', or 'multi')
            
        Returns:
            (x, y, z) coordinates of the target, or None if calculation fails
        """
        if method == 'lls':
            return self.linear_least_squares(distances)
        elif method == 'nonlinear':
            return self.nonlinear_optimization(distances)
        elif method == 'multi':
            return self.multilateral_algorithm(distances)
        else:
            logger.error(f"Unknown trilateration method: {method}")
            return None
    
    def calculate_position_error(self, true_position: Tuple[float, float, float], 
                                 estimated_position: Tuple[float, float, float]) -> float:
        """
        Calculate the error between true and estimated positions.
        
        Args:
            true_position: True (x, y, z) coordinates
            estimated_position: Estimated (x, y, z) coordinates
            
        Returns:
            Euclidean distance error in meters
        """
        true_pos = np.array(true_position)
        est_pos = np.array(estimated_position)
        return np.linalg.norm(true_pos - est_pos)


# Example usage
if __name__ == "__main__":
    # Define anchor positions (4 corners of a room)
    anchors = [
        (0.0, 0.0, 2.5),    # Corner 1
        (5.0, 0.0, 2.5),    # Corner 2
        (5.0, 5.0, 2.5),    # Corner 3
        (0.0, 5.0, 2.5)     # Corner 4
    ]
    
    # Create trilateration object
    trilat = Trilateration(anchors)
    
    # Simulate true position and distances
    true_pos = (2.5, 2.5, 1.0)
    
    # Calculate true distances and add noise
    distances = []
    for anchor in anchors:
        true_dist = np.linalg.norm(np.array(anchor) - np.array(true_pos))
        noise = np.random.normal(0, 0.1)  # 10cm noise
        distances.append(true_dist + noise)
    
    # Estimate position using different methods
    lls_pos = trilat.estimate_position(distances, method='lls')
    nl_pos = trilat.estimate_position(distances, method='nonlinear')
    multi_pos = trilat.estimate_position(distances, method='multi')
    
    # Print results
    print(f"True position: {true_pos}")
    print(f"LLS estimate: {lls_pos}, error: {trilat.calculate_position_error(true_pos, lls_pos):.3f}m")
    print(f"Nonlinear estimate: {nl_pos}, error: {trilat.calculate_position_error(true_pos, nl_pos):.3f}m")
    print(f"Multilateral estimate: {multi_pos}, error: {trilat.calculate_position_error(true_pos, multi_pos):.3f}m")
