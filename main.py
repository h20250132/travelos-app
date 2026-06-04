import io
import os
from datetime import datetime, date, timedelta

from fastapi import FastAPI, Depends, Request, Form, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

import models
from database import engine, SessionLocal

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="TravelOS")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def configure_initial_fleet():
    db = SessionLocal()
    if db.query(models.Vehicle).count() == 0:
        db.add(
            models.Vehicle(
                plate_number="AP XX XX 8118", 
                vehicle_name="Toyota Etios", 
                current_odometer=125430.0
            )
        )
        db.commit()
    db.close()

# --- OWNER DASHBOARD ---
@app.get("/dashboard", response_class=HTMLResponse)
def owner_dashboard(request: Request, db: Session = Depends(get_db)):
    trips = db.query(models.Trip).order_by(models.Trip.created_at.desc()).all()
    vehicles = db.query(models.Vehicle).all()

    total_revenue = sum(t.total_fare for t in trips if t.status == "Completed")
    total_expenses = sum(t.diesel_cost + t.toll_cost + t.driver_commission + t.other_expenses for t in trips if t.status == "Completed")
    net_profit = total_revenue - total_expenses
    total_pending_balance = sum(t.balance_due for t in trips)

    vehicle_options = "".join([f'<option value="{v.plate_number}">{v.vehicle_name} ({v.plate_number})</option>' for v in vehicles])

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </head>
    <body class="bg-light">
        <nav class="navbar navbar-dark bg-dark mb-4">
            <div class="container-fluid justify-content-start gap-2">
                <a class="btn btn-sm btn-light active" href="/dashboard">Owner View</a>
                <a class="btn btn-sm btn-outline-warning" href="/driver-portal">Driver View</a>
            </div>
        </nav>

        <div class="container pb-4">
            <h3 class="mb-4 fw-bold">🚖 Fleet Management</h3>
            
            <!-- Simple Financial Summary Boxes -->
            <div class="row g-3 mb-4">
                <div class="col-6 col-md-3"><div class="card p-3 shadow-sm bg-white"><small class="text-muted">Total Revenue</small><h4 class="text-primary fw-bold">₹{total_revenue:,.2f}</h4></div></div>
                <div class="col-6 col-md-3"><div class="card p-3 shadow-sm bg-white"><small class="text-muted">Total Expenses</small><h4 class="text-danger fw-bold">₹{total_expenses:,.2f}</h4></div></div>
                <div class="col-6 col-md-3"><div class="card p-3 shadow-sm bg-success text-white"><small>Net Profit</small><h4 class="fw-bold">₹{net_profit:,.2f}</h4></div></div>
                <div class="col-6 col-md-3"><div class="card p-3 shadow-sm bg-warning text-dark"><small>Pending Balance</small><h4 class="fw-bold">₹{total_pending_balance:,.2f}</h4></div></div>
            </div>

            <!-- Booking Form Box -->
            <div class="card p-4 shadow-sm mb-4 bg-white">
                <h5 class="mb-3 text-secondary fw-bold">Dispatch New Trip</h5>
                <form action="/dashboard/add-trip" method="POST">
                    <div class="row g-3">
                        <div class="col-md-3">
                            <label class="form-label small fw-semibold">Vehicle</label>
                            <select name="vehicle_plate" class="form-select" required>
                                {vehicle_options}
                            </select>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label small fw-semibold">Driver Name</label>
                            <input type="text" name="assigned_driver" class="form-control" placeholder="Type Driver Name" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label small fw-semibold">Customer Name</label>
                            <input type="text" name="customer_name" class="form-control" placeholder="Customer Name" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label small fw-semibold">Customer Phone</label>
                            <input type="tel" name="customer_phone" class="form-control" placeholder="Phone Number" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label small fw-semibold">Starting Odometer (KM)</label>
                            <input type="number" step="0.1" name="start_km" class="form-control" placeholder="Start KM" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label small fw-semibold">From Location</label>
                            <input type="text" name="from_location" class="form-control" placeholder="From" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label small fw-semibold">To Location</label>
                            <input type="text" name="to_location" class="form-control" placeholder="To" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label small fw-semibold">Fare Amount (₹)</label>
                            <input type="number" step="0.01" name="total_fare" class="form-control" placeholder="Total Fare" required>
                        </div>
                    </div>
                    <button type="submit" class="btn btn-dark w-100 mt-3 py-2 fw-bold">DISPATCH TRIP</button>
                </form>
            </div>

            <!-- History Table Log -->
            <h5 class="mb-3 text-secondary fw-bold">Trip History Logs</h5>
            <div class="accordion" id="tripHistoryAccordion">
    """

    for index, t in enumerate(trips):
        date_str = t.created_at.strftime('%d-%b-%Y')
        status_badge = f'<span class="badge bg-warning text-dark">Running</span>' if t.status == "Active" else f'<span class="badge bg-success">Completed</span>'
        route_summary = f"{t.from_location} ➔ {t.to_location}"
        driver_name = t.assigned_driver if t.status == 'Active' else t.completed_by_driver

        html_content += f"""
                <div class="accordion-item mb-2 shadow-sm border rounded">
                    <h2 class="accordion-header" id="heading_{t.id}">
                        <button class="accordion-button collapsed bg-white text-dark" type="button" data-bs-toggle="collapse" data-bs-target="#collapse_{t.id}">
                            <div class="d-flex align-items-center gap-3 w-100 flex-wrap text-start">
                                <span>📅 <b>{date_str}</b></span>
                                <span class="badge bg-secondary">{t.vehicle_plate}</span>
                                <span>👤 Driver: <b>{driver_name}</b></span>
                                <span class="text-muted text-truncate" style="max-width: 200px;">🛣️ {route_summary}</span>
                                <span class="ms-auto me-3">₹{t.total_fare}</span>
                                {status_badge}
                            </div>
                        </button>
                    </h2>
                    <div id="collapse_{t.id}" class="accordion-collapse collapse" data-bs-parent="#tripHistoryAccordion">
                        <div class="accordion-body bg-light text-dark">
                            <div class="row g-3">
                                <div class="col-md-4">
                                    <h6><b>Customer Info</b></h6>
                                    <p class="mb-1">Name: {t.customer_name}</p>
                                    <p class="mb-1">Phone: {t.customer_phone}</p>
                                </div>
                                <div class="col-md-4">
                                    <h6><b>Trip Details</b></h6>
                                    <p class="mb-1">Odometer: {t.start_km} KM ➔ {t.end_km if t.end_km else '-'} KM</p>
                                    <p class="mb-1">Distance: {t.distance_travelled} KM</p>
                                </div>
                                <div class="col-md-4">
                                    <h6><b>Expenses & Payouts</b></h6>
                                    <p class="mb-1">Diesel: ₹{t.diesel_cost} | Tolls: ₹{t.toll_cost}</p>
                                    <p class="mb-1">Driver Commission: ₹{t.driver_commission}</p>
                                    <p class="mb-1 text-danger"><b>Remaining Balance Due: ₹{t.balance_due}</b></p>
                                    
                                    <form action="/dashboard/settle-payment/{t.id}" method="POST" class="d-flex gap-1 mt-2">
                                        <input type="number" step="0.01" class="form-control form-control-sm" name="amt" placeholder="Collect Cash Amount" required>
                                        <button type="submit" class="btn btn-sm btn-success">Collect</button>
                                    </form>
                                    <form action="/dashboard/delete-trip/{t.id}" method="POST" class="mt-2" onsubmit="return confirm('Delete permanently?');">
                                        <button type="submit" class="btn btn-sm btn-outline-danger w-100">🗑️ Delete Entry</button>
                                    </form>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
        """
        
    html_content += """
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.post("/dashboard/add-trip")
def process_new_dispatch(
    vehicle_plate: str = Form(...), assigned_driver: str = Form(...),
    customer_name: str = Form(...), customer_phone: str = Form(...),
    start_km: float = Form(...), from_location: str = Form(...),
    to_location: str = Form(...), total_fare: float = Form(...), 
    db: Session = Depends(get_db)
):
    new_trip = models.Trip(
        vehicle_plate=vehicle_plate, assigned_driver=assigned_driver,
        customer_name=customer_name, customer_phone=customer_phone,
        start_km=start_km, from_location=from_location, to_location=to_location,
        total_fare=total_fare, balance_due=total_fare, payment_status="Pending", status="Active"
    )
    db.add(new_trip)
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/dashboard/settle-payment/{trip_id}")
def reconcile_trip_payment(trip_id: int, amt: float = Form(...), db: Session = Depends(get_db)):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if trip:
        trip.amount_received += amt
        trip.balance_due = max(0.0, trip.total_fare - trip.amount_received)
        if trip.balance_due <= 0:
            trip.payment_status = "Paid"
        db.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/dashboard/delete-trip/{trip_id}")
def purge_trip_record(trip_id: int, db: Session = Depends(get_db)):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if trip:
        db.delete(trip)
        db.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


# --- FIELD DRIVER PORTAL ---
@app.get("/driver-portal", response_class=HTMLResponse)
def driver_portal(request: Request, db: Session = Depends(get_db)):
    active_trips = db.query(models.Trip).filter(models.Trip.status == "Active").all()
    
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Driver View</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="bg-dark text-white">
        <nav class="navbar navbar-dark bg-secondary mb-4">
            <div class="container-fluid justify-content-start gap-2">
                <a class="btn btn-sm btn-outline-light" href="/dashboard">Owner View</a>
                <a class="btn btn-sm btn-warning active fw-bold" href="/driver-portal">Driver View</a>
            </div>
        </nav>

        <div class="container py-2">
            <h4 class="mb-4 text-warning fw-bold">Active Journeys</h4>
    """
    
    if not active_trips:
        html_content += """
            <div class="alert alert-secondary text-center p-4 bg-transparent border">
                <p class="mb-0 text-muted">No active trips dispatched right now.</p>
            </div>
        """
    else:
        for t in active_trips:
            html_content += f"""
            <div class="card bg-black text-white border-warning mb-4 shadow-sm p-3">
                <div class="card-body">
                    <h5 class="card-title text-warning fw-bold">Vehicle: {t.vehicle_plate}</h5>
                    <p class="mb-1">Passenger: {t.customer_name} ({t.customer_phone})</p>
                    <p class="mb-1">Route: {t.from_location} to {t.to_location}</p>
                    <p class="mb-3 text-warning fs-6"><b>Starting Odometer: {t.start_km:.1f} KM</b></p>
                    
                    <form action="/driver-portal/complete-trip/{t.id}" method="POST" class="p-3 border rounded bg-dark">
                        <h6 class="text-warning border-bottom pb-1 mb-3">Complete Trip Metrics</h6>
                        
                        <div class="mb-2">
                            <label class="form-label small text-white-50">Confirm Driver Name</label>
                            <input type="text" name="completed_by_driver" class="form-control form-control-sm" value="{t.assigned_driver}" required>
                        </div>

                        <div class="mb-2">
                            <label class="form-label small text-warning fw-bold">Closing Odometer (KM) *</label>
                            <input type="number" step="0.1" name="end_km" class="form-control form-control-sm bg-warning text-dark fw-bold" required min="{t.start_km + 0.1}">
                        </div>

                        <div class="row g-2 mb-2">
                            <div class="col-6">
                                <label class="form-label small text-white-50">Diesel Cost (₹)</label>
                                <input type="number" step="0.01" name="diesel_cost" class="form-control form-control-sm" value="0">
                            </div>
                            <div class="col-6">
                                <label class="form-label small text-white-50">Fuel Litres</label>
                                <input type="number" step="0.01" name="diesel_litres" class="form-control form-control-sm" value="0">
                            </div>
                        </div>
                        <div class="row g-2 mb-3">
                            <div class="col-6">
                                <label class="form-label small text-white-50">Toll Expenses (₹)</label>
                                <input type="number" step="0.01" name="toll_cost" class="form-control form-control-sm" value="0">
                            </div>
                            <div class="col-6">
                                <label class="form-label small text-white-50">Driver Commission (₹)</label>
                                <input type="number" step="0.01" name="driver_commission" class="form-control form-control-sm" value="0">
                            </div>
                        </div>
                        <div class="mb-3">
                            <label class="form-label small text-white-50">Other Costs & Details</label>
                            <div class="input-group input-group-sm">
                                <input type="number" step="0.01" name="other_expenses" class="form-control" value="0" style="max-width:30%;">
                                <input type="text" name="expense_note" class="form-control" placeholder="Note why">
                            </div>
                        </div>

                        <button type="submit" class="btn btn-warning btn-sm w-100 fw-bold">SAVE AND CLOSE TRIP</button>
                    </form>
                </div>
            </div>
            """
            
    html_content += """
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.post("/driver-portal/complete-trip/{trip_id}")
def driver_complete_trip(
    trip_id: int, completed_by_driver: str = Form(...), end_km: float = Form(...),
    diesel_cost: float = Form(0.0), diesel_litres: float = Form(0.0),
    toll_cost: float = Form(0.0), driver_commission: float = Form(0.0),
    other_expenses: float = Form(0.0), expense_note: str = Form(None),
    db: Session = Depends(get_db)
):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip record missing.")
        
    trip.completed_by_driver = completed_by_driver
    trip.end_km = end_km
    trip.diesel_cost = diesel_cost
    trip.diesel_litres = diesel_litres
    trip.toll_cost = toll_cost
    trip.driver_commission = driver_commission
    trip.other_expenses = other_expenses
    trip.expense_note = expense_note
    trip.status = "Completed"
    
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.plate_number == trip.vehicle_plate).first()
    if vehicle and end_km > vehicle.current_odometer:
        vehicle.current_odometer = end_km

    db.commit()
    return RedirectResponse(url="/driver-portal", status_code=status.HTTP_303_SEE_OTHER)
