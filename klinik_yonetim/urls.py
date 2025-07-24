# klinik_yonetim/urls.py
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views # Django'nun hazır kimlik doğrulama görünümleri
from django.views.generic import TemplateView # Basit şablonları doğrudan render etmek için

urlpatterns = [
    # Admin Paneli
    path('admin/', admin.site.urls),
    
    # Uygulama URL'lerinin dahil edilmesi
    path('appointments/', include('appointments.urls')), # Randevu uygulaması URL'leri
    path('hesap/', include('accounts.urls')),         # Hesap uygulaması URL'leri (kayıt, giriş, profil vb.)
    path('payments/', include('payments.urls')),         # Ödeme uygulaması URL'leri
    
    # Ana Sayfa URL'si
    path('', TemplateView.as_view(template_name='home.html'), name='home'), 
    
    # Django'nun yerleşik şifre sıfırlama akışı
    # 1. Şifre sıfırlama isteği formu (eposta girilir)
    path('sifre-sifirla/', 
         auth_views.PasswordResetView.as_view(
             template_name='accounts/password_reset.html',
             email_template_name='accounts/password_reset_email.html', # E-posta şablonunu belirtmek iyi bir pratiktir
             subject_template_name='accounts/password_reset_subject.txt', # E-posta konusu şablonu
         ), 
         name='password_reset'),
    
    # 2. Şifre sıfırlama e-postası gönderildi mesajı
    path('sifre-sifirla/basarili/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='accounts/password_reset_done.html'
         ), 
         name='password_reset_done'),
    
    # 3. Şifre sıfırlama bağlantısına tıklanınca şifre belirleme formu
    path('sifre-sifirla/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='accounts/password_reset_confirm.html'
         ), 
         name='password_reset_confirm'),
    
    # 4. Şifre sıfırlama işlemi tamamlandı mesajı
    path('sifre-sifirla/tamamlandi/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='accounts/password_reset_complete.html'
         ), 
         name='password_reset_complete'),
]
