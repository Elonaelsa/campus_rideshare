from flask import (
    Flask, render_template, request, jsonify, redirect, url_for,
    session, flash, get_flashed_messages
)
import firebase_admin
from firebase_admin import credentials, db
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import requests
import os

# ---------------- App setup ----------------
app = Flask(__name__)
app.secret_key = "supersecretkey"  # change for production

# ---------------- Firebase Initialization ----------------
# Ensure serviceAccountKey.json exists in project root (or change path)
SERVICE_ACCOUNT_PATH = "serviceAccountKey.json"
DATABASE_URL = "https://campusride-share-default-rtdb.asia-southeast1.firebasedatabase.app"

cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})

# ---------------- Upload folder setup ----------------
UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------- Helper utilities ----------------
def normalize_rtdb_output(obj):
    """
    Convert lists to dicts so templates can safely call .items().
    If obj is dict -> return as-is.
    If obj is list -> convert to {index: item} skipping None entries.
    """
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, list):
        return {str(i): item for i, item in enumerate(obj) if item is not None}
    return {}

def get_users_safe():
    return normalize_rtdb_output(db.reference("users").get() or {})

def get_rides_safe():
    return normalize_rtdb_output(db.reference("offered_rides").get() or {})

def get_bookings_safe():
    return normalize_rtdb_output(db.reference("bookings").get() or {})

# ---------------- Home ----------------
@app.route("/")
def index():
    return render_template("index.html")

# ---------------- Register ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        role = request.form.get("role", "").strip() or "student"
        college_id = request.form.get("college_id", "").strip()
        phone = request.form.get("phone", "").strip()
        id_document = request.files.get("id_document")
        terms = request.form.get("terms")

        if not all([full_name, email, password, confirm_password, role, college_id, phone, terms]):
            flash("⚠️ All fields are required.", "danger")
            return redirect(url_for("register"))

        if not email.endswith("@saintgits.org"):
            flash("📧 Use a @saintgits.org email.", "danger")
            return redirect(url_for("register"))

        if (not phone.isdigit()) or len(phone) != 10:
            flash("📱 Phone must be 10 digits.", "danger")
            return redirect(url_for("register"))

        if len(college_id) != 10 or not college_id.isalnum():
            flash("🆔 College ID must be 10 alphanumeric characters.", "danger")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("🔑 Passwords do not match.", "danger")
            return redirect(url_for("register"))

        users_ref = db.reference("users").get() or {}
        # Normalize
        users_ref = normalize_rtdb_output(users_ref)

        # uniqueness checks
        for _, user in users_ref.items():
            if user.get("email", "").lower() == email:
                flash("❌ Email already registered.", "danger")
                return redirect(url_for("register"))
            if user.get("phone") == phone:
                flash("❌ Phone already registered.", "danger")
                return redirect(url_for("register"))
            if user.get("college_id") == college_id:
                flash("❌ College ID already registered.", "danger")
                return redirect(url_for("register"))

        # Save ID document
        id_doc_filename = ""
        if id_document and id_document.filename != "":
            safe_filename = secure_filename(f"{college_id}_{id_document.filename}")
            id_document.save(os.path.join(UPLOAD_FOLDER, safe_filename))
            id_doc_filename = safe_filename

        hashed_pw = generate_password_hash(password)
        user_data = {
            "full_name": full_name,
            "email": email,
            "password": hashed_pw,
            "role": role,
            "college_id": college_id,
            "phone": phone,
            "college": "",
            "department": "",
            "id_document": id_doc_filename,
            "profile_image": "",
            "total_rides": 0,
            "rating": 0,
            "earned": 0,
            "date_joined": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        db.reference("users").push(user_data)
        flash("🎉 Registration successful. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

# ---------------- Login ----------------
# Admin default credentials (hardcoded fallback)
ADMIN_EMAIL = "admin@saintgits.org"
ADMIN_PASSWORD = "admin123"

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # Check hardcoded admin first
        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            # Create basic admin session (not stored in Firebase)
            session["user"] = {"id": "admin_local", "full_name": "Admin", "email": email, "role": "admin"}
            session["user_id"] = "admin_local"
            session["admin"] = True
            flash("👑 Logged in as admin (local).", "success")
            return redirect(url_for("admin_dashboard"))

        # Check Firebase users
        users_ref = db.reference("users").get() or {}
        users_ref = normalize_rtdb_output(users_ref)

        for key, user in users_ref.items():
            if user.get("email", "").lower() == email:
                if check_password_hash(user.get("password", ""), password):
                    session["user"] = {
                        "id": key,
                        "full_name": user.get("full_name", ""),
                        "email": user.get("email", ""),
                        "role": user.get("role", "user")
                    }
                    session["user_id"] = key
                    session["admin"] = (user.get("email", "").lower() == ADMIN_EMAIL)
                    if session["admin"]:
                        flash("👑 Welcome Admin!", "success")
                        return redirect(url_for("admin_dashboard"))
                    else:
                        flash("✅ Login successful!", "success")
                        return redirect(url_for("dashboard"))
                else:
                    flash("❌ Incorrect password.", "danger")
                    return redirect(url_for("login"))

        flash("⚠️ No account found with that email.", "warning")
        return redirect(url_for("login"))

    get_flashed_messages()
    return render_template("login.html")

# ---------------- Forgot Password ----------------
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        try:
            api_key = os.getenv("FIREBASE_API_KEY")
            if not api_key:
                flash("⚠️ Firebase API key not configured. Can't send reset email.", "danger")
                return redirect(url_for("forgot_password"))
            reset_url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}"
            payload = {"requestType": "PASSWORD_RESET", "email": email}
            response = requests.post(reset_url, json=payload)
            result = response.json()
            if "error" in result:
                flash("❌ " + result["error"]["message"], "danger")
            else:
                flash("📩 Password reset email sent. Check inbox.", "success")
                return redirect(url_for("login"))
        except Exception as e:
            flash(f"⚠️ Error sending reset email: {str(e)}", "danger")
    return render_template("forgot_password.html")

# ---------------- Logout ----------------
@app.route("/logout")
def logout():
    session.clear()
    flash("👋 Logged out.", "info")
    return redirect(url_for("index"))

# ---------------- Dashboard (User) ----------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        flash("⚠️ Please login first.", "warning")
        return redirect(url_for("login"))

    user_id = session.get("user_id")
    # fetch user data (normalize)
    user_data = db.reference(f"users/{user_id}").get()
    if not user_data:
        # if admin_local or missing, use session's user basic info
        user_data = session.get("user", {"full_name": "Unknown", "email": ""})

    # fetch rides offered by this user
    offered_rides_ref = db.reference("offered_rides").get() or {}
    offered_rides_ref = normalize_rtdb_output(offered_rides_ref)

    rides = []
    total_earnings = 0

    for ride_id, ride in offered_rides_ref.items():
        if not ride:
            continue
        # match by user_id or user name
        if ride.get("user_id") == user_id or ride.get("user") == session.get("user", {}).get("full_name"):
            r = dict(ride)
            r["id"] = ride_id
            try:
                ride_date = datetime.strptime(r.get("date", ""), "%Y-%m-%d").date()
                r["status"] = "Completed" if ride_date < datetime.today().date() else "Active"
            except Exception:
                r["status"] = r.get("status", "Active")
            rides.append(r)
            try:
                price = float(r.get("price", 0))
                booked = int(r.get("booked_seats", 0) or 0)
                total_earnings += price * booked
            except Exception:
                pass

    # --- COUNT OFFERED RIDES ---
    total_offered = len(rides)

    # --- COUNT BOOKED RIDES ---
    bookings_ref = db.reference("bookings").get() or {}
    total_booked = 0
    for _, booking in bookings_ref.items():
        if not booking:
            continue
        # user booked this ride
        if booking.get("user_id") == user_id:
            total_booked += 1

    # --- Stats (existing logic preserved) ---
    stats = {
        "total_rides": len(rides),
        "money_earned": total_earnings,
        "money_saved": len(rides) * 50,
        "co2_reduced": len(rides) * 2.5,
        "rating": user_data.get("rating", 4.8),
        "total_offered": total_offered,
        "total_booked": total_booked
    }

    return render_template("dashboard.html", user=user_data, stats=stats, rides=rides)
# ---------------- Profile view & update ----------------
@app.route("/profile")
def profile():
    if "user_id" not in session:
        flash("⚠️ Please login first.", "warning")
        return redirect(url_for("login"))
    user_id = session["user_id"]
    user = db.reference(f"users/{user_id}").get()
    if not user:
        flash("❌ User not found.", "danger")
        return redirect(url_for("dashboard"))
    return render_template("profile.html", user=user)

@app.route("/update_profile", methods=["GET", "POST"])
def update_profile():
    if "user_id" not in session:
        flash("⚠️ Please login first.", "warning")
        return redirect(url_for("login"))
    user_ref = db.reference(f"users/{session['user_id']}")
    user = user_ref.get() or {}
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        college = request.form.get("college", "").strip()
        department = request.form.get("department", "").strip()
        profile_image = request.files.get("profile_image")

        updates = {}
        if full_name: updates["full_name"] = full_name
        if phone: updates["phone"] = phone
        if college: updates["college"] = college
        if department: updates["department"] = department

        if profile_image and profile_image.filename != "":
            filename = secure_filename(f"{session['user_id']}_{profile_image.filename}")
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            profile_image.save(filepath)
            updates["profile_image"] = filename

        if updates:
            user_ref.update(updates)
            flash("✅ Profile updated.", "success")
        else:
            flash("ℹ️ No changes provided.", "info")
        return redirect(url_for("profile"))

    return render_template("update_profile.html", user=user)

@app.route("/update_password", methods=["POST"])
def update_password():
    if "user_id" not in session:
        flash("⚠️ Please login first.", "warning")
        return redirect(url_for("login"))
    user_ref = db.reference(f"users/{session['user_id']}")
    user = user_ref.get()
    if not user:
        flash("❌ User not found.", "danger")
        return redirect(url_for("dashboard"))

    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not check_password_hash(user.get("password", ""), current_password):
        flash("❌ Current password incorrect.", "danger")
        return redirect(url_for("update_profile"))
    if new_password != confirm_password:
        flash("❌ New passwords do not match.", "danger")
        return redirect(url_for("update_profile"))

    hashed = generate_password_hash(new_password)
    user_ref.update({"password": hashed})
    flash("✅ Password updated.", "success")
    return redirect(url_for("profile"))

# ---------------- Offer Ride ----------------
@app.route("/offer_ride", methods=["GET", "POST"])
def offer_ride():
    if "user_id" not in session:
        flash("⚠️ Please login first.", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        rides_ref = db.reference("offered_rides")
        counter_ref = db.reference("ride_counter")

        current_counter = counter_ref.get() or 0
        if isinstance(current_counter, dict):
            # If counter stored as dict accidentally, try to extract numeric value
            try:
                current_counter = int(current_counter.get("value", 0))
            except Exception:
                current_counter = 0
        try:
            new_ride_id = int(current_counter) + 1
        except Exception:
            new_ride_id = 1
        counter_ref.set(new_ride_id)

        pickup = request.form.get("pickup", "").strip()
        drop = request.form.get("drop", "").strip()
        date = request.form.get("date", "").strip()
        time = request.form.get("time", "").strip()
        seats = request.form.get("seats", "").strip()
        cost = request.form.get("cost", "").strip()
        vehicle = request.form.get("vehicle", "").strip()
        notes = request.form.get("notes", "").strip()

        user_id = session.get("user_id")
        user_name = session.get("user", {}).get("full_name") or ""

        ride_data = {
            "ride_id": new_ride_id,
            "user_id": user_id,
            "user": user_name,
            "pickup": pickup,
            "drop": drop,
            "date": date,
            "time": time,
            "seats": seats,
            "price": cost,
            "vehicle": vehicle,
            "notes": notes,
            "status": "active",
            "created_at": str(datetime.now())
        }

        rides_ref.child(str(new_ride_id)).set(ride_data)
        flash(f"✅ Ride #{new_ride_id} added.", "success")
        return redirect(url_for("my_rides"))

    return render_template("offer_ride.html")

# ---------------- My Rides ----------------
@app.route("/my_rides")
def my_rides():
    if "user_id" not in session:
        flash("⚠️ Please login first.", "warning")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    user = db.reference(f"users/{user_id}").get() or session.get("user", {})

    now = datetime.now()
    offered_rides = []
    booked_rides = []

    # ------------------ Offered Rides ------------------
    rides_ref = db.reference("offered_rides").get() or {}

    # Handle both dict and list Firebase outputs
    if isinstance(rides_ref, dict):
        rides_iter = rides_ref.items()
    elif isinstance(rides_ref, list):
        rides_iter = enumerate(rides_ref)
    else:
        rides_iter = []

    for rid, ride in rides_iter:
        if not isinstance(ride, dict):
            continue
        if ride.get("driver_id") == user_id or ride.get("user") == user.get("full_name"):
            ride_copy = dict(ride)
            ride_copy["id"] = rid

            # Determine status by comparing date/time with current time
            try:
                ride_dt = datetime.strptime(
                    f"{ride.get('date', '')} {ride.get('time', '')}", "%Y-%m-%d %H:%M"
                )
                ride_copy["status"] = "Upcoming" if ride_dt >= now else "Completed"
            except Exception:
                ride_copy["status"] = ride.get("status", "Unknown")

            offered_rides.append(ride_copy)

    # ------------------ Booked Rides ------------------
    bookings_ref = db.reference("bookings").get() or {}

    # Handle both dict and list Firebase outputs
    if isinstance(bookings_ref, dict):
        bookings_iter = bookings_ref.items()
    elif isinstance(bookings_ref, list):
        bookings_iter = enumerate(bookings_ref)
    else:
        bookings_iter = []

    for _, booking in bookings_iter:
        if not isinstance(booking, dict):
            continue
        if booking.get("user_id") == user_id:
            ride_id = booking.get("ride_id")
            ride_details = db.reference(f"offered_rides/{ride_id}").get() or {}

            ride_info = {
                "id": ride_id,
                "driver": booking.get("ride_owner", booking.get("driver_name", "Unknown")),
                "pickup": booking.get("pickup", ride_details.get("pickup", "")),
                "drop": booking.get("drop", ride_details.get("drop", "")),
                "date": booking.get("date", ride_details.get("date", "")),
                "time": booking.get("time", ride_details.get("time", "")),
                "status": booking.get("status", ride_details.get("status", "Pending")),
                "payment_method": booking.get("payment_method", "N/A"),
                "screenshot": booking.get("payment_screenshot", ""),
            }
            booked_rides.append(ride_info)

    # ------------------ Render Template ------------------
    return render_template(
        "my_rides.html",
        user=user,
        offered_rides=offered_rides,
        booked_rides=booked_rides,
    )


# ---------------- Edit Ride ----------------
@app.route("/edit_ride/<ride_id>", methods=["GET", "POST"])
def edit_ride(ride_id):
    if "user_id" not in session:
        flash("⚠️ Please login first.", "warning")
        return redirect(url_for("login"))

    ride_ref = db.reference(f"offered_rides/{ride_id}")
    ride = ride_ref.get()

    if not ride:
        flash("❌ Ride not found.", "danger")
        return redirect(url_for("my_rides"))

    if request.method == "POST":
        # Get updated form data
        updated_data = {
            "pickup": request.form.get("pickup"),
            "drop": request.form.get("drop"),
            "date": request.form.get("date"),
            "time": request.form.get("time"),
            "available_seats": request.form.get("available_seats"),
            "price": request.form.get("price"),
        }

        # Update in Firebase
        ride_ref.update(updated_data)
        flash("✅ Ride details updated successfully!", "success")
        return redirect(url_for("my_rides"))

    # Render edit page with pre-filled data
    return render_template("edit_ride.html", ride=ride, ride_id=ride_id)


# ---------------- Cancel Ride ----------------
@app.route("/cancel_ride/<ride_id>", methods=["POST"])
def cancel_ride(ride_id):
    if "user_id" not in session:
        flash("⚠️ Please login first.", "warning")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    ride_id = str(ride_id)

    # --- 1) Try updating offered_ride directly ---
    offered_ref = db.reference(f"offered_rides/{ride_id}")
    try:
        offered_ride = offered_ref.get()
    except Exception:
        offered_ride = None

    updated_offered = False

    if offered_ride:
        try:
            offered_ref.update({"status": "Cancelled"})
            updated_offered = True
        except Exception:
            pass

    # --- 2) If not found, search offered_rides by ride_id field ---
    if not updated_offered:
        all_offered = db.reference("offered_rides").get() or {}
        if isinstance(all_offered, dict):
            for key, value in all_offered.items():
                if isinstance(value, dict) and (
                    str(key) == ride_id or str(value.get("ride_id", "")) == ride_id
                ):
                    try:
                        db.reference(f"offered_rides/{key}").update({"status": "Cancelled"})
                        updated_offered = True
                        break
                    except Exception:
                        pass

    # --- 3) Update related bookings ---
    updated_bookings = 0
    bookings_raw = db.reference("bookings").get() or {}

    if isinstance(bookings_raw, dict):
        for bkey, bdata in bookings_raw.items():
            if isinstance(bdata, dict) and str(bdata.get("ride_id", "")) == ride_id:
                try:
                    db.reference(f"bookings/{bkey}").update({"status": "Cancelled"})
                    updated_bookings += 1
                except Exception:
                    pass

    # --- Flash result ---
    if updated_offered or updated_bookings > 0:
        flash("🚫 Ride cancelled successfully!", "info")
    else:
        flash("⚠️ Could not find ride/bookings to cancel.", "warning")

    return redirect(url_for("my_rides"))


# ---------------- Find Rides ----------------
@app.route("/find_rides", methods=["GET", "POST"])
def find_rides():
    available_rides = {}
    if request.method == "POST":
        pickup = request.form.get("pickup", "").strip().lower()
        drop = request.form.get("drop", "").strip().lower()
        date = request.form.get("date", "").strip()

        # Log search
        db.reference("ride_requests").push({
            "pickup": pickup,
            "drop": drop,
            "date": date,
            "searched_at": str(datetime.now())
        })

        all_rides = db.reference("offered_rides").get() or {}
        all_rides = normalize_rtdb_output(all_rides)

        for key, ride in all_rides.items():
            if not ride:
                continue
            pickup_db = ride.get("pickup", "").strip().lower()
            drop_db = ride.get("drop", "").strip().lower()
            date_db = ride.get("date", "").strip()
            if ((not pickup or pickup in pickup_db or pickup_db in pickup) and
                (not drop or drop in drop_db or drop_db in drop) and
                (not date or date == date_db)):
                ride_id = ride.get("ride_id", key)
                available_rides[ride_id] = ride

    return render_template("find_rides.html", available_rides=available_rides)


# ---------------- Ride Details ----------------
@app.route("/ride_details/<ride_id>")
def ride_details(ride_id):
    # Fetch ride details from Firebase
    ride = db.reference(f"offered_rides/{ride_id}").get()
    if not ride:
        flash("❌ Ride not found.", "danger")
        return redirect(url_for("find_rides"))

    # Fetch driver info (if user_id or driver_id exists)
    driver_id = ride.get("user_id") or ride.get("driver_id")
    driver = db.reference(f"users/{driver_id}").get() if driver_id else None

    # Optionally include driver info inside ride dict
    if driver:
        ride["driver_info"] = driver

    # Pass everything to template (including ride_id for Book Ride)
    return render_template("ride_details.html", ride=ride, driver=driver, ride_id=ride_id)



# -------------------- Book Ride Page (Map + Confirm) --------------------
@app.route("/book_ride/<ride_id>")
def book_ride(ride_id):
    """
    Fetch ride details from Firebase Realtime Database
    and display them on the booking page.
    """
    try:
        # Fetch ride details from Firebase
        ride = db.reference(f"offered_rides/{ride_id}").get()

        # If no such ride found, show an error and redirect
        if not ride:
            flash("❌ Ride not found.", "danger")
            return redirect(url_for("find_rides"))

        # Render the booking page and pass all ride details
        return render_template("book_ride.html", ride=ride, ride_id=ride_id)

    except Exception as e:
        print("Error fetching ride:", e)
        flash("⚠️ Something went wrong while fetching ride details.", "danger")
        return redirect(url_for("find_rides"))
# ---------------- Confirm Booking ----------------
@app.route("/confirm_booking/<ride_id>", methods=["GET", "POST"])
def confirm_booking(ride_id):
    """
    Displays payment confirmation form and handles booking confirmation.
    """
    if "user_id" not in session:
        flash("⚠️ Please login to book a ride.", "warning")
        return redirect(url_for("login"))

    try:
        # Fetch ride details
        ride_ref = db.reference(f"offered_rides/{ride_id}")
        ride = ride_ref.get()

        if not ride:
            flash("❌ Ride not found.", "danger")
            return redirect(url_for("find_rides"))

        # When the form is submitted
        if request.method == "POST":
            payment_method = request.form.get("payment_method")
            note = request.form.get("note", "").strip()
            screenshot_url = None

            # Handle file upload if online payment selected
            if payment_method == "online_payment" and "payment_screenshot" in request.files:
                file = request.files["payment_screenshot"]
                if file and file.filename != "":
                    import os
                    from werkzeug.utils import secure_filename

                    filename = secure_filename(file.filename)
                    upload_path = os.path.join("static/uploads", filename)
                    os.makedirs(os.path.dirname(upload_path), exist_ok=True)
                    file.save(upload_path)
                    screenshot_url = f"/{upload_path}"

            # Save booking data to Firebase
            booking_data = {
                "ride_id": ride_id,
                "user_id": session["user_id"],
                "ride_owner": ride.get("user"),
                "pickup": ride.get("pickup"),
                "drop": ride.get("drop"),
                "date": ride.get("date"),
                "time": ride.get("time"),
                "vehicle": ride.get("vehicle"),
                "price": ride.get("price"),
                "payment_method": payment_method,
                "payment_screenshot": screenshot_url,
                "note": note,
                "status": "confirmed",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            # Push booking into Firebase
            booking_ref = db.reference("bookings").push(booking_data)

            # Decrease available seat count if > 0
            if int(ride.get("seats", 0)) > 0:
                ride_ref.update({"seats": int(ride["seats"]) - 1})

            flash("✅ Booking confirmed successfully!", "success")
            return redirect(url_for("my_rides"))

        # GET request → Show the payment form
        return render_template("confirm_booking.html", ride=ride, ride_id=ride_id)

    except Exception as e:
        print("Error confirming booking:", e)
        flash("⚠️ Something went wrong while confirming booking.", "danger")
        return redirect(url_for("find_rides"))

# ---------------- Admin-only pages ----------------

@app.route("/admin_dashboard")
def admin_dashboard():
    if not session.get("admin"):
        flash("⚠️ Unauthorized.", "danger")
        return redirect(url_for("login"))

    admin_data = session.get("user")

    rides_ref = db.reference("offered_rides").get() or {}
    users_ref = db.reference("users").get() or {}
    bookings_ref = db.reference("bookings").get() or {}

    users_ref = normalize_rtdb_output(users_ref)
    rides_ref = normalize_rtdb_output(rides_ref)
    bookings_ref = normalize_rtdb_output(bookings_ref)

    today = datetime.now().date()
    rides_list = []
    for ride_id, ride_data in rides_ref.items():
        if not ride_data:
            continue
        ride_date_str = ride_data.get("date", "")
        try:
            ride_date = datetime.strptime(ride_date_str, "%Y-%m-%d").date()
            status = "Expired" if ride_date < today else ride_data.get("status", "Active")
        except Exception:
            status = ride_data.get("status", "Active")

        driver_name = "Unknown"
        driver_email = ""
        driver_id = ride_data.get("user_id") or ride_data.get("driver_id")
        if driver_id and isinstance(users_ref, dict):
            matched = users_ref.get(str(driver_id))
            if not matched:
                # search by uid match
                for uid, udata in users_ref.items():
                    if uid == driver_id:
                        matched = udata
                        break
            if matched:
                driver_name = matched.get("full_name") or matched.get("name") or driver_name
                driver_email = matched.get("email", "")

        ride_info = {
            "id": ride_id,
            "pickup": ride_data.get("pickup", "N/A"),
            "drop": ride_data.get("drop", "N/A"),
            "date": ride_date_str,
            "seats": ride_data.get("seats", "N/A"),
            "price": ride_data.get("price", "N/A"),
            "status": status,
            "driver_name": driver_name,
            "driver_email": driver_email
        }
        rides_list.append(ride_info)

    # stats
    total_rides = len(rides_list)
    total_users = len(users_ref) if isinstance(users_ref, dict) else 0
    total_booked = len(bookings_ref) if isinstance(bookings_ref, dict) else 0
    money_earned = total_booked * 10
    avg_rating = 4.7

    stats = {
        "total_rides": total_rides,
        "total_users": total_users,
        "total_booked": total_booked,
        "money_earned": money_earned,
        "rating": avg_rating
    }

    return render_template("admin_dashboard.html", user=admin_data, stats=stats, rides=rides_list, users=users_ref)

# ---------------- Admin user profiles / list ----------------
@app.route("/admin_users_profiles")
def admin_users_profiles():
    if not session.get("admin"):
        flash("⚠️ Unauthorized.", "danger")
        return redirect(url_for("login"))
    admin_data = session.get("user")
    users_ref = db.reference("users").get() or {}
    users_ref = normalize_rtdb_output(users_ref)

    user_profiles = []
    for uid, u in users_ref.items():
        if not u:
            continue
        profile = {
            "id": uid,
            "name": u.get("full_name") or u.get("name") or "Unknown",
            "email": u.get("email", "N/A"),
            "role": u.get("role", "User"),
            "date_joined": u.get("date_joined", "Not available")
        }
        user_profiles.append(profile)

    return render_template("admin_users_profiles.html", user_profiles=user_profiles, user=admin_data)

@app.route("/admin_user_profile/<user_id>")
def admin_user_profile(user_id):
    if not session.get("admin"):
        flash("⚠️ Unauthorized.", "danger")
        return redirect(url_for("login"))
    user_data = db.reference(f"users/{user_id}").get()
    if not user_data:
        flash("❌ User not found.", "danger")
        return redirect(url_for("admin_users_profiles"))
    admin_data = session.get("user")
    return render_template("admin_user_profile_detail.html", user_data=user_data, user=admin_data)

# ---------------- Manage Users (admin) ----------------
@app.route("/manage_users")
def manage_users():
    if not session.get("admin"):
        flash("⚠️ Unauthorized.", "danger")
        return redirect(url_for("login"))
    users = db.reference("users").get() or {}
    users = normalize_rtdb_output(users)
    return render_template("manage_users.html", users=users)

# Add / edit / delete user routes (AJAX-friendly)
@app.route("/add_user", methods=["POST"])
def add_user():
    if not session.get("admin"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    try:
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "user")
        if not (full_name and email and password):
            return jsonify({"success": False, "message": "Missing fields"})
        hashed = generate_password_hash(password)
        date_joined = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_data = {
            "full_name": full_name,
            "email": email,
            "password": hashed,
            "role": role,
            "date_joined": date_joined,
            "college_id": "",
            "phone": "",
            "college": "",
            "department": "",
            "profile_image": "",
            "total_rides": 0,
            "rating": 0,
            "earned": 0
        }
        db.reference("users").push(user_data)
        return jsonify({"success": True, "message": "User added"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/edit_user/<user_id>", methods=["POST"])
def edit_user(user_id):
    if not session.get("admin"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    try:
        updates = {}
        full_name = request.form.get("full_name")
        email = request.form.get("email")
        role = request.form.get("role")
        phone = request.form.get("phone")
        if full_name: updates["full_name"] = full_name.strip()
        if email: updates["email"] = email.strip().lower()
        if role: updates["role"] = role.strip()
        if phone: updates["phone"] = phone.strip()
        if updates:
            db.reference(f"users/{user_id}").update(updates)
        return jsonify({"success": True, "message": "User updated"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/delete_user/<user_id>", methods=["DELETE"])
def delete_user(user_id):
    if not session.get("admin"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    try:
        db.reference(f"users/{user_id}").delete()
        return jsonify({"success": True, "message": "User deleted"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
# -------- Helper class (add this ONCE above all routes) --------
class DualRideStore(dict):
    """
    Allows Jinja to use rides BOTH as:
    - list (for ride in rides)
    - dict (for ride_id, ride in rides.items())
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.list_data = list(self.values())

    def __iter__(self):
        return iter(self.list_data)

    def __getitem__(self, key):
        if isinstance(key, int):   # index access
            return self.list_data[key]
        return super().__getitem__(key)  # key access

    def items(self):
        return super().items()

    def refresh(self):
        self.list_data = list(self.values())


# ---------------- Manage Rides (admin) ----------------
@app.route("/manage_rides")
def manage_rides():
    if not session.get("admin"):
        flash("⚠️ Unauthorized.", "danger")
        return redirect(url_for("login"))

    rides_ref = db.reference("offered_rides").get() or {}
    rides_ref = normalize_rtdb_output(rides_ref)

    # ∆ CHANGED: Use DualRideStore instead of list
    rides = DualRideStore()

    for key, ride in rides_ref.items():
        if ride:
            ride["id"] = key
            rides[key] = ride   # behaves like dict

    rides.refresh()  # builds list structure

    return render_template("manage_rides.html", rides=rides)



@app.route("/manage_offered_rides")
def manage_offered_rides():
    if not session.get("admin"):
        flash("⚠️ Unauthorized.", "danger")
        return redirect(url_for("login"))

    rides_ref = db.reference("offered_rides").get() or {}
    rides_ref = normalize_rtdb_output(rides_ref)

    offered_rides = []
    for key, ride in rides_ref.items():
        if not ride:
            continue
        offered_rides.append({
            "id": key,
            "driver": ride.get("user", "Unknown"),
            "pickup": ride.get("pickup", "N/A"),
            "drop": ride.get("drop", "N/A"),
            "date": ride.get("date", "N/A"),
            "time": ride.get("time", "N/A"),
            "status": ride.get("status", "N/A"),
            "seats": ride.get("seats", "N/A"),
        })
    return render_template("manage_offered_rides.html", offered_rides=offered_rides)


# ---------------- Delete Ride ----------------
@app.route("/delete_ride/<ride_id>")
def delete_ride(ride_id):
    if not session.get("admin"):
        flash("⚠️ Unauthorized.", "danger")
        return redirect(url_for("login"))

    db.reference(f"offered_rides/{ride_id}").delete()
    flash("Ride deleted.", "success")
    return redirect(url_for("manage_rides"))

# ---------------- Ride Details (Admin) ----------------
@app.route("/admin/ride_details/<ride_id>")
def admin_ride_details(ride_id):
    if not session.get("admin"):
        flash("⚠️ Please login as admin.", "warning")
        return redirect(url_for("login"))

    # Fetch ride
    ride_ref = db.reference(f"offered_rides/{ride_id}").get()
    if not ride_ref:
        flash("Ride not found!", "danger")
        return redirect(url_for("manage_rides"))

    ride = normalize_rtdb_output(ride_ref)

    # ----- Fetch passengers (list or dict safe conversion)
    passengers = ride.get("passengers", {})

    # Convert list → dict (safe for Jinja items())
    if isinstance(passengers, list):
        passengers = {
            str(i): p for i, p in enumerate(passengers)
            if isinstance(p, dict)
        }
    elif not isinstance(passengers, dict):
        passengers = {}

    # Final ride details sent to template
    ride_details = {
        "pickup": ride.get("pickup", "N/A"),
        "drop": ride.get("drop", "N/A"),
        "date": ride.get("date", "N/A"),
        "time": ride.get("time", "N/A"),
        "seats": ride.get("seats", 0),
        "price": ride.get("price", 0),
        "status": ride.get("status", "Active"),
        "driver_name": ride.get("driver_name", ride.get("user", "N/A")),
        "vehicle": ride.get("vehicle", "Not Provided"),

        # Always dictionary → safe for Jinja2
        "passengers": passengers,
        "booked_seats": len(passengers)
    }

    return render_template(
        "admin_ride_details.html",
        ride=ride_details,
        ride_id=ride_id
    )
# ---------------- Admin Bookings ----------------
@app.route("/admin_booking")
def admin_booking():
    if not session.get("admin"):
        flash("⚠️ Unauthorized.", "danger")
        return redirect(url_for("login"))

    bookings_data = db.reference("bookings").get() or {}

    bookings = []
    for booking_id, b in bookings_data.items():
        bookings.append({
            "id": booking_id,
            "ride_id": b.get("ride_id", ""),
            "user_name": b.get("user_name", ""),
            "pickup": b.get("pickup", ""),
            "drop": b.get("drop", ""),
            "date": b.get("date", ""),
            "seats": b.get("seats", ""),
            "status": b.get("status", "")
        })

    return render_template("admin_booking.html", bookings=bookings)


# ---------------- View Booking Details ----------------
@app.route("/admin/booking_details/<booking_id>")
def booking_details(booking_id):
    if not session.get("admin"):
        flash("⚠️ Unauthorized.", "danger")
        return redirect(url_for("login"))

    booking = db.reference(f"bookings/{booking_id}").get()

    if not booking:
        flash("Booking not found", "danger")
        return redirect(url_for("admin_booking"))

    return render_template("admin_view_booking.html", booking=booking, id=booking_id)


# ---------------- Delete Booking ----------------
@app.route("/admin/delete_booking/<booking_id>", methods=["POST"])
def delete_booking(booking_id):
    if not session.get("admin"):
        return {"success": False, "message": "Unauthorized"}

    ref = db.reference(f"bookings/{booking_id}")
    if not ref.get():
        return {"success": False, "message": "Booking not found"}

    ref.delete()
    return {"success": True, "message": "Booking deleted successfully"}

# ---------------- Admin Reports ----------------
@app.route("/admin_reports")
def admin_reports():
    if not session.get("admin"):
        flash("⚠️ Unauthorized.", "danger")
        return redirect(url_for("login"))

    users_ref = db.reference("users").get() or {}
    rides_ref = db.reference("offered_rides").get() or {}

    users_ref = normalize_rtdb_output(users_ref)
    rides_ref = normalize_rtdb_output(rides_ref)

    total_users = len(users_ref)
    total_rides = len(rides_ref)
    total_revenue = total_rides * 50  # sample calculation
    growth_percent = round((total_rides / (total_users or 1)) * 10, 2)

    return render_template(
        "admin_reports.html",
        total_users=total_users,
        total_rides=total_rides,
        total_revenue=total_revenue,
        growth_percent=growth_percent,
        users_ref=users_ref,
        rides_ref=rides_ref
    )

# ---------------- Public user profiles listing (optional) ----------------
@app.route("/user_profiles")
def user_profiles():
    users = db.reference("users").get() or {}
    users = normalize_rtdb_output(users)
    return render_template("user_profiles.html", users=users)

# ---------------- Bookings list (user/admin) ----------------
@app.route("/bookings")
def bookings():
    bookings = db.reference("bookings").get() or {}
    bookings = normalize_rtdb_output(bookings)
    return render_template("bookings.html", bookings=bookings)

# ---------------- Reports (public route mapped earlier) ----------------
@app.route("/reports")
def reports():
    return render_template("reports.html")

# ---------------- Run ----------------
if __name__ == "__main__":
    app.run(debug=True)
