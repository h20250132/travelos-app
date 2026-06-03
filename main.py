import io
import os
from datetime import datetime, date
import matplotlib
matplotlib.use('Agg')  # Prevents server crash on headless cloud environment
import matplotlib.pyplot as plt

from fastapi import FastAPI, Depends, Request, Form, status, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

import models
# 🌟 FIXED: Changed 'Engine' to 'engine' to match your database file exactly
from database import engine, SessionLocal

# 🌟 FIXED: Using lowercase engine here to create tables automatically
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="TravelOS")

# Dependency to get database session per request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- OWNER DASHBOARD ---
@app.get("/dashboard", response_class=HTMLResponse)
def owner_dashboard(request: Request, db: Session = Depends(get_db)):
    # Sorted by created_at column matching your models.py
    trips = db.query(models.Trip).order_by(models.Trip.created_at.desc(), models.Trip.id.desc()).all()
    
    # Financial Matrix Calculations (Only for completed trips)
    total_revenue = sum(t.total_fare for t in trips if t.status == "Completed")
    total_diesel = sum(t.diesel_cost for t in trips if t.status == "Completed")
    total_tolls = sum(t.toll_cost for t in trips if t.status == "Completed")
    total_commissions = sum(t.driver_commission for t in trips if t.status == "Completed")
    total_expenses = total_diesel + total_tolls + total_commissions
    net_profit = total_revenue - total_expenses
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TravelOS Owner Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #f4f6f9; font-family: 'Segoe UI', system-ui, sans-serif; }}
            .card-summary {{ border-radius: 12px; border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
        </style>
    </head>
    <body>
        <div class="container py-4">
            <h2 class="mb-4 text-dark fw-bold">🚖 Venkataramana Travels Dashboard</h2>
            
            <div class="row g-3 mb-4">
                <div class="col-6 col-md-3">
                    <div class="card card-summary bg-primary text-white p-3">
                        <small>Total Revenue</small><h3>₹{total_revenue:,.2f}</h3>
                    </div>
                </div>
                <div class="col-6 col-md-3">
                    <div class="card card-summary bg-danger text-white p-3">
                        <small>Diesel Spend</small><h3>₹{total_diesel:,.2f}</h3>
                    </div>
                </div>
                <div class="col-6 col-md-3">
                    <div class="card card-summary bg-warning text-dark p-3">
                        <small>Driver Commission</small><h3>₹{total_commissions:,.2f}</h3>
                    </div>
                </div>
                <div class="col-6 col-md-3">
                    <div class="card card-summary bg-success text-white p-3">
                        <small>Net Profit</small><h3>₹{net_profit:,.2f}</h3>
                    </div>
                </div>
            </div>

            <div class="card card-summary p-3 mb-4 text-center">
                <h5 class="text-muted mb-2">Performance Analytics Trends</h5>
                <img src="/analytics-chart.png" class="img-fluid rounded mx-auto d-block" style="max-height: 280px;" alt="Performance Trends Chart">
            </div>

            <div class="card card-summary p-4 mb-4">
                <h4 class="mb-3 text-secondary fw-bold">📌 Dispatch New Trip Assignment</h4>
                <form action="/dashboard/add-trip" method="POST">
                    <div class="row g-3">
                        <div class="col-md-4">
                            <label class="form-label fw-semibold">👤 Customer Name</label>
                            <input type="text" name="customer_name" class="form-control" required placeholder="Passenger Name">
                        </div>
                        <div class="col-md-4">
                            <label class="form-label fw-semibold">📞 Customer Phone</label>
                            <input type="text" name="customer_phone" class="form-control" placeholder="Mobile Number (Optional)">
                        </div>
                        <div class="col-md-4">
                            <label class="form-label fw-semibold">🛣️ Opening Odometer (KM)</label>
                            <input type="number" step="0.1" name="start_km" class="form-control" required placeholder="Current Start KM">
                        </div>
                        <div class="col-md-4">
                            <label class="form-label fw-semibold">📍 From Location</label>
                            <input type="text" name="from_location" class="form-control" placeholder="Starting Point">
                        </div>
                        <div class="col-md-4">
                            <label class="form-label fw-semibold">🏁 To Location</label>
                            <input type="text" name="to_location" class="form-control" placeholder="Drop-off Destination">
                        </div>
                        <div class="col-md-4">
                            <label class="form-label fw-semibold">💰 Total Deal Fare (₹)</label>
                            <input type="number" step="0.01" name="total_fare" class="form-control" required placeholder="Agreed Billing Amount">
                        </div>
                    </div>
                    <button type="submit" class="btn btn-dark w-100 mt-3 py-2 fw-bold">🚀 Send Trip to Ravi's App</button>
                </form>
            </div>

            <div class="card card-summary overflow-hidden">
                <div class="bg-dark text-white p-3">
                    <h5 class="mb-0">📊 Live Trip Database & History Logs</h5>
                </div>
                <div class="table-responsive">
                    <table class="table table-striped table-hover text-center align-middle mb-0">
                        <thead class="table-dark">
                            <tr>
                                <th>📅 Date</th>
                                <th>👤 Customer</th>
                                <th>🗺️ Route Journey</th>
                                <th>🛣️ Start KM</th>
                                <th>🏁 End KM</th>
                                <th>💰 Fare</th>
                                <th>⛽ Diesel Cost</th>
                                <th>📌 Status</th>
                            </tr>
                        </thead>
                        <tbody>
    """
    
    for t in trips:
        # Formats your database created_at timestamp into clean text (e.g., 03-Jun-2026)
        formatted_date = t.created_at.strftime('%d-%b-%Y') if t.created_at else date.today().strftime('%d-%b-%Y')
        
        status_badge = '<span class="badge bg-success">Completed</span>' if t.status == "Completed" else '<span class="badge bg-warning text-dark">Active</span>'
        route_display = f"{t.from_location} ➔ {t.to_location}" if (t.from_location or t.to_location) else "Not Specified"
        end_km_display = f"{t.end_km:.1f} km" if t.end_km else "-"
        
        html_content += f"""
                            <tr>
                                <td><strong>{formatted_date}</strong></td>
                                <td>
                                    <div>{t.customer_name}</div>
                                    <small class="text-muted">{t.customer_phone if t.customer_phone else ''}</small>
                                </td>
                                <td><small>{route_display}</small></td>
                                <td>{t.start_km:.1f} km</td>
                                <td>{end_km_display}</td>
                                <td>₹{t.total_fare:,.2f}</td>
                                <td>₹{t.diesel_cost:,.2f}</td>
                                <td>{status_badge}</td>
                            </tr>
        """
        
    html_content += """
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.post("/dashboard/add-trip")
def add_trip(
    customer_name: str = Form(...), 
    customer_phone: str = Form(None),
    start_km: float = Form(...), 
    from_location: str = Form(None),
    to_location: str = Form(None),
    total_fare: float = Form(...), 
    db: Session = Depends(get_db)
):
    new_trip = models.Trip(
        customer_name=customer_name,
        customer_phone=customer_phone,
        start_km=start_km,
        from_location=from_location,
        to_location=to_location,
        total_fare=total_fare,
        status="Active"
    )
    db.add(new_trip)
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


# --- DRIVER PORTAL (RAVI'S APP INTERFACE) ---
@app.get("/driver-portal", response_class=HTMLResponse)
def driver_portal(request: Request, db: Session = Depends(get_db)):
    # Filter out active trips specifically assigned for the vehicle route runs
    active_trips = db.query(models.Trip).filter(models.Trip.status == "Active").all()
    
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Driver Trip Portal</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>body { background-color: #212529; color: white; font-family: system-ui, sans-serif; }</style>
    </head>
    <body>
        <div class="container py-4">
            <h2 class="mb-4 text-warning fw-bold">🚖 Ravi's Active Assignments</h2>
    """
    
    if not active_trips:
        html_content += """
            <div class="alert alert-secondary text-center p-5 rounded-4 bg-dark border-secondary">
                <h4 class="text-white-50">🎉 No active trips assigned!</h4>
                <p class="mb-0 text-muted">Enjoy your break. Check back later when your owner maps a run.</p>
            </div>
        """
    else:
        for t in active_trips:
            trip_date_str = t.created_at.strftime('%d-%b-%Y') if t.created_at else date.today().strftime('%d-%b-%Y')
            html_content += f"""
            <div class="card bg-dark text-white border-warning mb-4 shadow-sm p-3" style="border-width: 2px; border-radius:14px;">
                <div class="card-body">
                    <h5 class="card-title text-warning fw-bold">Passenger: {t.customer_name}</h5>
                    <p class="mb-1 text-white-50">📅 <strong>Date:</strong> {trip_date_str}</p>
                    <p class="mb-1 text-white-50">📍 <strong>Route:</strong> {t.from_location if t.from_location else '-'} to {t.to_location if t.to_location else '-'}</p>
                    <p class="mb-3 text-warning">🛣️ <strong>Assigned Opening KM:</strong> {t.start_km:.1f} km</p>
                    <hr class="border-secondary">
                    
                    <form action="/driver-portal/complete-trip/{t.id}" method="POST">
                        <div class="mb-3">
                            <label class="form-label text-warning fw-semibold">🏁 Closing Odometer KM Reading</label>
                            <input type="number" step="0.1" name="end_km" class="form-control bg-secondary text-white border-0" required min="{t.start_km}">
                        </div>
                        <div class="row g-2 mb-3">
                            <div class="col-6">
                                <label class="form-label text-white-50 small">⛽ Diesel Cost (₹)</label>
                                <input type="number" step="0.01" name="diesel_cost" class="form-control bg-secondary text-white border-0" value="0">
                            </div>
                            <div class="col-6">
                                <label class="form-label text-white-50 small"> Toll Charges (₹)</label>
                                <input type="number" step="0.01" name="toll_cost" class="form-control bg-secondary text-white border-0" value="0">
                            </div>
                        </div>
                        <div class="row g-2 mb-3">
                            <div class="col-6">
                                <label class="form-label text-white-50 small">⛽ Diesel Litres</label>
                                <input type="number" step="0.01" name="diesel_litres" class="form-control bg-secondary text-white border-0" value="0">
                            </div>
                            <div class="col-6">
                                <label class="form-label text-white-50 small">🤵 Commission (₹)</label>
                                <input type="number" step="0.01" name="driver_commission" class="form-control bg-secondary text-white border-0" value="0">
                            </div>
                        </div>
                        <button type="submit" class="btn btn-warning w-100 fw-bold py-2 mt-2 text-dark">✅ Complete & Save Trip Log</button>
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

@app.get("/analytics-chart.png")
def get_analytics_chart(db: Session = Depends(get_db)):
    trips = db.query(models.Trip).filter(models.Trip.status == "Completed").all()
    
    revenue = sum(t.total_fare for t in trips)
    expenses = sum(t.diesel_cost + t.toll_cost + t.driver_commission for t in trips)
    profit = revenue - expenses

    fig, ax = plt.subplots(figsize=(6, 3))
    categories = ['Revenue', 'Expenses', 'Net Profit']
    values = [revenue, expenses, profit]
    colors = ['#007bff', '#dc3545', '#28a745']

    bars = ax.bar(categories, values, color=colors, width=0.45, edgecolor='black', linewidth=0.6)
    ax.set_ylabel('Amounts in ₹', fontsize=9)
    ax.grid(axis='y', linestyle='--', alpha=0.4)

    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, yval + (yval*0.01 if yval > 0 else 1), f"₹{int(yval):,}", ha='center', va='bottom', fontsize=8, weight='bold')

    plt.tight_layout()
    
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png', dpi=150)
    img_buf.seek(0)
    plt.close(fig)
    
    return StreamingResponse(img_buf, media_type="image/png")
