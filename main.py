from fastapi import FastAPI, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session
import uvicorn
import io
from datetime import datetime

# Import graph-making modules safely
import matplotlib
matplotlib.use('Agg')  # Prevents background windows from popping up on your PC
import matplotlib.pyplot as plt

import models
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="TravelOS_Beta")

@app.on_event("startup")
def setup_default_vehicle():
    db = next(get_db())
    if not db.query(models.Vehicle).first():
        etios = models.Vehicle(
            name="Toyota Etios",
            plate_number="AP-16-TV-1234",
            current_odometer=125430.0,
            last_oil_change=125000.0
        )
        db.add(etios)
        db.commit()

def get_base_layout(content: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TravelOS Beta</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
        <style>
            body {{ background-color: #f8f9fa; }}
            .sidebar {{ min-height: 100vh; background-color: #212529; color: white; }}
            .sidebar a {{ color: rgba(255,255,255,0.75); text-decoration: none; }}
            .sidebar a:hover, .sidebar a.active {{ color: white; background-color: rgba(255,255,255,0.1); }}
            .card-counter {{ border-left: 5px solid; }}
        </style>
    </head>
    <body>
        <div class="container-fluid">
            <div class="row">
                <div class="col-md-3 col-lg-2 sidebar p-3 d-none d-md-block">
                    <h4 class="text-warning mb-4"><i class="bi bi-car-front-fill"></i> TravelOS</h4>
                    <hr>
                    <ul class="nav flex-column gap-2">
                        <li class="nav-item"><a href="/dashboard" class="nav-link p-2 rounded active"><i class="bi bi-speedometer2 me-2"></i> Owner Dashboard</a></li>
                        <li class="nav-item"><a href="/driver-portal" class="nav-link p-2 rounded"><i class="bi bi-person-badge me-2"></i> Driver Portal (Ravi)</a></li>
                        <li class="nav-item"><a href="/logout" class="nav-link p-2 rounded text-danger"><i class="bi bi-box-arrow-left me-2"></i> Logout</a></li>
                    </ul>
                </div>
                <div class="col-md-9 col-lg-10 ms-sm-auto p-4">
                    {content}
                </div>
            </div>
        </div>
    </body>
    </html>
    """

# --- ROUTE TO DELIVER THE GRAPH IMAGE ON-THE-FLY ---
@app.get("/analytics-chart.png")
def get_analytics_chart(db: Session = Depends(get_db)):
    trips = db.query(models.Trip).filter(models.Trip.status == "Completed").all()
    
    # Initialize dictionary structure for data tracking
    monthly_data = {}
    
    for t in trips:
        # Format dates nicely (e.g., "Jun 2026")
        month_str = t.created_at.strftime("%b %Y") if t.created_at else datetime.utcnow().strftime("%b %Y")
        
        if month_str not in monthly_data:
            monthly_data[month_str] = {"revenue": 0.0, "expenses": 0.0, "trips": 0}
            
        trip_expenses = t.diesel_cost + t.toll_cost + t.driver_commission + t.other_expenses
        monthly_data[month_str]["revenue"] += t.total_fare
        monthly_data[month_str]["expenses"] += trip_expenses
        monthly_data[month_str]["trips"] += 1

    # Default placeholder view if database has no completed entries yet
    if not monthly_data:
        current_month = datetime.utcnow().strftime("%b %Y")
        monthly_data[current_month] = {"revenue": 0.0, "expenses": 0.0, "trips": 0}

    months = list(monthly_data.keys())
    revenues = [monthly_data[m]["revenue"] for m in months]
    expenses = [monthly_data[m]["expenses"] for m in months]

    # Generate visual figure graph plot
    fig, ax1 = plt.subplots(figsize=(8, 4))
    
    width = 0.35
    x = range(len(months))
    
    # Draw bars side-by-side
    ax1.bar([i - width/2 for i in x], revenues, width, label='Revenue (₹)', color='#0d6efd')
    ax1.bar([i + width/2 for i in x], expenses, width, label='Expenses (₹)', color='#dc3545')
    
    ax1.set_xlabel('Months', fw='bold')
    ax1.set_ylabel('Amount in Rupees (₹)', fw='bold')
    ax1.set_title('Monthly Financial Business Analytics', fontsize=14, fw='bold', pad=15)
    ax1.set_xticks(x)
    ax1.set_xticklabels(months)
    ax1.legend(loc='upper left')
    ax1.grid(True, linestyle='--', alpha=0.5)
    
    plt.tight_layout()
    
    # Store image securely in local memory stream to transmit back
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150)
    buf.seek(0)
    plt.close(fig)
    
    return Response(content=buf.getvalue(), media_type="image/png")

@app.get("/")
def home():
    return RedirectResponse(url="/dashboard")

@app.get("/dashboard", response_class=HTMLResponse)
def owner_dashboard(db: Session = Depends(get_db)):
    vehicle = db.query(models.Vehicle).first()
    trips = db.query(models.Trip).order_by(models.Trip.id.desc()).all()
    
    revenue = 0.0
    expenses = 0.0
    profit = 0.0
    total_litres = 0.0
    total_km_for_mileage = 0.0
    
    trip_rows = ""
    for t in trips:
        revenue += t.total_fare
        trip_expenses = t.diesel_cost + t.toll_cost + t.driver_commission + t.other_expenses
        
        status_badge = '<span class="badge bg-warning text-dark">Running</span>' if t.status == "Active" else '<span class="badge bg-success">Completed</span>'
        distance_str = f"{t.end_km - t.start_km:.1f} km" if t.end_km else "--"
        
        if t.status == "Completed":
            expenses += trip_expenses
            net_trip_profit = t.total_fare - trip_expenses
            profit += net_trip_profit
            profit_str = f"₹{net_trip_profit:.2f}"
            profit_class = "text-success" if net_trip_profit > 0 else "text-danger"
            
            distance = (t.end_km - t.start_km) if t.end_km else 0
            if distance > 0 and t.diesel_litres > 0:
                total_km_for_mileage += distance
                total_litres += t.diesel_litres
        else:
            profit_str = "Running..."
            profit_class = "text-muted"

        trip_rows += f"""
        <tr>
            <td>
                <strong>{t.customer_name}</strong> <span class="text-muted small">({t.customer_phone or 'No Phone'})</span><br>
                <span class="badge bg-light text-dark"><i class="bi bi-geo-alt-fill text-danger"></i> From: {t.from_location or '--'}</span> → 
                <span class="badge bg-light text-dark">To: {t.to_location or '--'}</span><br>
                <small class="text-secondary">Pickup: {t.pickup_location or '--'}</small>
            </td>
            <td>{status_badge}</td>
            <td>{distance_str}</td>
            <td class="text-primary fw-bold">₹{t.total_fare:.2f}</td>
            <td class="text-danger">₹{trip_expenses:.2f}</td>
            <td>₹{t.driver_commission:.2f}</td>
            <td class="fw-bold {profit_class}">{profit_str}</td>
        </tr>
        """
    
    if not trip_rows:
        trip_rows = '<tr><td colspan="7" class="text-center py-4 text-muted">No trips recorded yet. Set your first trip above!</td></tr>'

    mileage = (total_km_for_mileage / total_litres) if total_litres > 0 else 16.5
    service_due = 10000 - (vehicle.current_odometer - vehicle.last_oil_change)
    
    if service_due <= 1000:
        alert_html = f'<div class="alert alert-danger m-0 py-2 mb-3"><i class="bi bi-exclamation-triangle-fill"></i> <strong>Oil Change Critical!</strong> Due in {service_due:.1f} km</div>'
    else:
        alert_html = f'<div class="alert alert-success m-0 py-2 mb-3"><i class="bi bi-check-circle-fill"></i> Oil Change healthy (Due in {service_due:.1f} km)</div>'

    dashboard_content = f"""
    <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
        <h2>Venkataramana Car Travels — Dashboard</h2>
        <span class="badge bg-dark p-2">Vehicle: Toyota Etios</span>
    </div>

    <div class="row g-3 mb-4">
        <div class="col-md-3"><div class="card bg-white shadow-sm p-3 card-counter border-primary"><small class="text-muted text-uppercase fw-bold">Total Revenue</small><h3 class="text-primary">₹{revenue:.2f}</h3></div></div>
        <div class="col-md-3"><div class="card bg-white shadow-sm p-3 card-counter border-success"><small class="text-muted text-uppercase fw-bold">Net Profit</small><h3 class="text-success">₹{profit:.2f}</h3></div></div>
        <div class="col-md-3"><div class="card bg-white shadow-sm p-3 card-counter border-danger"><small class="text-muted text-uppercase fw-bold">Total Expenses</small><h3 class="text-danger">₹{expenses:.2f}</h3></div></div>
        <div class="col-md-3"><div class="card bg-white shadow-sm p-3 card-counter border-warning"><small class="text-muted text-uppercase fw-bold">Fleet Mileage</small><h3 class="text-warning">{mileage:.2f} km/l</h3></div></div>
    </div>

    <div class="card shadow-sm mb-4">
        <div class="card-header bg-white fw-bold py-3"><i class="bi bi-bar-chart-line-fill text-primary"></i> Live Monthly Performance Trends Graph</div>
        <div class="card-body text-center bg-white">
            <img src="/analytics-chart.png" class="img-fluid rounded border shadow-sm" alt="Performance Graph" style="max-height: 400px; width:100%; object-fit: contain;">
        </div>
    </div>

    <div class="row g-4 mb-4">
        <div class="col-md-4">
            <div class="card shadow-sm h-100">
                <div class="card-header bg-dark text-white fw-bold">🚗 Vehicle Health Status</div>
                <div class="card-body">
                    <p><strong>Current Odometer:</strong> {vehicle.current_odometer:.1f} km</p>
                    <p><strong>Last Oil Change:</strong> {vehicle.last_oil_change:.1f} km</p>
                    <hr>
                    {alert_html}
                    
                    <form action="/reset-oil" method="POST">
                        <button type="submit" class="btn btn-sm btn-outline-dark w-100"><i class="bi bi-wrench"></i> Log Fresh Oil Change Today</button>
                    </form>
                </div>
            </div>
        </div>
        
        <div class="col-md-8">
            <div class="card shadow-sm h-100">
                <div class="card-header bg-primary text-white fw-bold">📋 Dispatch New Booking</div>
                <div class="card-body">
                    <form action="/create-trip" method="POST" class="row g-3">
                        <div class="col-md-6"><label class="form-label">Customer Name</label><input type="text" name="customer_name" class="form-control" placeholder="e.g. Ram" required></div>
                        <div class="col-md-6"><label class="form-label">Customer Phone Number</label><input type="text" name="customer_phone" class="form-control" placeholder="e.g. 9848022345" required></div>
                        
                        <div class="col-md-6"><label class="form-label">From (Source)</label><input type="text" name="from_location" class="form-control" placeholder="e.g. Hyderabad" required></div>
                        <div class="col-md-6"><label class="form-label">To (Destination)</label><input type="text" name="to_location" class="form-control" placeholder="e.g. Vijayawada" required></div>
                        
                        <div class="col-md-12"><label class="form-label">Exact Pickup Location address</label><input type="text" name="pickup_location" class="form-control" placeholder="e.g. Secunderabad Railway Station" required></div>
                        
                        <div class="col-md-6"><label class="form-label">Start Odometer Auto-Locked At</label><input type="text" class="form-control bg-light" value="{vehicle.current_odometer:.1f} km" readonly></div>
                        <div class="col-md-6"><label class="form-label">Agreed Fare (₹)</label><input type="number" step="0.1" name="total_fare" class="form-control" placeholder="e.g. 8000" required></div>
                        
                        <div class="col-12 mt-3"><button type="submit" class="btn btn-primary w-100">Send Assignment to Ravi's Mobile</button></div>
                    </form>
                </div>
            </div>
        </div>
    </div>

    <div class="card shadow-sm">
        <div class="card-header bg-white fw-bold py-3">📊 Trip History & Ledger Logs</div>
        <div class="table-responsive">
            <table class="table table-hover align-middle mb-0">
                <thead class="table-light">
                    <tr><th>Customer / Route / Details</th><th>Status</th><th>Distance</th><th>Fare</th><th>Expenses</th><th>Driver Comm.</th><th>Net Profit</th></tr>
                </thead>
                <tbody>{trip_rows}</tbody>
            </table>
        </div>
    </div>
    """
    return get_base_layout(dashboard_content)

@app.post("/create-trip")
def create_trip(
    customer_name: str = Form(...),
    customer_phone: str = Form(...),
    from_location: str = Form(...),
    to_location: str = Form(...),
    pickup_location: str = Form(...),
    total_fare: float = Form(...),
    db: Session = Depends(get_db)
):
    vehicle = db.query(models.Vehicle).first()
    start_km = vehicle.current_odometer if vehicle else 125430.0
    
    new_trip = models.Trip(
        customer_name=customer_name, 
        customer_phone=customer_phone,
        from_location=from_location,
        to_location=to_location,
        pickup_location=pickup_location,
        start_km=start_km, 
        total_fare=total_fare, 
        status="Active"
    )
    db.add(new_trip)
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)

@app.post("/reset-oil")
def reset_oil(db: Session = Depends(get_db)):
    vehicle = db.query(models.Vehicle).first()
    if vehicle:
        vehicle.last_oil_change = vehicle.current_odometer
        db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)

@app.get("/driver-portal", response_class=HTMLResponse)
def driver_portal(db: Session = Depends(get_db)):
    active_trips = db.query(models.Trip).filter(models.Trip.status == "Active").all()
    
    active_cards = ""
    for trip in active_trips:
        active_cards += f"""
        <div class="card shadow border-warning mb-4">
            <div class="card-header bg-warning text-dark fw-bold fs-5">
                🚀 Live Assignment Ready
            </div>
            <div class="card-body bg-white">
                <div class="bg-light p-3 rounded mb-3 border">
                    <p class="mb-1 fs-5"><strong>Passenger:</strong> {trip.customer_name}</p>
                    <p class="mb-2 fs-5"><strong>Phone:</strong> <a href="tel:{trip.customer_phone}" class="btn btn-sm btn-primary py-1 px-2"><i class="bi bi-telephone-fill"></i> Call {trip.customer_phone}</a></p>
                    <hr class="my-2">
                    <p class="mb-1"><strong>From:</strong> <span class="badge bg-dark">{trip.from_location}</span></p>
                    <p class="mb-1"><strong>To:</strong> <span class="badge bg-dark">{trip.to_location}</span></p>
                    <p class="mb-0 text-danger mt-2"><strong>📍 Pickup Address:</strong><br><span class="fw-bold">{trip.pickup_location}</span></p>
                </div>
                
                <p class="mb-3 fs-6"><strong>Starting Odometer:</strong> <span class="badge bg-secondary fs-6">{trip.start_km:.1f} km</span></p>
                
                <h5 class="text-center my-3 text-success border-top pt-3">🏁 Closing Submission Form</h5>
                <form action="/complete-trip/{trip.id}" method="POST">
                    <div class="mb-3">
                        <label class="form-label fw-bold text-danger">ENTER FINAL ODOMETER READING (KM)</label>
                        <input type="number" step="0.1" name="end_km" class="form-control form-control-lg border-danger font-monospace text-center fs-2" placeholder="000000" required>
                    </div>
                    <div class="row g-2 mb-3">
                        <div class="col-6"><label class="form-label small fw-bold">Diesel Filled (Litres)</label><input type="number" step="0.01" name="diesel_litres" class="form-control" value="0"></div>
                        <div class="col-6"><label class="form-label small fw-bold">Diesel Cost (₹)</label><input type="number" step="0.1" name="diesel_cost" class="form-control" value="0"></div>
                    </div>
                    <div class="row g-2 mb-3">
                        <div class="col-6"><label class="form-label small fw-bold">Toll Charges (₹)</label><input type="number" step="0.1" name="toll_cost" class="form-control" value="0"></div>
                        <div class="col-6"><label class="form-label small fw-bold">Driver Commission (₹)</label><input type="number" step="0.1" name="driver_commission" class="form-control" value="0"></div>
                    </div>
                    <button type="submit" class="btn btn-success btn-lg w-100 py-3 mt-2 fw-bold fs-5">SAVE & SUBMIT TRIP</button>
                </form>
            </div>
        </div>
        """
        
    if not active_cards:
        active_cards = """
        <div class="text-center py-5 bg-white rounded shadow-sm border">
            <i class="bi bi-emoji-smile text-success" style="font-size: 3rem;"></i>
            <h5 class="mt-3">No active jobs assigned!</h5>
            <p class="text-muted px-3 small">When a trip is dispatched for the Toyota Etios, it will show up right here instantly for Ravi.</p>
        </div>
        """

    driver_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TravelOS - Driver Portal</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
    </head>
    <body class="bg-light">
        <nav class="navbar navbar-dark bg-dark"><div class="container-fluid"><span class="navbar-brand mb-0 h1"><i class="bi bi-person-circle"></i> Driver App: Ravi</span><a href="/dashboard" class="btn btn-outline-warning btn-sm">Switch to Owner View</a></div></nav>
        <div class="container p-3" style="max-width: 500px;">
            <h3 class="my-3 text-secondary">Active Assignments</h3>
            {active_cards}
        </div>
    </body>
    </html>
    """
    return driver_html

@app.post("/complete-trip/{trip_id}")
def complete_trip(
    trip_id: int,
    end_km: float = Form(...),
    diesel_litres: float = Form(0.0),
    diesel_cost: float = Form(0.0),
    toll_cost: float = Form(0.0),
    driver_commission: float = Form(0.0),
    db: Session = Depends(get_db)
):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if trip:
        trip.end_km = end_km
        trip.diesel_litres = diesel_litres
        trip.diesel_cost = diesel_cost
        trip.toll_cost = toll_cost
        trip.driver_commission = driver_commission
        trip.status = "Completed"
        
        vehicle = db.query(models.Vehicle).first()
        if vehicle and end_km > vehicle.current_odometer:
            vehicle.current_odometer = end_km
        db.commit()
        
    return RedirectResponse(url="/driver-portal", status_code=303)

@app.get("/logout")
def logout():
    return RedirectResponse(url="/dashboard")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)