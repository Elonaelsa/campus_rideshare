# 🚗 Campus RideShare

A web-based ride-sharing platform built for college students to share rides, reduce commute costs, and contribute to a greener campus environment.

---

## 📌 Features

- 🔐 **User Authentication** — Register & login with `@saintgits.org` email
- 🚘 **Offer a Ride** — Drivers can post rides with pickup, drop, date, time, seats & price
- 🔍 **Find Rides** — Students can search for available rides by location and date
- 📋 **Book a Ride** — Book rides with cash or online payment (screenshot upload)
- 👤 **Profile Management** — Update personal details and profile picture
- 🗂️ **My Rides** — View all offered and booked rides with status tracking
- ✏️ **Edit / Cancel Rides** — Manage your posted rides easily
- 🛠️ **Admin Dashboard** — Admin can view all users, rides, and bookings
- 🔑 **Forgot Password** — Firebase-powered password reset via email

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, Flask |
| Database | Firebase Realtime Database |
| Auth | Firebase Admin SDK + Session |
| Frontend | HTML, CSS, Jinja2 Templates |
| File Storage | Local (`static/uploads`) |
| Password Security | Werkzeug `generate_password_hash` |

---

## 📁 Project Structure

```
campus_rideshare/
│
├── flask_project/
│   ├── app.py               # Main Flask application
│   ├── config.py            # Configuration
│   ├── models.py            # Data models
│   ├── requirements.txt     # Python dependencies
│   ├── static/              # CSS, JS, images, uploads
│   ├── templates/           # HTML Jinja2 templates
│   └── uploads/             # Uploaded files
│
├── requirements.txt         # Root requirements
└── README.md
```

---

## ⚙️ Setup & Installation

### 1. Clone the repository
```bash
git clone https://github.com/Elonaelsa/campus_rideshare.git
cd campus_rideshare/flask_project
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
pip install firebase-admin requests
```

### 3. Add Firebase credentials
- Go to [Firebase Console](https://console.firebase.google.com/) → Your Project → ⚙️ Project Settings → Service Accounts
- Click **"Generate new private key"** and download the JSON file
- Place it in the `flask_project/` folder and rename it to:
  ```
  serviceAccountKey.json
  ```

### 4. Run the app
```bash
python app.py
```

Visit `http://127.0.0.1:5000` in your browser.

---

## 🔑 Default Admin Login

```
Email:    admin@saintgits.org
Password: admin123
```

---

## 🔒 Registration Rules

- Email must end with `@saintgits.org`
- Phone number must be exactly 10 digits
- College ID must be exactly 10 alphanumeric characters
- Password confirmation required

---

## 🌱 Impact

| Metric | Per Ride |
|--------|----------|
| 💰 Money Saved | ~₹50 |
| 🌿 CO₂ Reduced | ~2.5 kg |

---

## 📄 License

This project is built for academic purposes at **Saintgits College of Engineering**.

---

> Made with ❤️ by the Campus RideShare Team
