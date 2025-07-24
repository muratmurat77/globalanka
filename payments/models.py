from django.db import models
from django.utils.translation import gettext_lazy as _
from appointments.models import Appointment
from accounts.models import Expert, CustomerAgent
from decimal import Decimal

class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('credit_card', _('Kredi Kartı')),
        ('bank_transfer', _('Banka Havalesi')),
        ('cash', _('Nakit')),
        ('other', _('Diğer')),
    ]

    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.CASCADE,
        related_name='payment',
        verbose_name=_('Randevu'),
        help_text=_('Bu ödemenin ilişkili olduğu randevu.')
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Ödenen Tutar'),
        help_text=_('Müşteri tarafından ödenen gerçek tutar.')
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='credit_card',
        verbose_name=_('Ödeme Yöntemi'),
        help_text=_('Ödemenin yapıldığı yöntem.')
    )
    payment_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Ödeme Tarihi'),
        help_text=_('Ödemenin kaydedildiği tarih ve saat.')
    )
    expert_commission = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Uzman Komisyonu'),
        help_text=_('Randevudan uzmana ödenecek komisyon tutarı.')
    )
    agent_commission = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Temsilci Komisyonu'),
        help_text=_('Randevudan temsilciye ödenecek komisyon tutarı.')
    )
    is_commission_calculated = models.BooleanField(
        default=False,
        verbose_name=_('Komisyon Hesaplandı mı?'),
        help_text=_('Komisyonların bu ödeme için hesaplanıp hesaplanmadığını belirtir.')
    )

    def __str__(self):
        service_type = self.appointment.get_service_type_display() if self.appointment.service_type else _("Bilinmiyor")
        return f"{self.appointment.client.get_full_name()} için ödeme ({self.amount_paid} TL) - {service_type}"

    class Meta:
        verbose_name = _('Ödeme')
        verbose_name_plural = _('Ödemeler')
        ordering = ['-payment_date']

    def calculate_commissions(self):
        """
        Randevu ile ilişkili Expert ve CustomerAgent'ın komisyonlarını hesaplar.
        Komisyon oranlarının yüzde değeri (örneğin 10.0 gibi) olarak saklandığı varsayılır.
        """
        if self.is_commission_calculated:
            # print(f"DEBUG: Komisyonlar zaten hesaplandı. Payment ID: {self.pk}") # Debug çıktısı kaldırıldı
            return

        expert = self.appointment.expert
        agent = self.appointment.agent

        if expert and expert.commission_rate is not None:
            # commission_rate artık DecimalField olduğu için doğrudan kullanılabilir
            self.expert_commission = self.amount_paid * (expert.commission_rate / Decimal('100'))
        else:
            self.expert_commission = Decimal('0.00')

        if agent and agent.commission_rate is not None:
            # commission_rate artık DecimalField olduğu için doğrudan kullanılabilir
            self.agent_commission = self.amount_paid * (agent.commission_rate / Decimal('100'))
        else:
            self.agent_commission = Decimal('0.00')
        
        self.is_commission_calculated = True

        # Debug çıktısı kaldırıldı
        # print(f"DEBUG: Komisyon hesaplanıyor - Payment ID: {self.pk if self.pk else 'Yeni Ödeme'}")
        # print(f"DEBUG: Ödenen Tutar: {self.amount_paid}")
        # print(f"DEBUG: Uzman: {expert.user.username if expert else 'Yok'}, Oran: {expert.commission_rate if expert else 'Yok'}")
        # print(f"DEBUG: Temsilci: {agent.user.username if agent else 'Yok'}, Oran: {agent.commission_rate if agent else 'Yok'}")
        # print(f"DEBUG: Hesaplanan Uzman Komisyonu: {self.expert_commission}")
        # print(f"DEBUG: Hesaplanan Temsilci Komisyonu: {self.agent_commission}")
        # print(f"DEBUG: is_commission_calculated ayarlandı: {self.is_commission_calculated}")

    def save(self, *args, **kwargs):
        """
        Ödeme kaydedilirken komisyonları otomatik olarak hesaplar.
        """
        is_new_object = not self.pk

        if is_new_object or not self.is_commission_calculated:
            self.calculate_commissions()
        elif self.pk:
            try:
                old_payment = Payment.objects.get(pk=self.pk)
                if self.amount_paid != old_payment.amount_paid:
                    # print(f"DEBUG: amount_paid değişti, komisyonlar yeniden hesaplanıyor. Payment ID: {self.pk}") # Debug çıktısı kaldırıldı
                    self.is_commission_calculated = False
                    self.calculate_commissions()
            except Payment.DoesNotExist:
                # print(f"DEBUG: Eski ödeme objesi bulunamadı, yeni gibi hesaplanıyor. Payment ID: {self.pk}") # Debug çıktısı kaldırıldı
                self.is_commission_calculated = False
                self.calculate_commissions()

        # Debug çıktısı kaldırıldı
        # print(f"DEBUG: Payment save metodu çağrıldı. ID: {self.pk if self.pk else 'Yeni'}. Kaydetmeden önce komisyonlar: Uzman={self.expert_commission}, Temsilci={self.agent_commission}, Hesaplandı mı?={self.is_commission_calculated}")
        
        super().save(*args, **kwargs)
        
        # Debug çıktısı kaldırıldı
        # print(f"DEBUG: Ödeme kaydedildi. Final Komisyonlar: Uzman={self.expert_commission}, Temsilci={self.agent_commission}, Hesaplandı mı?={self.is_commission_calculated}")
