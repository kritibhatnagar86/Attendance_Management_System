import math
# import psycopg2
import uuid
import platform
from sqlalchemy import text
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from datetime import datetime

# OS-Specific Imports
try:
    from plyer import gps
except ImportError:
    gps = None  

try:
    from geopy.geocoders import Nominatim
except ImportError:
    Nominatim = None  

# Database Connection using SQLAlchemy
DATABASE_URL = "postgresql://neondb_owner:npg_sd5UD1XuWYrT@ep-wispy-salad-a8c23f8w-pooler.eastus2.azure.neon.tech/Attendance_System?sslmode=require"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Unique Device ID (Ensures One Attendance Per Device Per Day)
DEVICE_ID = str(uuid.getnode())

# Teacher's Fixed Location (Change as Needed)
TEACHER_LOCATION = {"lat": 28.6139, "lon": 77.2090}  

# Haversine Formula to Calculate Distance
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi, delta_lambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

class AttendanceApp(App):
    def build(self):
        self.current_location = None  

        layout = BoxLayout(orientation="vertical", padding=20, spacing=20)

        self.status_label = Label(text="Fetching location...")
        layout.add_widget(self.status_label)

        self.attendance_label = Label(text="Attendance Status")
        layout.add_widget(self.attendance_label)

        self.student_id_input = TextInput(hint_text="Enter Student ID", multiline=False)
        layout.add_widget(self.student_id_input)

        self.register_btn = Button(text="Register Location", size_hint=(1, 0.2))
        self.register_btn.bind(on_press=self.register_student)
        layout.add_widget(self.register_btn)

        self.mark_btn = Button(text="Mark Attendance", size_hint=(1, 0.2))
        self.mark_btn.bind(on_press=self.mark_attendance)
        layout.add_widget(self.mark_btn)

        if platform.system() == "Android" and gps:
            try:
                gps.configure(on_location=self.update_location, on_status=self.on_gps_status)
                gps.start(minTime=1000, minDistance=1)
            except Exception as e:
                self.status_label.text = f"GPS Error: {e}"
        else:
            self.get_location_fallback()

        return layout

    def update_location(self, **kwargs):
        self.current_location = {"lat": kwargs["lat"], "lon": kwargs["lon"]}
        self.status_label.text = f"GPS Location: {self.current_location['lat']}, {self.current_location['lon']}"

    def on_gps_status(self, status):
        if status == "provider-disabled":
            self.status_label.text = "⚠️ GPS is disabled. Enable it in settings."

    def get_location_fallback(self):
        if Nominatim:
            try:
                geolocator = Nominatim(user_agent="attendance_app")
                location = geolocator.geocode("Jaipur, India")  
                if location:
                    self.current_location = {"lat": location.latitude, "lon": location.longitude}
                    self.status_label.text = f"Approx. Location: {self.current_location['lat']}, {self.current_location['lon']}"
                else:
                    self.status_label.text = "Location not found."
            except Exception as e:
                self.status_label.text = f"Geolocation Error: {e}"
        else:
            self.status_label.text = "⚠️ Geopy is not installed."

    def register_student(self, instance):
        student_id = self.student_id_input.text.strip()

        if not student_id:
            self.attendance_label.text = "Please enter a Student ID!"
            return

        if not self.current_location:
            self.attendance_label.text = "Waiting for location..."
            return

        lat, lon = self.current_location["lat"], self.current_location["lon"]
        date = datetime.now().date()
        time = datetime.now().time()

        session = SessionLocal()
        try:
            result = session.execute(
    text("SELECT * FROM attendance WHERE student_id = :student_id AND date = :date"),
    {"student_id": student_id, "date": date}
).fetchone()
            
            if result:
                self.attendance_label.text = "Attendance already marked for today!"
            else:
                session.execute(
    text("INSERT INTO attendance (student_id, date, time, latitude, longitude, device_id) VALUES (:student_id, :date, :time, :lat, :lon, :device_id)"),
    {"student_id": student_id, "date": date, "time": time, "lat": lat, "lon": lon, "device_id": DEVICE_ID}
)
                session.commit()
                self.attendance_label.text = f"Registered: {student_id}\nTime: {time}\nDevice ID: {DEVICE_ID}\nLocation: {lat}, {lon}"

        except Exception as e:
            self.attendance_label.text = f"Database Error: {e}"
        finally:
            session.close()

    def mark_attendance(self, instance):
        teacher_lat, teacher_lon = TEACHER_LOCATION["lat"], TEACHER_LOCATION["lon"]
        attendance_list = []
        date = datetime.now().date()

        session = SessionLocal()
        try:
            results = session.execute(
    text("SELECT student_id, latitude, longitude, device_id, time FROM attendance WHERE date = :date"),
    {"date": date}
).fetchall()

            
            for student_id, lat, lon, device_id, time in results:
                distance = haversine_distance(teacher_lat, teacher_lon, lat, lon)
                if distance <= 10:
                    attendance_list.append(f"{student_id} (Time: {time}, Device: {device_id})")

        except Exception as e:
            self.attendance_label.text = f"Database Error: {e}"
            return
        finally:
            session.close()

        if attendance_list:
            self.attendance_label.text = "Present: " + ", ".join(attendance_list)
        else:
            self.attendance_label.text = "No student within 10m range."

if __name__ == '__main__':
    AttendanceApp().run()
