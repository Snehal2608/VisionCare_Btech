from django.shortcuts import render, redirect, get_object_or_404
# import keras
import tensorflow as tf 
from PIL import Image
import numpy as np
import os
from django.core.files.storage import FileSystemStorage
from django.contrib import messages
from django.contrib.auth.models import User
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from django.core.files import File
from django.contrib.auth import authenticate, login as auth_login
from reportlab.lib import colors
from reportlab.platypus import Image as RLImage
from django.db.models import Count
from reportlab.lib.utils import simpleSplit
import json

# Import the validator from utils.py
from .utils import is_valid_fundus
from .models import UserProfile, EyeReport, Scanner

# Load model
media = 'media'
# Ensure this model is trained on ROP classes!
model = tf.keras.models.load_model('EfficientNetB0_model.h5') 

# ---------------- PREDICTION LOGIC ----------------
def makepredictions(path):
    # 1. Open and Process the Image
    img = Image.open(path)
    img_d = img.resize((224, 224))
    
    # Handle PNGs or Grayscale images
    if len(np.array(img_d).shape) < 3:
        rgb_img = Image.new("RGB", img_d.size)
        rgb_img.paste(img_d)
    else:
        rgb_img = img_d
        
    rgb_img = np.array(rgb_img, dtype=np.float64)
    rgb_img = rgb_img.reshape(1, 224, 224, 3)
    
    # 2. Get Prediction from Model
    predictions = model.predict(rgb_img)
    predicted_class = int(np.argmax(predictions))
    
    # Optional: Print confidence for debugging in terminal
    confidence = np.max(predictions) * 100
    print(f"Model Prediction Index: {predicted_class} | Confidence: {confidence:.2f}%")

    # 3. Map Index to ROP Stage
    # IMPORTANT: This list must match the EXACT order your model was trained on.
    classes = [
        "Normal",       # Index 0
        "ROP Stage 1",  # Index 1
        "ROP Stage 2",  # Index 2
        "ROP Stage 3",  # Index 3
        "ROP Stage 4",  # Index 4
        "ROP Stage 5",  # Index 5
        "Plus Disease"  # Index 6 (if applicable)
    ]
    
    # Return the class based strictly on the model's output index
    if 0 <= predicted_class < len(classes):
        return classes[predicted_class]
    else:
        return "Unknown"

def get_solution_for_disease(disease):
    disease_solutions = {
        "Normal": "Healthy retina. No signs of ROP. Routine follow-up as per standard screening guidelines.",
        
        "ROP Stage 1": "Demarcation Line detected. This is a mild abnormality. Usually resolves on its own without treatment. Close observation and follow-up exams are required.",
        
        "ROP Stage 2": "Ridge detected. The demarcation line has grown into a ridge. Treatment is rarely needed, but frequent monitoring is essential to ensure it does not progress.",
        
        "ROP Stage 3": "Extraretinal Fibrovascular Proliferation. Abnormal blood vessels are growing. Treatment (Laser or Anti-VEGF) may be required if 'Plus' disease is present.",
        
        "ROP Stage 4": "Partial Retinal Detachment. This is serious. Surgical intervention (Scleral buckling or Vitrectomy) is typically required to prevent blindness.",
        
        "ROP Stage 5": "Total Retinal Detachment. This is the most severe stage. Immediate complex surgery is required, though visual prognosis may be guarded.",
        
        "Plus Disease": "Dilation and tortuosity of vessels detected. This indicates active, severe progression. Immediate treatment (Laser/Injection) is usually required.",

        "Unknown": "Unable to determine stage. Please consult a specialist immediately."
    }
    return disease_solutions.get(disease, "Consult doctor for treatment and regular checkups.")


# ---------------- PDF Report Generator ----------------
def generate_pdf_report(report):
    profile = UserProfile.objects.get(user=report.patient)
    file_name = f"eye_reports/{report.patient.username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    file_path = os.path.join(media, file_name)

    c = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4
    margin = 50

    # ----------------- Border -----------------
    c.setStrokeColor(colors.HexColor("#024b30"))
    c.setLineWidth(3)
    c.rect(margin/2, margin/2, width - margin, height - margin, stroke=1, fill=0)

    # ----------------- Header -----------------
    c.setFillColor(colors.HexColor("#024b30"))
    c.rect(0, height - 80, width, 80, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Times-Bold", 26)
    c.drawCentredString(width/2, height - 50, "Vision Care Clinic")

    # ----------------- Patient Info Table -----------------
    y = height - 120
    c.setFillColor(colors.black)
    c.setFont("Times-Bold", 16)
    c.drawString(margin, y, "Patient Information:")
    y -= 5

    patient_data = [
        ("Name", report.patient.username),
        ("Email", report.patient.email),
        ("Age", getattr(profile, "age", "N/A")),
        ("Contact", getattr(profile, "contact_number", "N/A")),
        ("Address", getattr(profile, "address", "N/A")),
        ("Blood Group", getattr(profile, "blood_group", "N/A")),
        ("Gender", getattr(profile, "gender", "N/A")),
    ]
    if getattr(profile, "other_info", None):
        patient_data.append(("Other Info", profile.other_info))

    c.setFont("Times-Roman", 14)
    y -= 20
    row_height = 20
    for label, value in patient_data:
        c.drawString(margin + 10, y, f"{label}: {value}")
        y -= row_height

    # ----------------- Disease Info Table -----------------
    y -= 10
    c.setFillColor(colors.HexColor("#024b30"))
    c.setFont("Times-Bold", 16)
    c.drawString(margin, y, "Diagnosis & Recommendations:")
    y -= 20

    disease_data = [
        ("Disease Detected", report.disease),
        ("Solution & Care", report.solution),
    ]

    c.setFillColor(colors.black)
    c.setFont("Times-Roman", 14)
    for label, value in disease_data:
        c.drawString(margin + 10, y, f"{label}:")
        y -= 18
        # Wrap text for long solution
        if label == "Solution & Care":
            wrapped_lines = simpleSplit(value, "Times-Roman", 13, width - 2*margin - 20)
            for line in wrapped_lines:
                if y < margin + 50:
                    c.showPage()
                    y = height - margin
                c.drawString(margin + 20, y, line)
                y -= 18
        else:
            c.drawString(margin + 20, y, value)
            y -= 20

    # ----------------- Eye Image -----------------
    if report.report_image:
        try:
            img_path = os.path.join(media, report.report_image.name)
            img = RLImage(img_path)
            img_width = 200
            img_height = 200
            img.drawHeight = img_height
            img.drawWidth = img_width
            img.wrapOn(c, width, height)
            # Place image below disease info
            if y - img_height < margin + 50:
                c.showPage()
                y = height - margin - img_height
            img.drawOn(c, width - margin - img_width, y - img_height + 20)
            y -= img_height + 20
        except Exception as e:
            print("Error adding image to PDF:", e)

    # ----------------- Footer -----------------
    c.setFillColor(colors.HexColor("#024b30"))
    c.rect(0, 0, width, 50, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Times-Italic", 12)
    c.drawCentredString(width/2, 20, "Thank you for choosing Vision Care Clinic")

    c.showPage()
    c.save()
    return file_name

# ------------------- Existing views -------------------
def index(request):
    return render(request,'index.html')

def eye(request):
    if request.method == "POST" and request.FILES.get('upload'):
        upload = request.FILES['upload']
        
        # --- VALIDATION START ---
        is_valid, error_msg = is_valid_fundus(upload)
        if not is_valid:
            # Show warning and reload page without saving
            messages.warning(request, f"⚠️ {error_msg}")
            return render(request, 'eye.html')
        # --- VALIDATION END ---

        fss = FileSystemStorage()
        file = fss.save(upload.name, upload)
        file_url = fss.url(file)
        
        # Run prediction on the saved file
        disease = makepredictions(os.path.join(media, file))
        solution = get_solution_for_disease(disease)
        
        if request.user.is_authenticated:
             # Create report logic if you need it for the demo user
             pass 

        return render(request, 'eye.html', {'pred': disease, 'file_url': file_url})
    else:
        return render(request, 'eye.html')


# ------------------- Scanner Dashboard -------------------
def scanner_dashboard(request):
    if 'role' not in request.session or request.session['role'] != 'scanner':
        messages.error(request, "Access denied!")
        return redirect('login')

    patients = UserProfile.objects.filter(role='patient')
    for profile in patients:
        profile.latest_report = EyeReport.objects.filter(patient=profile.user).order_by('-date_time').first()

    patient_reports = [{'userprofile': p, 'report': p.latest_report} for p in patients]

    # Stats
    total_patients = patients.count()
    scans_completed = sum(1 for p in patients if p.latest_report)
    patients_remaining = total_patients - scans_completed

    context = {
        'patient_reports': patient_reports,
        'total_patients': total_patients,
        'scans_completed': scans_completed,
        'patients_remaining': patients_remaining
    }

    return render(request, 'scanner_dashboard.html', context)


def scan_patient(request, user_id):
    if 'role' not in request.session or request.session['role'] != 'scanner':
        messages.error(request, "Access denied!")
        return redirect('login')

    patient_user = get_object_or_404(User, id=user_id)
    # Removing patient_profile fetch if not strictly used, or keep it if needed for template
    
    existing_report = EyeReport.objects.filter(patient=patient_user).order_by('-date_time').first()

    if request.method == "POST" and 'eye_image' in request.FILES:
        uploaded_file = request.FILES['eye_image']

        # --- VALIDATION START ---
        is_valid, error_msg = is_valid_fundus(uploaded_file)
        if not is_valid:
            messages.warning(request, f"⚠️ {error_msg}")
            # Return immediately to the form with the warning
            return render(request, 'scan_patient.html', {
                'patient': patient_user,
                'existing_report': existing_report
            })
        # --- VALIDATION END ---

        fs = FileSystemStorage()
        filename = fs.save(uploaded_file.name, uploaded_file)
        file_path = fs.path(filename)

        disease = makepredictions(file_path)
        solution = get_solution_for_disease(disease)
        
        report = EyeReport.objects.create(
            patient=patient_user,
            disease=disease,
            solution=solution,
            report_image=uploaded_file
        )
        
        # Generate PDF report
        pdf_path = generate_pdf_report(report)
        with open(os.path.join(media, pdf_path), 'rb') as f:
            django_file = File(f)
            report.pdf_report.save(os.path.basename(pdf_path), django_file, save=True)

        messages.success(request, f"Scan completed for {patient_user.username}. Disease: {disease}")
        return redirect('scanner_dashboard')

    return render(request, 'scan_patient.html', {
        'patient': patient_user,
        'existing_report': existing_report
    })

# ------------------- Login / Signup / Dashboards -------------------
DOCTOR_CREDENTIALS = {"username": "dradmin", "password": "doctor123"}

def login(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        role = request.POST.get('role')

        # Doctor login (fixed credentials)
        if role == 'doctor':
            if username == "dradmin" and password == "doctor123":
                return redirect('doctor_dashboard')
            else:
                messages.error(request, "Invalid doctor credentials!")
                return redirect('login')

        # For patient and scanner
        try:
            user = User.objects.get(username=username)
            profile = UserProfile.objects.get(user=user)

            if profile.role != role:
                messages.error(request, f"Role mismatch! You are registered as {profile.role}.")
                return redirect('login')

            if user.check_password(password):
                auth_login(request, user)
                request.session['role'] = role

                if role == 'patient':
                    return redirect('patient_dashboard')
                elif role == 'scanner':
                    return redirect('scanner_dashboard')
            else:
                messages.error(request, "Incorrect password!")
        except User.DoesNotExist:
            messages.error(request, "User does not exist!")
        except UserProfile.DoesNotExist:
            messages.error(request, "User profile not found!")

        return redirect('login')

    return render(request, 'login.html')

def signup(request):
    if request.method == "POST":
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        role = request.POST['role']

        if role == 'doctor':
            messages.error(request, "Doctor account is fixed and cannot be created!")
            return redirect('signup')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists!")
            return redirect('signup')
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists!")
            return redirect('signup')

        user = User.objects.create_user(username=username, email=email, password=password)

        if role == 'patient':
            # Patient-specific fields
            age = request.POST.get('age')
            contact_number = request.POST.get('contact_number')
            address = request.POST.get('address')
            blood_group = request.POST.get('blood_group')
            gender = request.POST.get('gender')
            other_info = request.POST.get('other_info')

            profile = UserProfile.objects.create(
                user=user,
                role=role,
                age=age,
                contact_number=contact_number,
                address=address,
                blood_group=blood_group,
                gender=gender,
                other_info=other_info
            )
        else:
            profile = UserProfile.objects.create(user=user, role=role)

        messages.success(request, f"Account created for {username} as {role}!")
        return redirect('login')

    return render(request, 'signup.html')


def admin_dashboard(request):
    return render(request, 'admin_dashboard.html')

def doctor_dashboard(request):
    if request.method == "POST":
        if 'delete_report' in request.POST:
            report_id = request.POST.get('delete_report')
            EyeReport.objects.filter(id=report_id).delete()
        elif 'delete_scanner' in request.POST:
            scanner_id = request.POST.get('delete_scanner')
            UserProfile.objects.filter(id=scanner_id, role='scanner').delete()
        return redirect('doctor_dashboard')

    patients = UserProfile.objects.filter(role='patient')
    for profile in patients:
        latest_report = EyeReport.objects.filter(patient=profile.user).order_by('-date_time').first()
        profile.latest_report = latest_report

    scanners = UserProfile.objects.filter(role='scanner')

    total_patients = patients.count()
    scans_completed = sum(1 for p in patients if p.latest_report)
    patients_remaining = total_patients - scans_completed

    disease_counts = {}
    for profile in patients:
        if profile.latest_report:
            disease = profile.latest_report.disease
            disease_counts[disease] = disease_counts.get(disease, 0) + 1

    chart_labels = json.dumps(list(disease_counts.keys()))
    chart_data = json.dumps(list(disease_counts.values()))

    context = {
        'patients': patients,
        'scanners': scanners,
        'scans_completed': scans_completed,
        'patients_remaining': patients_remaining,
        'total_patients': total_patients,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
    }

    return render(request, 'doctor_dashboard.html', context)


def patient_detail(request, user_id):
    try:
        patient_user = get_object_or_404(User, id=user_id)
        reports = EyeReport.objects.filter(patient=patient_user).order_by('-date_time')
    except Exception as e:
        print("Error in patient_detail view:", e)
        raise

    return render(request, 'patient_detail.html', {
        'patient': patient_user,
        'reports': reports
    })

def patient_dashboard(request):
    user = request.user
    reports = EyeReport.objects.filter(patient=user).order_by('-date_time')
    profile = UserProfile.objects.get(user=user)

    context = {
        'patient': user,
        'reports': reports,
        'profile': profile
    }
    return render(request, 'patient_dashboard.html', context)

def mark_scan_done(request, user_id):
    patient_user = get_object_or_404(User, id=user_id)
    return redirect('scan_patient', user_id=patient_user.id)