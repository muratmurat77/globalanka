# accounts/urls.py
from django.urls import path
from .views import (
    SignUpView,
    ProfileView,
    CustomLoginView,
    AgentClientManagementView, 
    ExpertDashboardView,     # ExpertDashboardView artık aktif olarak import edildiği için burada tanımlanıyor
    AgentAddClientView,  # Yeni müşteri ekleme view'ı eklendi
)
from django.contrib.auth.views import LogoutView # Django'nun hazır çıkış görünümü

app_name = 'accounts' # Bu uygulama için URL'lerin isim alanını (namespace) belirler

urlpatterns = [
    # Kullanıcı kimlik doğrulama ile ilgili URL'ler
    path('kayit/', SignUpView.as_view(), name='signup'), # Yeni kullanıcı kayıt sayfası
    path('giris/', CustomLoginView.as_view(), name='login'), # Özel giriş sayfası
    path('cikis/', LogoutView.as_view(), name='logout'), # Kullanıcı oturumunu kapatma işlemi
    path('profil/', ProfileView.as_view(), name='profile'), # Kullanıcı profili görüntüleme ve güncelleme sayfası
    
    # Müşteri temsilcilerine özel yönetim sayfası
    path('musteri-yonetimi/', AgentClientManagementView.as_view(), name='agent_client_management'), 

    # Müşteri temsilcisi yeni müşteri ekleme
    path('musteri-ekle/', AgentAddClientView.as_view(), name='agent_add_client'),
    
    # Uzmanlar için özel panel sayfası
    # "_navbar.html" dosyanızdaki 'accounts:uzman_panosu' URL'sine uygun olarak tanımlanmıştır.
    path('uzman-paneli/', ExpertDashboardView.as_view(), name='uzman_panosu'), 
]
