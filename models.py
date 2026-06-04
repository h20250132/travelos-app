from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from database import Base
from datetime import datetime

class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String, unique=True, index=True, nullable=False)
    vehicle_name = Column(String, nullable=False)
    current_odometer = Column(Float, default=0.0)

class Trip(Base):
    __tablename__ = "trips"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    vehicle_plate = Column(String, ForeignKey("vehicles.plate_number"), nullable=False)
    
    assigned_driver = Column(String, nullable=False)       
    completed_by_driver = Column(String, nullable=True)     
    
    customer_name = Column(String, nullable=False)
    customer_phone = Column(String, nullable=False)
    from_location = Column(String, nullable=False)
    to_location = Column(String, nullable=False)
    
    start_km = Column(Float, nullable=False)
    end_km = Column(Float, nullable=True)
    
    total_fare = Column(Float, default=0.0)                 
    amount_received = Column(Float, default=0.0)            
    balance_due = Column(Float, default=0.0)                
    
    diesel_cost = Column(Float, default=0.0)
    diesel_litres = Column(Float, default=0.0)
    toll_cost = Column(Float, default=0.0)
    driver_commission = Column(Float, default=0.0)
    other_expenses = Column(Float, default=0.0)
    expense_note = Column(String, nullable=True)            
    
    status = Column(String, default="Active")               
    payment_status = Column(String, default="Pending")     

    @property
    def distance_travelled(self) -> float:
        if self.end_km and self.start_km:
            return max(0.0, self.end_km - self.start_km)
        return 0.0
