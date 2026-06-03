import io
import os
from datetime import datetime, date, timedelta
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from fastapi import FastAPI, Depends, Request, Form, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

import models
from database import engine, SessionLocal

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="TravelOS Enterprise")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- OWNER MANAGEMENT DASHBOARD STARTUP CONTROLS ---
@app.on_event("startup")
def configure_initial_fleet():
    # 🌟 TEMPORARY LOGIC: This wipes the old conflicting SQLite file on bootup to resolve the 500 error
    if os.path.exists("travelos.db"):
        try:
            os.remove("travelos.db")
        except Exception:
            pass

    # Re-verify and initialize structural data models
    models.Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    if db.query(models.Vehicle).count() == 0:
        today = date.today()
        db.add_all([
            models.Vehicle(plate_number="AP39AB1234", vehicle_name="Toyota Etios", current_odometer=125430.0, insurance_expiry=today + timedelta(days=5), rc_expiry=today + timedelta(days=200), fitness_expiry=today + timedelta(days=90), service_due_km=130000.0),
            models.Vehicle(plate_number="AP39CD5678", vehicle_name="Maruti Swift", current_odometer=84200.0, insurance_expiry=today + timedelta(days=120), rc_expiry=today + timedelta(days=15), fitness_expiry=today + timedelta(days=4), service_due_km=85000.0),
            models.Vehicle(plate_number="AP39EF9999", vehicle_name="Innova Crysta", current_odometer=192000.0, insurance_expiry=today + timedelta(days=80), rc_expiry=today + timedelta(days=450), fitness_expiry=today + timedelta(days=180), service_due_km=193500.0)
        ])
        db.commit()
    db.close()


@app.get("/dashboard", response_class=HTMLResponse)
def owner_dashboard(request: Request, db: Session = Depends(get_db)):
    trips = db.query(models.Trip).order_by(models.Trip.created_at.desc()).all()
    vehicles = db.query(models.Vehicle).all()
    today_dt = date.today()

    # Compliance Tracking Alerts Setup
    maintenance_alerts = []
    for v in vehicles:
        if v.insurance_expiry and (v.insurance_expiry.date() - today_dt).days <= 7:
            maintenance_alerts.append(f"⚠️ <b>{v.plate_number}</b>: Insurance expires in {(v.insurance_expiry.date() - today_dt).days} days! (Due: {v.insurance_expiry.strftime('%d-%b')})")
        if v.fitness_expiry and (v.fitness_expiry.date() - today_dt).days <= 7:
            maintenance_alerts.append(f"🛑 <b>{v.plate_number}</b>: Fitness Certificate (FC) expires in {(v.fitness_expiry.date() - today_dt).days} days!")

    # Dynamic KPI Counters
    today_trips_count = sum(1 for t in trips if t.created_at.date() == today_dt)
    active_trips_count = sum(1 for t in trips if t.status == "Active")
    total_km_run = sum(t.distance_travelled for t in trips if t.status == "Completed")
    total_pending_payments = sum(t.balance_due for t in trips)

    # Audited Account Ledgers 
    total_revenue = sum(t.total_fare for t in trips if t.status == "Completed")
    total_diesel = sum(t.diesel_cost for t in trips if t.status == "Completed")
    total_tolls = sum(t.toll_cost for t in trips if t.status == "Completed")
    total_commissions = sum(t.driver_commission for t in trips if t.status == "Completed")
    total_other = sum(t.other_expenses for t in trips if t.status == "Completed")
    net_profit = total_revenue - (total_diesel + total_tolls + total_commissions + total_other)

    # Live Active Workforce State Monitors
    known_drivers = {"Ravi": "Available", "Kumar": "Available", "Srinivas": "Available"}
    driver_current_task = {"Ravi": "No active trip", "Kumar": "No active trip", "Srinivas": "No active trip"}
    
    for t in trips:
        if t.status == "Active" and t.assigned_driver in known_drivers:
            known_drivers[t.assigned_driver] = "On-Duty 🚖"
            driver_current_task[t.assigned_driver] = f"Driving {t.vehicle_plate} ({t.from_location} ➔ {t.to_location})"

    driver_status_html = ""
    for driver, status_state in known_drivers.items():
        badge_color = "bg-danger" if "On-Duty" in status_state else "bg-success"
        task_desc = driver_current_task[driver]
        driver_status_html += f"""
        <div class="col-md-4">
            <div class="p-3 rounded-3 bg-white shadow-sm border-start border-4 {'border-danger' if 'On-Duty' in status_state else 'border-success'}">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <h6 class="mb-0 fw-bold text-dark">👤 {driver}</h6>
                    <span class="badge {badge_color}">{status_state}</span>
                </div>
                <small class="text-muted d-block">{task_desc}</small>
            </div>
        </div>
        """

    alert_html = "".join([f'<div class="alert alert-danger py-2 mb-2">{a}</div>' for a in maintenance_alerts])
    vehicle_options = "".join([f'<option value="{v.plate_number}">{v.plate_number} ({v.vehicle_name})</option>' for v in vehicles])

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TravelOS Pro Fleet Manager</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <style>
            body {{ background-color: #f0f2f5; font-family: system-ui, -apple-system, sans-serif; }}
            .card-kpi {{ border-radius: 14px; border: none; box-shadow: 0 4px 12px rgba(0,0,0,0.04); color: white; }}
            .history-header-btn {{ border: none; background: transparent; width: 100%; text-align: left; padding: 1rem; display: flex; align-items: center; justify-content: space-between; text-decoration: none !important; }}
            .history-header-btn:focus {{ box-shadow: none; }}
            .accordion-item {{ border: 1px solid rgba(0,0,0,0.08); border-radius: 10px !important; margin-bottom: 10px; overflow: hidden; background-color: white; box-shadow: 0 2px 6px rgba(0,0,0,0.02); }}
            .badge-active-run {{ background-color: #fff3cd; color: #856404; font-weight: bold; }}
            .badge-completed-run {{ background-color: #d4edda; color: #155724; font-weight: bold; }}
            .badge-pending-pay-run {{ background-color: #f8d7da; color: #721c24; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="container-fluid py-4 px-md-5">
            <h2 class="mb-4 text-dark fw-bold">🚖 Venkataramana Travels ERP Suite</h2>
            
            {alert_html if maintenance_alerts else ''}

            <h5 class="text-secondary fw-bold mb-3">🤵 Real-Time Driver Login & Operational Status</h5>
            <div class="row g-3 mb-4">
                {driver_status_html}
            </div>

            <div class="row g-3 mb-4">
                <div class="col-6 col-lg-3"><div class="card card-kpi bg-dark p-3"><small class="text-white-50">Today's Total Runs</small><h3>{today_trips_count} Runs</h3></div></div>
                <div class="col-6 col-lg-3"><div class="card card-kpi bg-warning p-3 text-dark"><small class="text-dark-50">Vehicles Live on Road</small><h3>{active_trips_count} Active</h3></div></div>
                <div class="col-6 col-lg-3"><div class="card card-kpi bg-danger p-3"><small class="text-white-50">Outstanding Book Balances</small><h3>₹{total_pending_payments:,.2f}</h3></div></div>
                <div class="col-6 col-lg-3"><div class="card card-kpi bg-info p-3 text-dark"><small class="text-dark-50">Fleet Rolling Run Volume</small><h3>{total_km_run:,.1f} KM</h3></div></div>
            </div>

            <div class="row g-3 mb-4">
                <div class="col-6 col-md-3"><div class="card p-3 shadow-sm bg-white"><small class="text-muted">Gross Freight Billing</small><h4 class="text-primary fw-bold">₹{total_revenue:,.2f}</h4></div></div>
                <div class="col-6 col-md-3"><div class="card p-3 shadow-sm bg-white"><small class="text-muted">Total Variable Outlays</small><h4 class="text-danger fw-bold">₹{(total_diesel + total_tolls + total_commissions + total_other):,.2f}</h4></div></div>
                <div class="col-12 col-md-6"><div class="card p-3 shadow-sm text-white bg-success"><small class="text-white-50">Audited Net Ledger Profits</small><h2 class="fw-bold">₹{net_profit:,.2f}</h2></div></div>
            </div>

            <div class="card p-4 shadow-sm mb-4 bg-white text-center">
                <h5 class="text-muted mb-3 fw-bold">Fleet Operations Metrics Matrix</h5>
                <img src="/analytics-chart.png" class="img-fluid rounded mx-auto d-block" style="max-height: 280px;" alt="Fleet Visual Analytics">
            </div>

            <div class="card p-4 shadow-sm mb-4 bg-white">
                <h4 class="mb-4 text-dark fw-bold text-secondary">📌 Dispatch / Log Logged Run Records</h4>
                <form action="/dashboard/add-trip" method="POST">
                    <div class="row g-3">
                        <div class="col-md-3">
                            <label class="form-label fw-semibold">📅 Logging Date Target</label>
                            <input type="date" name="manual_date" class="form-control" value="{date.today().strftime('%Y-%m-%d')}" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label fw-semibold">🚖 Select Asset Car</label>
                            <select name="vehicle_plate" class="form-select" required>
                                {vehicle_options}
                            </select>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label fw-semibold">👤 Assigned Driver</label>
                            <select name="assigned_driver" class="form-select" required>
                                <option value="Ravi" selected>Ravi (Default)</option>
                                <option value="Kumar">Kumar</option>
                                <option value="Srinivas">Srinivas</option>
                            </select>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label fw-semibold">👤 Customer Name *</label>
                            <input type="text" name="customer_name" class="form-control" placeholder="Passenger Identity" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label fw-semibold">📞 Customer Mobile Phone *</label>
                            <input type="tel" name="customer_phone" class="form-control" placeholder="Mandatory Contact" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label fw-semibold">🛣️ Trip Dispatched Odo (KM)</label>
                            <input type="number" step="0.1" name="start_km" class="form-control" placeholder="Start Meter Read" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label fw-semibold">📍 Trip Source / Drop Destination</label>
                            <div class="input-group">
                                <input type="text" name="from_location" class="form-control" placeholder="From" required>
                                <input type="text" name="to_location" class="form-control" placeholder="To" required>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label fw-semibold">💰 Gross Fixed Deal Fare (₹)</label>
                            <input type="number" step="0.01" name="total_fare" class="form-control" placeholder="Contract Fare Amount" required>
                        </div>
                    </div>
                    <button type="submit" class="btn btn-dark w-100 mt-4 py-2 fw-bold text-uppercase">🚀 Dispatch & Sync Live Fleet Assignment</button>
                </form>
            </div>

            <h4 class="mb-3 text-dark fw-bold text-secondary">📊 Audited Master Business Run History (Click rows to expand)</h4>
            <div class="accordion" id="tripHistoryAccordion">
    """

    for index, t in enumerate(trips):
        date_str = t.created_at.strftime('%d-%b-%Y')
        
        if t.status == "Active":
            bg_badge_class = "badge-active-run"
            status_text = "LIVE RUNNING"
            profit_text = "Running..."
            profit_class = "text-warning"
        elif t.payment_status == "Pending" or t.balance_due > 0:
            bg_badge_class = "badge-pending-pay-run"
            status_text = f"Payment Pending (Due: ₹{t.balance_due})"
            single_trip_profit = t.total_fare - (t.diesel_cost + t.toll_cost + t.driver_commission + t.other_expenses)
            profit_text = f"Profit: ₹{single_trip_profit:,.2f}"
            profit_class = "text-success" if single_trip_profit >= 0 else "text-danger"
        else:
            bg_badge_class = "badge-completed-run"
            status_text = "COMPLETED & SETTLED"
            single_trip_profit = t.total_fare - (t.diesel_cost + t.toll_cost + t.driver_commission + t.other_expenses)
            profit_text = f"Profit: ₹{single_trip_profit:,.2f}"
            profit_class = "text-success" if single_trip_profit >= 0 else "text-danger"

        route_summary = f"{t.from_location} ➔ {t.to_location}"
        driver_name = t.assigned_driver if t.status == 'Active' else t.completed_by_driver

        html_content += f"""
                <div class="accordion-item shadow-sm">
                    <h2 class="accordion-header" id="heading_{t.id}">
                        <button class="history-header-btn {bg_badge_class}" type="button" data-bs-toggle="collapse" data-bs-target="#collapse_{t.id}" aria-expanded="false" aria-controls="collapse_{t.id}">
                            <div class="d-flex align-items-center gap-3 flex-wrap">
                                <span>📅 <b>{date_str}</b></span>
                                <span class="badge bg-secondary fs-6">{t.vehicle_plate}</span>
                                <span class="text-dark fw-semibold">👤 Driver: {driver_name}</span>
                                <span class="text-dark-50 text-truncate" style="max-width: 250px;">🛣️ {route_summary}</span>
                            </div>
                            <div class="d-flex align-items-center gap-3">
                                <span class="{profit_class} fw-bold me-2">{profit_text}</span>
                                <small class="text-muted d-none d-md-inline">▶ Click to Open</small>
                            </div>
                        </button>
                    </h2>
                    <div id="collapse_{t.id}" class="accordion-collapse collapse" aria-labelledby="heading_{t.id}" data-bs-parent="#tripHistoryAccordion">
                        <div class="accordion-body bg-light text-dark border-top">
                            <div class="row g-4">
                                <div class="col-md-3">
                                    <div class="bg-white p-3 rounded shadow-sm h-100">
                                        <h6 class="text-secondary border-bottom pb-1 fw-bold">👤 Customer Detail</h6>
                                        <p class="mb-1"><b>Name:</b> {t.customer_name}</p>
                                        <p class="mb-1"><b>Phone:</b> {t.customer_phone}</p>
                                        <p class="mb-0"><b>Status:</b> <span class="badge bg-dark">{status_text}</span></p>
                                    </div>
                                </div>
                                <div class="col-md-3">
                                    <div class="bg-white p-3 rounded shadow-sm h-100">
                                        <h6 class="text-secondary border-bottom pb-1 fw-bold">🛣️ Range Metrics</h6>
                                        <p class="mb-1"><b>Start Odo:</b> {t.start_km} KM</p>
                                        <p class="mb-1"><b>End Odo:</b> {t.end_km if t.end_km else '-'} KM</p>
                                        <p class="mb-1"><b>Net Run:</b> {t.distance_travelled} KM</p>
                                        <p class="mb-0"><b>Fuel Efficiency:</b> {f'{t.mileage:.2f} km/l' if (t.status == 'Completed' and t.diesel_litres > 0) else 'N/A'}</p>
                                    </div>
                                </div>
                                <div class="col-md-3">
                                    <div class="bg-white p-3 rounded shadow-sm h-100">
                                        <h6 class="text-secondary border-bottom pb-1 fw-bold">💰 Detailed Trip Ledger</h6>
                                        <p class="mb-1 text-primary"><b>Gross Deal Fare:</b> ₹{t.total_fare}</p>
                                        <p class="mb-1 text-muted"><b>Diesel Cost:</b> ₹{t.diesel_cost} ({t.diesel_litres if t.diesel_litres else '0'} L)</p>
                                        <p class="mb-1 text-muted"><b>Toll Outlay:</b> ₹{t.toll_cost}</p>
                                        <p class="mb-1 text-muted"><b>Driver Commission:</b> ₹{t.driver_commission}</p>
                                        <p class="mb-0 text-muted"><b>Misc Expenses:</b> ₹{t.other_expenses}</p>
                                    </div>
                                </div>
                                <div class="col-md-3">
                                    <div class="bg-white p-3 rounded shadow-sm h-100 d-flex flex-column justify-content-between">
                                        <div>
                                            <h6 class="text-secondary border-bottom pb-1 fw-bold">⚙️ Settle Ledger & Actions</h6>
                                            <p class="mb-1"><b>Collected:</b> ₹{t.amount_received}</p>
                                            <p class="mb-2 text-danger"><b>Remaining Due:</b> ₹{t.balance_due}</p>
                                        </div>
                                        <div>
                                            <form action="/dashboard/settle-payment/{t.id}" method="POST" class="row g-1 align-items-center mb-2">
                                                <div class="col-8"><input type="number" step="0.01" class="form-control form-control-sm" name="amt" placeholder="Collect ₹" required></div>
                                                <div class="col-4"><button type="submit" class="btn btn-sm btn-success w-100">Add</button></div>
                                            </form>
                                            <form action="/dashboard/delete-trip/{t.id}" method="POST" onsubmit="return confirm('⚠️ CRITICAL WARNING: Delete this record permanently?');">
                                                <button type="submit" class="btn btn-sm btn-outline-danger w-100 fw-bold py-1">🗑️ Delete Entry</button>
                                            </form>
                                        </div>
                                    </div>
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
    manual_date: str = Form(...),
    vehicle_plate: str = Form(...),
    assigned_driver: str = Form(...),
    customer_name: str = Form(...), 
    customer_phone: str = Form(...),
    start_km: float = Form(...), 
    from_location: str = Form(...),
    to_location: str = Form(...),
    total_fare: float = Form(...), 
    db: Session = Depends(get_db)
):
    parsed_date = datetime.strptime(manual_date, "%Y-%m-%d")
    new_trip = models.Trip(
        created_at=parsed_date,
        vehicle_plate=vehicle_plate,
        assigned_driver=assigned_driver,
        customer_name=customer_name,
        customer_phone=customer_phone,
        start_km=start_km,
        from_location=from_location,
        to_location=to_location,
        total_fare=total_fare,
        balance_due=total_fare,
        payment_status="Pending",
        status="Active"
    )
    db.add(new_trip)
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/dashboard/settle-payment/{trip_id}")
def reconcile_trip_payment(trip_id: int, amt: float = Form(...), db: Session = Depends(get_db)):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if trip:
        trip.amount_received += amt
        trip.balance_due = trip.total_fare - trip.amount_received
        if trip.balance_due <= 0:
            trip.payment_status = "Paid"
            trip.balance_due = 0.0
        elif trip.amount_received > 0:
            trip.payment_status = "Partial"
        db.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/dashboard/delete-trip/{trip_id}")
def purge_trip_record(trip_id: int, db: Session = Depends(get_db)):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if trip:
        db.delete(trip)
        db.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


# --- FIELD DRIVER PORTAL RUN MANIFESTS ---
@app.get("/driver-portal", response_class=HTMLResponse)
def driver_portal(request: Request, db: Session = Depends(get_db)):
    active_trips = db.query(models.Trip).filter(models.Trip.status == "Active").all()
    
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Field Driver Run Manifest Portal</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>body { background-color: #1b1e21; color: white; }</style>
    </head>
    <body>
        <div class="container py-4">
            <h2 class="mb-4 text-warning fw-bold">🚖 Live Field Driver Assignment Runs</h2>
    """
    
    if not active_trips:
        html_content += """
            <div class="alert alert-secondary text-center p-5 rounded-4 bg-dark border-secondary">
                <h4 class="text-white-50">🎉 All Runs Cleared & Logged!</h4>
                <p class="mb-0 text-muted">Awaiting dispatcher assignment uploads from backend systems.</p>
            </div>
        """
    else:
        for t in active_trips:
            html_content += f"""
            <div class="card bg-dark text-white border-warning mb-4 shadow-sm p-3" style="border-width: 2px; border-radius:14px;">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-center">
                        <h4 class="card-title text-warning fw-bold mb-0">Asset Vehicle: {t.vehicle_plate}</h4>
                        <span class="badge bg-danger">LIVE DISPATCH</span>
                    </div>
                    <hr class="border-secondary my-2">
                    <p class="mb-1 text-white-50">👤 <b>Client:</b> {t.customer_name} ({t.customer_phone})</p>
                    <p class="mb-1 text-white-50">📍 <b>Route Map:</b> {t.from_location} to {t.to_location}</p>
                    <p class="mb-2 text-warning fs-5">🛣️ <b>Dispatched Open Odo: {t.start_km:.1f} KM</b></p>
                    
                    <form action="/driver-portal/complete-trip/{t.id}" method="POST" class="bg-black p-3 rounded-3 border border-secondary">
                        <h6 class="text-warning border-bottom border-secondary pb-1 mb-3">📦 Finalize Journey Completion Logistics</h6>
                        
                        <div class="mb-2">
                            <label class="form-label small text-white-50">👤 Name of Current Driver Operating *</label>
                            <input type="text" name="completed_by_driver" class="form-control form-control-sm bg-dark text-white border-secondary" value="{t.assigned_driver}" required>
                        </div>

                        <div class="mb-2">
                            <label class="form-label small text-warning fw-bold">🏁 Journey End Closing Odometer (KM Value) *</label>
                            <input type="number" step="0.1" name="end_km" class="form-control form-control-sm bg-warning text-dark border-0 fw-bold" required min="{t.start_km + 0.1}">
                        </div>

                        <div class="row g-2 mb-2">
                            <div class="col-6">
                                <label class="form-label small text-white-50">⛽ Diesel Cost (Total ₹)</label>
                                <input type="number" step="0.01" name="diesel_cost" class="form-control form-control-sm bg-dark text-white border-secondary" value="0">
                            </div>
                            <div class="col-6">
                                <label class="form-label small text-white-50">⛽ Total Fuel Litres Added</label>
                                <input type="number" step="0.01" name="diesel_litres" class="form-control form-control-sm bg-dark text-white border-secondary" value="0">
                            </div>
                        </div>
                        <div class="row g-2 mb-3">
                            <div class="col-6">
                                <label class="form-label small text-white-50"> Toll Charges Paid (₹)</label>
                                <input type="number" step="0.01" name="toll_cost" class="form-control form-control-sm bg-dark text-white border-secondary" value="0">
                            </div>
                            <div class="col-6">
                                <label class="form-label small text-white-50">🤵 Driver Commissions Earned</label>
                                <input type="number" step="0.01" name="driver_commission" class="form-control form-control-sm bg-dark text-white border-secondary" value="0">
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label small text-white-50">🛠️ Other Expense Outlays</label>
                            <div class="input-group input-group-sm">
                                <input type="number" step="0.01" name="other_expenses" class="form-control bg-dark text-white border-secondary" value="0" style="max-width:35%;">
                                <input type="text" name="expense_note" class="form-control bg-dark text-white border-secondary" placeholder="Specify reason">
                            </div>
                        </div>

                        <button type="submit" class="btn btn-warning btn-sm w-100 fw-bold py-2 mt-2 text-dark text-uppercase">✅ Lock Journey Parameters</button>
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


# --- AUTOMATIC MATPLOTLIB GRAPHICS MOTOR ---
@app.get("/analytics-chart.png")
def get_analytics_chart(db: Session = Depends(get_db)):
    completed_trips = db.query(models.Trip).filter(models.Trip.status == "Completed").all()
    fig, ax = plt.subplots(figsize=(6, 3))
    
    if not completed_trips:
        ax.text(0.5, 0.5, 'No vehicle data logged yet.\nHistory records are empty.', 
                horizontalalignment='center', verticalalignment='center', 
                fontsize=11, color='gray', weight='bold')
        ax.set_xticks([])
        ax.set_yticks([])
    else:
        revenue = sum(t.total_fare for t in completed_trips)
        expenses = sum(t.diesel_cost + t.toll_cost + t.driver_commission + t.other_expenses for t in completed_trips)
        profit = revenue - expenses

        categories = ['Gross Revenue', 'Operational Cost', 'Net Profit Margin']
        values = [revenue, expenses, profit]
        colors = ['#007bff', '#dc3545', '#28a745']

        bars = ax.bar(categories, values, color=colors, width=0.45, edgecolor='black', linewidth=0.6)
        ax.set_ylabel('Ledger Balances (₹)', fontsize=8)
        ax.grid(axis='y', linestyle='--', alpha=0.3)

        for bar in bars:
            yval = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2, yval + (max(values)*0.01), f"₹{int(yval):,}", ha='center', va='bottom', fontsize=8, weight='bold')

    plt.tight_layout()
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png', dpi=150)
    img_buf.seek(0)
    plt.close(fig)
    return StreamingResponse(img_buf, media_type="image/png")
