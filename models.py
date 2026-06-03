from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String, unique=True, index=True, nullable=False)
    vehicle_name = Column(String, nullable=False)
    current_odometer = Column(Float, default=0.0)
    
    # Statutory Compliance Fields
    insurance_expiry = Column(DateTime, nullable=True)
    rc_expiry = Column(DateTime, nullable=True)
    fitness_expiry = Column(DateTime, nullable=True)
    service_due_km = Column(Float, nullable=True)


class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    vehicle_plate = Column(String, ForeignKey("vehicles.plate_number"), nullable=False)
    
    # Driver tracking states
    assigned_driver = Column(String, nullable=False)       # Set by Owner on dispatch
    completed_by_driver = Column(String, nullable=True)     # Logged by the operating driver at wrap-up
    
    # Passenger and Routing parameters
    customer_name = Column(String, nullable=False)
    customer_phone = Column(String, nullable=False)
    from_location = Column(String, nullable=False)
    to_location = Column(String, nullable=False)
    
    # Odometer and Range Logistics Metrics
    start_km = Column(Float, nullable=False)
    end_km = Column(Float, nullable=True)
    
    # Ledger Accounting Breakdown Fields
    total_fare = Column(Float, default=0.0)                 # Fixed deal price agreed with client
    amount_received = Column(Float, default=0.0)            # Money collected so far
    balance_due = Column(Float, default=0.0)                # Remaining balance outstanding
    
    # Operational expense outlays
    diesel_cost = Column(Float, default=0.0)
    diesel_litres = Column(Float, default=0.0)
    toll_cost = Column(Float, default=0.0)
    driver_commission = Column(Float, default=0.0)
    other_expenses = Column(Float, default=0.0)
    expense_note = Column(String, nullable=True)            # Reason notes for other expenses
    
    # Internal status controls
    status = Column(String, default="Active")               # "Active" or "Completed"
    payment_status = Column(String, default="Pending")     # "Pending", "Partial", or "Paid"

    # Hybrid Data Properties for Automated Calculations
    @property
    def distance_travelled(self) -> float:
        if self.end_km and self.start_km:
            return max(0.0, self.end_km - self.start_km)
        return 0.0

    @property
    def mileage(self) -> float:
        distance = self.distance_travelled
        if distance > 0 and self.diesel_litres and self.diesel_litres > 0:
            return distance / self.diesel_litres
        return 0.0
