# appointments/urls.py
from django.urls import path
from . import views 
from .views import (
    AppointmentCreateView,
    AppointmentListView,
    AppointmentUpdateView,
    cancel_appointment 
)

app_name = 'appointments' 

urlpatterns = [
    path('randevu/olustur/', AppointmentCreateView.as_view(), name='create'),
    path('randevu/liste/', AppointmentListView.as_view(), name='list'),
    path('randevu/guncelle/<int:pk>/', AppointmentUpdateView.as_view(), name='update'),
    path('randevu/iptal/<int:pk>/', cancel_appointment, name='cancel'), # Yeni eklenen URL
    path('get-available-slots/', views.get_available_appointment_slots, name='get_available_appointment_slots'),
]