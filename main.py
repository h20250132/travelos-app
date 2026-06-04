import io
import csv
from datetime import datetime, date, timedelta
from fastapi import FastAPI, Depends, Request, Form, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

import models
from database import engine, SessionLocal

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="TravelOS Pro")

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
                current_odometer=125430.0,
                oil_change_km=125000.0,
                tyre_change_km=120000.0,
                last_service_date=date(2026, 5, 10),
                insurance_expiry=date(2027, 5, 10)
            )
        )
        db.commit()
    db.close()

# --- OWNER DASHBOARD ---
@app.get("/dashboard", response_class=HTMLResponse)
def owner_dashboard(request: Request, selected_date_str: str = None, db: Session = Depends(get_db)):
    today = date.today()
    if selected_date_str:
        try:
            view_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
        except:
            view_date = today
    else:
        view_date = today

    trips = db.query(models.Trip).order_by(models.Trip.created_at.desc()).all()
    vehicles = db.query(models.Vehicle).all()

    total_revenue = sum(t.total_fare for t in trips if t.status == "Completed")
    total_expenses = sum((t.diesel_cost + t.toll_cost + t.driver_bata + t.driver_commission + t.other_expenses) for t in trips if t.status == "Completed")
    net_profit = sum(t.net_profit for t in trips if t.status == "Completed")
    total_pending_balance = sum(t.balance_due for t in trips)

    # Outstanding customer collections list matching layout adjustments
    pending_trips = db.query(models.Trip).filter(models.Trip.balance_due > 0).all()
    pending_rows_html = "".join([
        f"<tr><td>{t.customer_name}</td><td class='text-danger fw-bold'>₹{t.balance_due:,.2f}</td><td>{t.vehicle_plate}</td></tr>" 
        for t in pending_trips
    ]) or "<tr><td colspan='3' class='text-muted text-center'>No outstanding balances</td></tr>"

    # Dynamic Odometer JS Mapping
    odo_mapping_js = "const odoMap = {" + ",".join([f"'{v.plate_number}': {v.current_odometer}" for v in vehicles]) + "};"

    vehicle_options = "".join([f'<option value="{v.plate_number}">{v.vehicle_name} ({v.plate_number})</option>' for v in vehicles])
    
    # Maintenance Panel List Markup
    maintenance_rows_html = "".join([
        f"""<tr>
            <td><b>{v.vehicle_name}</b><br><small class='text-muted'>{v.plate_number}</small></td>
            <td>{v.current_odometer:,.1f} KM</td>
            <td>{v.oil_change_km:,.1f} KM</td>
            <td>{v.tyre_change_km:,.1f} KM</td>
            <td>{v.last_service_date.strftime('%d-%b-%Y') if v.last_service_date else '-'}</td>
            <td><span class='badge bg-info'>{v.insurance_expiry.strftime('%d-%b-%Y') if v.insurance_expiry else '-'}</span></td>
        </tr>""" for v in vehicles
    ])

    # Calendar Core Processing Engine
    active_date_trips = db.query(models.Trip).filter(models.Trip.trip_date == view_date).all()
    
    calendar_fleet_html = ""
    for v in vehicles:
        matching_trip = next((t for t in active_date_trips if t.vehicle_plate == v.plate_number), None)
        if matching_trip:
            status_text = f"<span class='badge bg-danger'>On Trip ({matching_trip.from_location} ➔ {matching_trip.to_location})</span>"
        else:
            status_text = "<span class='badge bg-success'>Empty / Available</span>"
        calendar_fleet_html += f"<li class='list-group-item d-flex justify-content-between align-items-center'>{v.vehicle_name} ({v.plate_number}) {status_text}</li>"

    ravi_trips = [t for t in active_date_trips if t.assigned_driver.lower() == "ravi"]
    ravi_status = f"<span class='badge bg-danger'>On Duty ({ravi_trips[0].vehicle_plate})</span>" if ravi_trips else "<span class='badge bg-secondary'>Off Duty / Available</span>"

    # Trip logs loops containing complete dynamic modular breakdowns
    trip_logs_html = ""
    for t in trips:
        date_str = t.trip_date.strftime('%d-%b-%Y')
        status_badge = f'<span class="badge bg-warning text-dark">Running</span>' if t.status == "Active" else f'<span class="badge bg-success">Completed</span>'
        route_summary = f"{t.from_location} ➔ {t.to_location}"
        driver_name = t.assigned_driver if t.status == 'Active' else t.completed_by_driver
        
        profit_breakdown_html = f"""
            <div class='bg-white p-2 border rounded mt-2 small shadow-sm'>
                <div class='text-muted fw-bold border-bottom pb-1 mb-1 text-uppercase' style='font-size:10px;'>Trip Profit Breakdown</div>
                <div class='d-flex justify-content-between'><span>Customer Fare:</span><b>₹{t.total_fare:,.2f}</b></div>
                <div class='d-flex justify-content-between text-danger'><span>Diesel Expenses:</span><span>-₹{t.diesel_cost:,.2f}</span></div>
                <div class='d-flex justify-content-between text-danger'><span>Toll Charges:</span><span>-₹{t.toll_cost:,.2f}</span></div>
                <div class='d-flex justify-content-between text-danger'><span>Driver Bata:</span><span>-₹{t.driver_bata:,.2f}</span></div>
                <div class='d-flex justify-content-between text-danger'><span>Commission Paid:</span><span>-₹{t.driver_commission:,.2f}</span></div>
                <div class='d-flex justify-content-between text-danger'><span>Other Costs:</span><span>-₹{t.other_expenses:,.2f}</span></div>
                <div class='d-flex justify-content-between border-top pt-1 mt-1 text-success fw-bold'><span>Net Profit:</span><span>₹{t.net_profit:,.2f}</span></div>
            </div>
        """ if t.status == "Completed" else "<p class='text-muted small italic'>Breakdown processing upon trip completion.</p>"

        trip_logs_html += f"""
        <div class="accordion-item mb-2 shadow-sm border rounded">
            <h2 class="accordion-header" id="heading_{t.id}">
                <button class="accordion-button collapsed bg-white text-dark" type="button" data-bs-toggle="collapse" data-bs-target="#collapse_{t.id}">
                    <div class="d-flex align-items-center gap-3 w-100 flex-wrap text-start">
                        <span>📅 <b>{date_str}</b></span>
                        <span class="badge bg-secondary">{t.vehicle_plate}</span>
                        <span>👤 Driver: <b>{driver_name}</b></span>
                        <span class="text-muted text-truncate" style="max-width: 200px;">🛣️ {route_summary}</span>
                        <span class="ms-auto me-3 fw-bold text-dark">₹{t.total_fare}</span>
                        {status_badge}
                    </div>
                </button>
            </h2>
            <div id="collapse_{t.id}" class="accordion-collapse collapse" data-bs-parent="#tripHistoryAccordion">
                <div class="accordion-body bg-light text-dark">
                    <div class="row g-3">
                        <div class="col-md-4">
                            <h6><b>Customer Information</b></h6>
                            <p class="mb-1">Name: {t.customer_name}</p>
                            <p class="mb-1">Phone: {t.customer_phone}</p>
                        </div>
                        <div class="col-md-4">
                            <h6><b>Trip Parameters</b></h6>
                            <p class="mb-1">Odometer Logs: {t.start_km} KM ➔ {t.end_km if t.end_km else '-'} KM</p>
                            <p class="mb-1">Distance Count: {t.distance_travelled} KM</p>
                            {profit_breakdown_html}
                        </div>
                        <div class="col-md-4">
                            <h6><b>Collections & Management</b></h6>
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

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TravelOS Owner View</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            {odo_mapping_js}
            def updateOdometerDefault() {{
                const selectedPlate = document.getElementById('vehicle_select').value;
                if(odoMap[selectedPlate] !== undefined) {{
                    document.getElementById('start_km_input').value = odoMap[selectedPlate];
                }}
            }}
            window.onload = function() {{
                updateOdometerDefault();
            }};
        </script>
    </head>
    <body class="bg-light">
        <nav class="navbar navbar-dark bg-dark mb-4 shadow-sm">
            <div class="container-fluid justify-content-start gap-2">
                <a class="btn btn-sm btn-light active fw-bold" href="/dashboard">Owner Operations View</a>
                <a class="btn btn-sm btn-outline-warning" href="/driver-portal">Driver Entry View</a>
            </div>
        </nav>

        <div class="container pb-5">
            <h3 class="mb-4 fw-bold text-dark">🚖 Fleet Management Command</h3>
            
            <div class="row g-3 mb-4">
                <div class="col-6 col-md-3"><div class="card p-3 shadow-sm bg-white border-0 border-start border-primary border-4"><small class="text-muted text-uppercase fw-bold" style="font-size:11px;">Total Revenue</small><h4 class="text-primary fw-bold mt-1">₹{total_revenue:,.2f}</h4></div></div>
                <div class="col-6 col-md-3"><div class="card p-3 shadow-sm bg-white border-0 border-start border-danger border-4"><small class="text-muted text-uppercase fw-bold" style="font-size:11px;">Total Expenses</small><h4 class="text-danger fw-bold mt-1">₹{total_expenses:,.2f}</h4></div></div>
                <div class="col-6 col-md-3"><div class="card p-3 shadow-sm bg-success text-white border-0"><small class="text-uppercase fw-bold opacity-75" style="font-size:11px;">Net Profit</small><h4 class="fw-bold mt-1">₹{net_profit:,.2f}</h4></div></div>
                <div class="col-6 col-md-3"><div class="card p-3 shadow-sm bg-warning text-dark border-0"><small class="text-uppercase fw-bold opacity-75" style="font-size:11px;">Pending Balance</small><h4 class="fw-bold mt-1">₹{total_pending_balance:,.2f}</h4></div></div>
            </div>

            <div class="row g-4 mb-5">
                <div class="col-md-4">
                    <div class="card p-3 shadow-sm bg-white border-0 h-100">
                        <h6 class="fw-bold text-secondary mb-3">📋 Customer Balances Breakdown</h6>
                        <div class="table-responsive">
                            <table class="table table-sm table-hover align-middle small">
                                <thead class="table-light"><tr><th>Customer</th><th>Pending Due</th><th>Vehicle</th></tr></thead>
                                <tbody>{pending_rows_html}</tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <div class="col-md-8">
                    <div class="card p-3 shadow-sm bg-white border-0 h-100">
                        <h6 class="fw-bold text-secondary mb-2">📅 Car & Driver Calendar Track</h6>
                        <form method="GET" action="/dashboard" class="row g-2 align-items-center mb-3">
                            <div class="col-auto"><input type="date" name="selected_date_str" value="{view_date.strftime('%Y-%m-%d')}" class="form-control form-control-sm"></div>
                            <div class="col-auto"><button type="submit" class="btn btn-sm btn-dark">Query Date</button></div>
                        </form>
                        <div class="row">
                            <div class="col-md-6">
                                <small class="text-muted fw-bold d-block mb-2 text-uppercase">Fleet Allocations ({view_date.strftime('%d-%b')})</small>
                                <ul class="list-group list-group-flush small">{calendar_fleet_html}</ul>
                            </div>
                            <div class="col-md-6 border-start">
                                <small class="text-muted fw-bold d-block mb-2 text-uppercase">Driver Attendance Profile</small>
                                <div class="p-2 border rounded bg-light d-flex justify-content-between align-items-center small">
                                    <span><b>Driver Ravi</b> ({view_date.strftime('%d-%b')})</span>
                                    {ravi_status}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card p-4 shadow-sm mb-5 bg-white border-0 rounded-3">
                <h5 class="mb-3 text-dark fw-bold">Dispatch New Journey Instance</h5>
                <form action="/dashboard/add-trip" method="POST">
                    <div class="row g-3">
                        <div class="col-md-3">
                            <label class="form-label small fw-semibold">Target Vehicle</label>
                            <select id="vehicle_select" name="vehicle_plate" class="form-select" onchange="updateOdometerDefault()" required>
                                {vehicle_options}
                            </select>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label small fw-semibold">Driver Selection Matrix</label>
                            <div class="input-group">
                                <select class="form-select" onchange="document.getElementById('driver_input').value=this.value;">
                                    <option value="Ravi">Ravi</option>
                                    <option value="" selected>Manual Entry Override...</option>
                                </select>
                                <input type="text" id="driver_input" name="assigned_driver" class="form-control" placeholder="Driver Name" value="Ravi" required>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label small fw-semibold">Customer Reference Name</label>
                            <input type="text" name="customer_name" class="form-control" placeholder="Customer Name" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label small fw-semibold">Customer Contact Phone</label>
                            <input type="tel" name="customer_phone" class="form-control" placeholder="Phone Number" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label small fw-semibold">Editable Start Odometer (KM)</label>
                            <input type="number" step="0.1" id="start_km_input" name="start_km" class="form-control fw-bold text-primary" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label small fw-semibold">Origin Point Location</label>
                            <input type="text" name="from_location" class="form-control" placeholder="From" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label small fw-semibold">Destination Endpoint Location</label>
                            <input type="text" name="to_location" class="form-control" placeholder="To" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label small fw-semibold">Expected Fare Value (₹)</label>
                            <input type="number" step="0.01" name="total_fare" class="form-control" placeholder="Total Fare" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label small fw-semibold">Trip Operational Date</label>
                            <input type="date" name="trip_date" value="{today.strftime('%Y-%m-%d')}" class="form-control" required>
                        </div>
                    </div>
                    <button type="submit" class="btn btn-dark w-100 mt-4 py-2 fw-bold text-uppercase tracking-wider">DISPATCH OPERATIONAL JOURNEY</button>
                </form>
            </div>

            <div class="card p-4 shadow-sm mb-5 bg-white border-0 rounded-3">
                <h5 class="mb-3 text-dark fw-bold">🔧 Vehicle Maintenance Supervision Engine</h5>
                <div class="table-responsive">
                    <table class="table table-hover align-middle small">
                        <thead class="table-dark">
                            <tr>
                                <th>Vehicle Name</th>
                                <th>Current Odometer</th>
                                <th>Last Oil Change</th>
                                <th>Last Tyre Change</th>
                                <th>Last Bench Service</th>
                                <th>Insurance Expiry Boundary</th>
                            </tr>
                        </thead>
                        <tbody>{maintenance_rows_html}</tbody>
                    </table>
                </div>
            </div>

            <div class="card p-4 shadow-sm mb-5 bg-white border-0 rounded-3">
                <h5 class="mb-3 text-dark fw-bold">📊 Analytics Data Extraction Reports Panel</h5>
                <div class="row g-3">
                    <div class="col-md-6">
                        <div class="p-3 border rounded bg-light">
                            <h6>Daily Metric Tracking Loop</h6>
                            <form action="/dashboard/reports/download" method="GET" class="row g-2 align-items-center mt-2">
                                <div class="col-auto"><input type="date" name="start" value="{today.strftime('%Y-%m-%d')}" class="form-control form-control-sm"></div>
                                <div class="col-auto"><input type="hidden" name="end" value="{today.strftime('%Y-%m-%d')}"><button type="submit" class="btn btn-sm btn-primary">Download Daily Log CSV</button></div>
                            </form>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="p-3 border rounded bg-light">
                            <h6>Monthly Aggregated Operational Export</h6>
                            <form action="/dashboard/reports/download" method="GET" class="row g-2 align-items-center mt-2">
                                <div class="col-auto"><label class="small text-muted">Start Bounds:</label><input type="date" name="start" value="{ (today - timedelta(days=30)).strftime('%Y-%m-%d')}" class="form-control form-control-sm"></div>
                                <div class="col-auto"><label class="small text-muted">End Bounds:</label><input type="date" name="end" value="{today.strftime('%Y-%m-%d')}" class="form-control form-control-sm"></div>
                                <div class="col-auto mt-4"><button type="submit" class="btn btn-sm btn-success">Download Extended Range CSV</button></div>
                            </form>
                        </div>
                    </div>
                </div>
            </div>

            <h5 class="mb-3 text-dark fw-bold">📋 Trip Operational Logs Framework</h5>
            <div class="accordion" id="tripHistoryAccordion">{trip_logs_html}</div>
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
    trip_date: str = Form(...), db: Session = Depends(get_db)
):
    parsed_date = datetime.strptime(trip_date, "%Y-%m-%d").date()
    new_trip = models.Trip(
        vehicle_plate=vehicle_plate, assigned_driver=assigned_driver,
        customer_name=customer_name, customer_phone=customer_phone,
        start_km=start_km, from_location=from_location, to_location=to_location,
        total_fare=total_fare, balance_due=total_fare, payment_status="Pending", 
        status="Active", trip_date=parsed_date
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


@app.get("/dashboard/reports/download")
def export_excel_csv_reports(start: str, end: str, db: Session = Depends(get_db)):
    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    end_date = datetime.strptime(end, "%Y-%m-%d").date()
    
    trips = db.query(models.Trip).filter(models.Trip.trip_date >= start_date, models.Trip.trip_date <= end_date).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Trip ID", "Date", "Vehicle Plate", "Driver", "Customer Name", 
        "From", "To", "Distance Travelled", "Fare Amount", "Diesel Cost", 
        "Toll Cost", "Driver Bata", "Commission Paid", "Other Expenses", "Net Profit", "Balance Due"
    ])
    
    for t in trips:
        writer.writerow([
            t.id, t.trip_date.strftime('%Y-%m-%d'), t.vehicle_plate, t.assigned_driver, t.customer_name,
            t.from_location, t.to_location, t.distance_travelled, t.total_fare, t.diesel_cost,
            t.toll_cost, t.driver_bata, t.driver_commission, t.other_expenses, t.net_profit, t.balance_due
        ])
    
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=TravelOS_Report_{start}_to_{end}.csv"}
    )


# --- DRIVER FIELD PORTAL REDACTED SECURE VIEW ---
@app.get("/driver-portal", response_class=HTMLResponse)
def driver_portal(request: Request, db: Session = Depends(get_db)):
    active_trips = db.query(models.Trip).filter(models.Trip.status == "Active").all()
    
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TravelOS Driver Portal</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="bg-dark text-white">
        <nav class="navbar navbar-dark bg-secondary mb-4 shadow-sm">
            <div class="container-fluid justify-content-start gap-2">
                <a class="btn btn-sm btn-outline-light" href="/dashboard">Owner Management Log</a>
                <a class="btn btn-sm btn-warning active fw-bold" href="/driver-portal">Driver Interface Terminal</a>
            </div>
        </nav>

        <div class="container py-2">
            <div class="alert alert-info border-0 p-3 mb-4 bg-gradient text-dark">
                <strong>🔒 Secure Portal View Restricted:</strong> Revenue records, performance analytics profiles, ledger charts, and corporate asset summaries are restricted from view.
            </div>
            <h4 class="mb-4 text-warning fw-bold">Active Journeys Log Entry</h4>
    """
    
    if not active_trips:
        html_content += """
            <div class="alert alert-secondary text-center p-5 bg-transparent border-dashed">
                <p class="mb-0 text-muted">No active transport operations found.</p>
            </div>
        """
    else:
        for t in active_trips:
            html_content += f"""
            <div class="card bg-black text-white border-warning mb-4 shadow p-3">
                <div class="card-body">
                    <h5 class="card-title text-warning fw-bold">Vehicle Unit Plate: {t.vehicle_plate}</h5>
                    <p class="mb-1 opacity-75">Customer Profile: {t.customer_name} ({t.customer_phone})</p>
                    <p class="mb-1 opacity-75">Route Vectors: {t.from_location} to {t.to_location}</p>
                    <p class="mb-3 text-warning fs-6"><b>Initial Dispatch Odometer: {t.start_km:.1f} KM</b></p>
                    
                    <form action="/driver-portal/complete-trip/{t.id}" method="POST" class="p-3 border rounded bg-dark border-secondary">
                        <h6 class="text-warning border-bottom border-secondary pb-2 mb-3">Complete Terminal Operational Metric Sign-off</h6>
                        
                        <div class="mb-2">
                            <label class="form-label small text-white-50">Confirm Operating Driver Name</label>
                            <input type="text" name="completed_by_driver" class="form-control form-control-sm bg-secondary text-white border-0" value="{t.assigned_driver}" required>
                        </div>

                        <div class="mb-2">
                            <label class="form-label small text-warning fw-bold">Closing Terminal Odometer Verification (KM) *</label>
                            <input type="number" step="0.1" name="end_km" class="form-control form-control-sm bg-warning text-dark fw-bold" required min="{t.start_km + 0.1}">
                        </div>

                        <div class="row g-2 mb-2">
                            <div class="col-6">
                                <label class="form-label small text-white-50">Diesel Financial Cost (₹)</label>
                                <input type="number" step="0.01" name="diesel_cost" class="form-control form-control-sm" value="0">
                            </div>
                            <div class="col-6">
                                <label class="form-label small text-white-50">Fuel Intake Volume (Litres)</label>
                                <input type="number" step="0.01" name="diesel_litres" class="form-control form-control-sm" value="0">
                            </div>
                        </div>
                        <div class="row g-2 mb-3">
                            <div class="col-4">
                                <label class="form-label small text-white-50">Toll Expense (₹)</label>
                                <input type="number" step="0.01" name="toll_cost" class="form-control form-control-sm" value="0">
                            </div>
                            <div class="col-4">
                                <label class="form-label small text-white-50">Driver Daily Bata (₹)</label>
                                <input type="number" step="0.01" name="driver_bata" class="form-control form-control-sm" value="0">
                            </div>
                            <div class="col-4">
                                <label class="form-label small text-white-50">Driver Comm (₹)</label>
                                <input type="number" step="0.01" name="driver_commission" class="form-control form-control-sm" value="0">
                            </div>
                        </div>
                        <div class="mb-3">
                            <label class="form-label small text-white-50">Supplementary Ledger Costs</label>
                            <div class="input-group input-group-sm">
                                <input type="number" step="0.01" name="other_expenses" class="form-control" value="0" style="max-width:30%;">
                                <input type="text" name="expense_note" class="form-control" placeholder="Operational cost description notation">
                            </div>
                        </div>

                        <button type="submit" class="btn btn-warning btn-sm w-100 fw-bold text-uppercase py-2 text-dark">SAVE METRIC RECORD AND CLOSE JOURNEY INSTANCE</button>
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
    toll_cost: float = Form(0.0), driver_bata: float = Form(0.0), driver_commission: float = Form(0.0),
    other_expenses: float = Form(0.0), expense_note: str = Form(None),
    db: Session = Depends(get_db)
):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Target instance identifier matching error.")
        
    trip.completed_by_driver = completed_by_driver
    trip.end_km = end_km
    trip.diesel_cost = diesel_cost
    trip.diesel_litres = diesel_litres
    trip.toll_cost = toll_cost
    trip.driver_bata = driver_bata
    trip.driver_commission = driver_commission
    trip.other_expenses = other_expenses
    trip.expense_note = expense_note
    trip.status = "Completed"
    
    # Update the vehicle ledger's current global odometer position context
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.plate_number == trip.vehicle_plate).first()
    if vehicle and end_km > vehicle.current_odometer:
        vehicle.current_odometer = end_km

    db.commit()
    return RedirectResponse(url="/driver-portal", status_code=status.HTTP_303_SEE_OTHER)
