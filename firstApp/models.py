from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('patient', 'Patient'),
        ('scanner', 'Scanner'),
    ]
    
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('O+', 'O+'), ('O-', 'O-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    # Patient additional info
    age = models.PositiveIntegerField(blank=True, null=True)
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES, blank=True, null=True)
    gender = models.CharField(max_length=10, blank=True, null=True)  # optional
    other_info = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"

class EyeReport(models.Model):
    patient = models.ForeignKey(User, on_delete=models.CASCADE)
    disease = models.CharField(max_length=255)
    solution = models.TextField()
    report_image = models.ImageField(upload_to='eye_images/')
    pdf_report = models.FileField(upload_to='eye_reports/', null=True, blank=True)
    date_time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient.username} - {self.disease}"

class Patient(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    scanned = models.BooleanField(default=False)
    disease = models.CharField(max_length=100, blank=True, null=True)
    image = models.ImageField(upload_to='eye_images/', blank=True, null=True)

    def __str__(self):
        return self.name

class Scanner(models.Model):
    name = models.CharField(max_length=100)
    status = models.CharField(max_length=50, default='Available')