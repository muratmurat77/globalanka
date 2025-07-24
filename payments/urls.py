# payments/urls.py
from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Ödeme listeleme sayfası
    path('list/', views.PaymentListView.as_view(), name='list'),
    # Yeni ödeme oluşturma sayfası (randevu ID'sine göre)
    path('create/<int:pk>/', views.PaymentCreateView.as_view(), name='create_payment'),
    # Aylık özet raporu
    path('monthly-summary/', views.MonthlySummaryView.as_view(), name='monthly_summary'),
    # Uzman komisyonları raporu
    path('expert-commissions/', views.ExpertCommissionListView.as_view(), name='expert_commissions'),
    # Temsilci komisyonları raporu
    path('agent-commissions/', views.AgentCommissionListView.as_view(), name='agent_commissions'),
    # Müşteri Temsilcisi Alt Temsilci Gelirleri Sayfası
    # 'name' parametresi, navbar'da kullanılan 'sub_agent_commissions' ile eşleştirildi
    path('agent/revenue/', views.agent_sub_agent_revenue_dashboard, name='sub_agent_commissions'),
]