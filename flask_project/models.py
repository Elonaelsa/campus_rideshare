from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

# Initialize db object (will be linked with app later)
db = SQLAlchemy()

# -----------------
# User Table
# -----------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)             # Full Name
    email = db.Column(db.String(120), unique=True, nullable=False)    # College Email
    password = db.Column(db.String(200), nullable=False)              # Password
    role = db.Column(db.String(20), default="student")                # student / staff / admin
    college_id = db.Column(db.String(50), nullable=False)             # College ID
    phone = db.Column(db.String(20), nullable=False)                  # Phone Number
    id_document_url = db.Column(db.String(300))                        # Firebase Storage ID document URL
    created_at = db.Column(db.DateTime, default=datetime.utcnow)      # Timestamp of registration

    rides = db.relationship("Ride", backref="driver", lazy=True)
    bookings = db.relationship("Booking", backref="passenger", lazy=True)

    def __repr__(self):
        return f"<User {self.email}>"

# -----------------
# Ride Table
# -----------------
class Ride(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(120), nullable=False)
    destination = db.Column(db.String(120), nullable=False)
    date = db.Column(db.Date, nullable=False)                         # Use proper date type
    time = db.Column(db.Time, nullable=False)                         # Use proper time type
    seats = db.Column(db.Integer, nullable=False)

    driver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    bookings = db.relationship("Booking", backref="ride", lazy=True)

    def __repr__(self):
        return f"<Ride {self.source} -> {self.destination}>"

# -----------------
# Booking Table
# -----------------
class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ride_id = db.Column(db.Integer, db.ForeignKey("ride.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(20), default="pending")              # pending / confirmed
    booking_time = db.Column(db.DateTime, default=datetime.utcnow)    # Timestamp of booking

    # Ensure a user cannot book the same ride twice
    __table_args__ = (db.UniqueConstraint('ride_id', 'user_id', name='unique_booking'),)

    def __repr__(self):
        return f"<Booking Ride:{self.ride_id} User:{self.user_id}>"
