import io
import os
from datetime import date
import matplotlib
matplotlib.use('Agg')  # Prevents crash on headless cloud server
import matplotlib.pyplot as plt

from fastapi import FastAPI, Depends, Request, Form, status, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

import models
from database import Engine, SessionLocal

# Create database tables if they don't exist
models.Base.metadata.create_all(bind=Engine)

app = FastAPI(title="TravelOS")

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- OWNER DASHBOARD ROUTE ---
@app.get("/dashboard", response_class=HTMLResponse)
def owner_dashboard(request: Request, db: Session = Depends(get_db)):
    # Fetch all trips sorted by date (newest first)
    trips = db.query(models.Trip).order_by(models.Trip.trip_date.desc(), models.Trip.id.desc()).all()
    
    # Financial Calculations
    total_revenue = sum(t.total_fare for t in trips if t.status == "Completed")
    total_diesel = sum(t.diesel_expenses for t in trips if t.status == "Completed")
    total_tolls = sum(t.toll_expenses for t in trips if t.status == "Completed")
    net_profit = total_revenue - (total_diesel + total_tolls)
    
    # Simple HTML Layout packed inside a responsive mobile template
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TravelOS Owner Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #f4f6f9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
            .card-summary {{ border-radius: 12px; border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
        </style>
    </head>
    <body>
        <div class="container py-4">
            <h2 class="mb-4 text-dark fw-bold">🚖 Venkataramana Travels Dashboard</h2>
            
            <!-- Financial Matrix -->
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
                    <div class="card card-summary bg-secondary text-white p-3">
                        <small>Toll Spend</small><h3>₹{total_tolls:,.2f}</h3>
                    </div>
                </div>
                <div class="col-6 col-md-3">
                    <div class="card card-summary bg-success text-white p-3">
                        <small>Net Profit</small><h3>₹{net_profit:,.2f}</h3>
                    </div>
                </div>
            </div>

            <!-- Dynamic Graph Chart -->
            <div class="card card-summary p-3 mb-4 text-center">
                <h5 class="text-muted mb-2">Monthly Analytics Chart</h5>
                <img src="/analytics-chart.png" class="img-fluid rounded mx-auto d-block" style="max-height: 300px;" alt="Performance Trends Chart">
            </div>

            <!-- Add Trip Assignment Dispatch Form -->
            <div class="card card-summary p-4 mb-4">
                <h4 class="mb-3 text-secondary fw-bold">📌 Dispatch New Trip Assignment</h4>
                <form action="/dashboard/add-trip" method="POST">
                    <div class="row g-3">
                        <div class="col-md-3">
                            <label class="form-label fw-semibold">📅 Trip Date</label>
                            <input type="date" name="trip_date" class="form-control" value="{date.today().strftime('%Y-%m-%d')}" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label fw-semibold">👤 Passenger Name</label>
                            <input type="text" name="passenger_name" class="form-control" placeholder="Passenger Name" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label fw-semibold">🛣️ Start Odometer (KM)</label>
                            <input type="number" name="start_km" class="form-control" placeholder="Opening KM" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label fw-semibold">💰 Fixed Fare (₹)</label>
                            <input type="number" step="0.01" name="total_fare" class="form-control" placeholder="Deal Fare Amount" required>
                        </div>
                    </div>
                    <button type="submit" class="btn btn-dark w-100 mt-3 py-2 fw-bold">🚀 Send Trip to Ravi's App</button>
                </form>
            </div>

            <!-- Bottom Live Trip History Database Table -->
            <div class="card card-summary overflow-hidden">
                <div class="bg-dark text-white p-3">
                    <h5 class="mb-0">📊 Live Trip Database & History</h5>
                </div>
                <div class="table-responsive">
                    <table class="table table-striped table-hover text-center align-middle mb-0">
                        <thead class="table-dark">
                            <tr>
                                <th>📅 Date</th>
                                <th>👤 Passenger</th>
                                <th>🛣️ Start KM</th>
                                <th>🏁 End KM</th>
                                <th>💰 Fare</th>
                                <th>⛽ Diesel</th>
                                <th> Toll</th>
                                <th>📌 Status</th>
                            </tr>
                        </thead>
                        <tbody>
    """
    
    for t in trips:
        formatted_date = t.trip_date.strftime('%d-%b-%Y')
        status_badge = '<span class="badge bg-success">Completed</span>' if t.status == "Completed" else '<span class="badge bg-warning text-dark">On Road</span>'
        end_km_display = f"{t.end_km} km" if t.end_km else "-"
        
        html_content += f"""
                            <tr>
                                <td><strong>{formatted_date}</strong></td>
                                <td>{t.passenger_name}</td>
                                <td>{t.start_km} km</td>
                                <td>{end_km_display}</td>
                                <td>₹{t.total_fare}</td>
                                <td>₹{t.diesel_expenses}</td>
                                <td>₹{t.toll_expenses}</td>
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
def add_trip(trip_date: str = Form(...), passenger_name: str = Form(...), start_km: int = Form(...), total_fare: float = Form(...), db: Session = Depends(get_db)):
    parsed_date = date.fromisoformat(trip_date)
    new_trip = models.Trip(
        trip_date=parsed_date,
        passenger_name=passenger_name,
        start_km=start_km,
        total_fare=total_fare,
        status="Assigned"
    )
    db.add(new_trip)
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


# --- DRIVER PORTAL ROUTE (RAVI'S INTERFACE) ---
@app.get("/driver-portal", response_class=HTMLResponse)
def driver_portal(request: Request, db: Session = Depends(get_db)):
    # Ravi only needs to see active assigned trips on the road
    active_trips = db.query(models.Trip).filter(models.Trip.status == "Assigned").all()
    
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Driver Trip Portal</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>body { background-color: #212529; color: white; }</style>
    </head>
    <body>
        <div class="container py-4">
            <h2 class="mb-4 text-warning fw-bold">🚖 Ravi's Active Assignments</h2>
    """
    
    if not active_trips:
        html_content += """
            <div class="alert alert-secondary text-center p-5 rounded-4">
                <h4>🎉 No active trips assigned!</h4>
                <p class="mb-0 text-muted">Enjoy your break. Check back later when new trips are scheduled.</p>
            </div>
        """
    else:
        for t in active_trips:
            html_content += f"""
            <div class="card bg-dark text-white border-warning mb-4 shadow-sm p-3" style="border-width: 2px; border-radius:14px;">
                <div class="card-body">
                    <h5 class="card-title text-warning fw-bold">Passenger: {t.passenger_name}</h5>
                    <p class="mb-1">📅 <strong>Date:</strong> {t.trip_date.strftime('%d-%b-%Y')}</p>
                    <p class="mb-3">🛣️ <strong>Assigned Opening KM:</strong> {t.start_km} km</p>
                    <hr class="border-secondary">
                    
                    <form action="/driver-portal/complete-trip/{t.id}" method="POST">
                        <div class="mb-3">
                            <label class="form-label text-warning">🏁 Closing Odometer KM Reading</label>
                            <input type="number" name="end_km" class="form-control bg-secondary text-white border-0" required min="{t.start_km}">
                        </div>
                        <div class="row g-2 mb-3">
                            <div class="col-6">
                                <label class="form-label text-white-50">⛽ Diesel Bills (₹)</label>
                                <input type="number" step="0.01" name="diesel" class="form-control bg-secondary text-white border-0" value="0">
                            </div>
                            <div class="col-6">
                                <label class="form-label text-white-50"> Toll Charges (₹)</label>
                                <input type="number" step="0.01" name="tolls" class="form-control bg-secondary text-white border-0" value="0">
                            </div>
                        </div>
                        <button type="submit" class="btn btn-warning w-100 fw-bold py-2 mt-2">✅ Complete & Save Trip Log</button>
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
def complete_trip(trip_id: int, end_km: int = Form(...), diesel: float = Form(...), tolls: float = Form(...), db: Session = Depends(get_db)):
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if trip:
        trip.end_km = end_km
        trip.diesel_expenses = diesel
        trip.toll_expenses = tolls
        trip.status = "Completed"
        db.commit()
    return RedirectResponse(url="/driver-portal", status_code=status.HTTP_303_SEE_OTHER)


# --- AUTOMATIC CHART MAKER ROUTE ---
@app.get("/analytics-chart.png")
def get_analytics_chart(db: Session = Depends(get_db)):
    trips = db.query(models.Trip).filter(models.Trip.status == "Completed").all()
    
    # Calculate simple dynamic metrics
    revenue = sum(t.total_fare for t in trips)
    expenses = sum(t.diesel_expenses + t.toll_expenses for t in trips)
    profit = revenue - expenses

    # Build the Matplotlib visualization figure
    fig, ax = plt.subplots(figsize=(6, 3.5))
    categories = ['Revenue', 'Expenses', 'Net Profit']
    values = [revenue, expenses, profit]
    colors = ['#007bff', '#dc3545', '#28a745']

    bars = ax.bar(categories, values, color=colors, width=0.5, edgecolor='black', linewidth=0.7)
    ax.set_ylabel('Amounts in ₹')
    ax.grid(axis='y', linestyle='--', alpha=0.5)

    # Attach amounts directly above the bars
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, yval + (yval*0.02 if yval > 0 else 1), f"₹{int(yval)}", ha='center', va='bottom', fontsize=9, weight='bold')

    plt.tight_layout()
    
    # Compress figure layout and turn into an online streaming binary response
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png', dpi=150)
    img_buf.seek(0)
    plt.close(fig)
    
    return StreamingResponse(img_buf, media_type="image/png")
