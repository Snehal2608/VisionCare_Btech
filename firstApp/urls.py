from django.contrib import admin
from django.urls import path
from firstApp import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),
    path('eye/', views.eye, name='eye'),
    path('login/', views.login, name='login'),
    path('signup/', views.signup, name='signup'),

    # Scanner URLs
    path('scanner/', views.scanner_dashboard, name='scanner_dashboard'),
    path('scan_patient/<int:user_id>/', views.scan_patient, name='scan_patient'),

    # Dashboard pages
    path('patient_dashboard/', views.patient_dashboard, name='patient_dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('doctor-dashboard/', views.doctor_dashboard, name='doctor_dashboard'),
    

    # Doctor patient detail and scan actions
    path('doctor/patient/<int:user_id>/', views.patient_detail, name='patient_detail'),
    path('doctor/scan_done/<int:user_id>/', views.mark_scan_done, name='mark_scan_done'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)