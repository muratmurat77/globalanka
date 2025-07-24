# appointments/models.py

from django.db import models
from accounts.models import CustomUser, Expert, CustomerAgent
from django.core.exceptions import ValidationError
from datetime import time, date
from django.utils import timezone

class Appointment(models.Model):
    """
    Klinikteki randevuları temsil eder.
    Bir danışanın bir uzmanla belirli bir tarihte randevu bilgilerini tutar.
    """
    STATUS_CHOICES = [
        ('pending', 'Onay Bekliyor'),
        ('confirmed', 'Onaylandı'),
        ('cancelled', 'İptal Edildi'),
        ('completed', 'Tamamlandı'),
    ]

    SERVICE_CHOICES = [
        ('filler', 'Dolgu Uygulaması'),
        ('botox', 'Botoks Uygulaması'),
        ('lip_blush', 'Dudak Renklendirme'),
        ('skin_care', 'Cilt Bakımı'),
        ('laser_hair_removal', 'Lazer Epilasyon'),
        ('chemical_peel', 'Kimyasal Peeling'),
        ('prp', 'PRP Tedavisi'),
        ('mesotherapy', 'Mezoterapi'),
        ('dermapen', 'Dermapen'),
        ('other', 'Diğer Hizmet'), 
    ]

    # İlişkili modeller
    expert = models.ForeignKey(
        Expert, 
        on_delete=models.CASCADE, 
        verbose_name="Uzman", 
        related_name="expert_appointments"
    )
    client = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        verbose_name="Müşteri", 
        related_name='client_appointments', 
        limit_choices_to={'user_type': 'client'} # Sadece 'client' tipi kullanıcılar seçilebilir
    )
    agent = models.ForeignKey(
        CustomerAgent, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Temsilci", 
        related_name='agent_appointments'
    )
    
    # Randevu bilgileri
    date = models.DateTimeField(verbose_name="Randevu Tarihi") # Randevu tarihi ve saati
    status = models.CharField(
        max_length=10, 
        choices=STATUS_CHOICES, 
        default='pending', 
        verbose_name="Durum"
    )
    payment_status = models.BooleanField(
        default=False, 
        verbose_name="Ödeme Durumu",
        help_text="Bu randevu için ödeme yapıldı mı?"
    )
    notes = models.TextField(blank=True, verbose_name="Notlar")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma Tarihi")
    
    # Randevu tutarı - Ödeme modülü tarafından doldurulacak veya güncellenecek
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        verbose_name="Randevu Ücreti",
        help_text="Bu randevu için müşteri tarafından ödenen veya belirlenen toplam tutar."
    )

    # Randevu ile ilişkili hizmet tipi
    service_type = models.CharField(
        max_length=50, 
        choices=SERVICE_CHOICES, 
        default='other', # Randevu oluşturulurken bir hizmet seçilmesi zorunlu olmalı, varsayılan 'Diğer'
        verbose_name="Hizmet Tipi",
        help_text="Bu randevuda sunulan hizmetin türü."
    )

    def clean(self):
        """
        Modelin veritabanına kaydedilmeden önce validasyonlarını kontrol eder.
        """
        # Aynı uzmana aynı tarih ve saatte birden fazla aktif randevu olamaz.
        # Kendi PK'sını hariç tutarak güncelleme işlemlerine izin verir.
        conflicting_appointments = Appointment.objects.filter(
            expert=self.expert,
            date=self.date,
            status__in=['confirmed', 'pending'] # Sadece onaylanmış veya bekleyen randevularla çakışmayı kontrol et
        )
        if self.pk: # Eğer randevu objesi zaten veritabanında varsa (güncelleme işlemi)
            conflicting_appointments = conflicting_appointments.exclude(pk=self.pk)

        if conflicting_appointments.exists():
            raise ValidationError("Bu uzmanın seçilen tarih ve saatte zaten onaylanmış veya bekleyen bir randevusu bulunmaktadır.")

        # Geçmiş bir tarih ve saate randevu oluşturulamaz.
        if self.date < timezone.now():
            raise ValidationError("Geçmiş bir tarih ve saate randevu oluşturulamaz.")

    class Meta:
        verbose_name = "Randevu"
        verbose_name_plural = "Randevular"
        ordering = ['-date'] # Randevuları tarihe göre azalan sırada sıralar
        # unique_together = ('expert', 'date') # Bu satır, `clean` metodundaki daha esnek kontrol nedeniyle gereksizleşti.
                                            # Eğer eklerseniz, uzman için aynı tarihte "completed" bile olsa başka randevu alınamaz.
                                            # Mevcut `clean` metodumuz daha spesifik kontrol sağlıyor.

    def __str__(self):
        """
        Randevu objesinin okunabilir string temsilini döndürür.
        """
        client_name = self.client.get_full_name() if self.client.get_full_name() else self.client.username
        expert_name = self.expert.user.get_full_name() if self.expert.user.get_full_name() else self.expert.user.username
        # Randevunun hizmet tipi ile birlikte daha açıklayıcı bir string döndür
        return f"{client_name} - Dr. {expert_name} ({self.date.strftime('%d.%m.%Y %H:%M')}) - {self.get_service_type_display()}"


class ExpertAvailability(models.Model):
    """
    Uzmanların haftalık müsaitliklerini tanımlar.
    """
    WEEKDAY_CHOICES = [
        (0, 'Pazartesi'),
        (1, 'Salı'),
        (2, 'Çarşamba'),
        (3, 'Perşembe'),
        (4, 'Cuma'),
        (5, 'Cumartesi'),
        (6, 'Pazar'),
    ]

    expert = models.ForeignKey(
        Expert, 
        on_delete=models.CASCADE, 
        verbose_name="Uzman", 
        related_name="availabilities"
    )
    day_of_week = models.IntegerField(
        choices=WEEKDAY_CHOICES, 
        verbose_name="Haftanın Günü"
    )
    start_time = models.TimeField(verbose_name="Başlangıç Saati")
    end_time = models.TimeField(verbose_name="Bitiş Saati")

    class Meta:
        verbose_name = "Uzman Müsaitlik"
        verbose_name_plural = "Uzman Müsaitlikleri"
        # Aynı uzman için aynı gün aynı müsaitlik aralığı olamaz
        unique_together = ('expert', 'day_of_week', 'start_time', 'end_time') 
        ordering = ['day_of_week', 'start_time']

    def clean(self):
        """
        Müsaitlik aralığının validasyonunu kontrol eder.
        """
        # Bitiş saati başlangıç saatinden sonra olmalı
        if self.start_time >= self.end_time:
            raise ValidationError("Bitiş saati, başlangıç saatinden sonra olmalıdır.")

        # Çakışan müsaitlik aralıkları kontrolü
        # Yeni aralık, mevcut bir aralığı kapsıyor veya onunla çakışıyor mu?
        conflicting_availabilities = ExpertAvailability.objects.filter(
            expert=self.expert,
            day_of_week=self.day_of_week,
            start_time__lt=self.end_time, # Başka bir müsaitliğin başlangıcı bu müsaitliğin bitişinden önce ise
            end_time__gt=self.start_time # Başka bir müsaitliğin bitişi bu müsaitliğin başlangıcından sonra ise
        )
        if self.pk: # Eğer obje zaten veritabanında varsa (güncelleme işlemi)
            conflicting_availabilities = conflicting_availabilities.exclude(pk=self.pk)

        if conflicting_availabilities.exists():
            raise ValidationError("Bu uzmanın seçilen gün için çakışan bir müsaitlik aralığı bulunmaktadır.")

    def __str__(self):
        return f"{self.expert.user.username} - {self.get_day_of_week_display()} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"


class ExpertHoliday(models.Model):
    """
    Uzmanların belirli tarihlerdeki tatil veya izin dönemlerini tanımlar.
    Bu tarihlerde randevu oluşturulmamalıdır.
    """
    expert = models.ForeignKey(
        Expert, 
        on_delete=models.CASCADE, 
        verbose_name="Uzman", 
        related_name="holidays"
    )
    start_date = models.DateField(verbose_name="Başlangıç Tarihi")
    end_date = models.DateField(verbose_name="Bitiş Tarihi")
    description = models.CharField(max_length=255, blank=True, null=True, verbose_name="Açıklama")

    class Meta:
        verbose_name = "Uzman Tatil/İzin"
        verbose_name_plural = "Uzman Tatil/İzinleri"
        ordering = ['start_date']

    def clean(self):
        """
        Tatil/izin tarihlerinin validasyonunu kontrol eder.
        """
        # Bitiş tarihi başlangıç tarihinden sonra veya eşit olmalı
        if self.start_date > self.end_date:
            raise ValidationError("Bitiş tarihi, başlangıç tarihinden sonra veya eşit olmalıdır.")

        # Çakışan tatil/izin tarihleri kontrolü
        # Yeni izin, mevcut bir izni kapsıyor veya onunla çakışıyor mu?
        conflicting_holidays = ExpertHoliday.objects.filter(
            expert=self.expert,
            start_date__lte=self.end_date, # Başka bir iznin başlangıcı bu iznin bitişinden önce veya eşitse
            end_date__gte=self.start_date  # Başka bir iznin bitişi bu iznin başlangıcından sonra veya eşitse
        )
        if self.pk: # Eğer obje zaten veritabanında varsa (güncelleme işlemi)
            conflicting_holidays = conflicting_holidays.exclude(pk=self.pk)

        if conflicting_holidays.exists():
            raise ValidationError("Bu uzmanın seçilen tarihlerde çakışan bir tatil/izin dönemi bulunmaktadır.")

    def __str__(self):
        return f"{self.expert.user.username} - Tatil: {self.start_date.strftime('%d.%m.%Y')} - {self.end_date.strftime('%d.%m.%Y')}"