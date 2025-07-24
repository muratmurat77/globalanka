# accounts/apps.py

from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = 'Hesap Yönetimi'  # Admin panelde görünecek isim

    def ready(self):
        """
        Uygulama hazır olduğunda sinyal dosyasını içe aktarır.
        Bu, sinyallerin otomatik olarak bağlanmasını sağlar.
        """
        import accounts.signals 
        # accounts.signals dosyasının içeriği yüklendiğinde,
        # @receiver dekoratörleri otomatik olarak sinyalleri Django'ya kaydeder.
