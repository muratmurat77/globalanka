from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from decimal import Decimal


class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = [
        ('admin', _('Yönetici')),
        ('expert', _('Uzman')),
        ('agent', _('Müşteri Temsilcisi')),
        ('client', _('Müşteri')),
    ]

    phone = models.CharField(
        max_length=15,
        blank=True,
        verbose_name=_('Telefon'),
        help_text=_('Örn: 5551234567')
    )

    user_type = models.CharField(
        max_length=10,
        choices=USER_TYPE_CHOICES,
        default='client',
        verbose_name=_('Kullanıcı Türü')
    )

    class Meta:
        verbose_name = _('Kullanıcı')
        verbose_name_plural = _('Kullanıcılar')


class Expert(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='expert_profile')

    specialization = models.CharField(
        max_length=100,
        verbose_name=_('Uzmanlık Alanı')
    )

    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.30'),
        verbose_name=_('Komisyon Oranı')
    )

    def __str__(self):
        return self.get_display_name()

    def get_display_name(self):
        display_name = self.user.get_full_name() or self.user.username
        return f"Dr. {display_name} - {self.specialization}"

    def save(self, *args, **kwargs):
        if self.commission_rate is None or self.commission_rate == Decimal('0.00'):
            self.commission_rate = self._meta.get_field('commission_rate').default
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _('Uzman')
        verbose_name_plural = _('Uzmanlar')


class CustomerAgent(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='agent_profile')

    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.15'),
        verbose_name=_('Komisyon Oranı')
    )

    assigned_clients = models.ManyToManyField(
        CustomUser,
        blank=True,
        related_name='agents',
        limit_choices_to={'user_type': 'client'},
        verbose_name=_('Atanmış Müşteriler')
    )

    ust_temsilci = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='alt_temsilciler',
        verbose_name=_('Üst Temsilci')
    )

    alt_temsilci_komisyon_orani = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.05'),
        verbose_name=_('Alt Temsilci Komisyon Oranı')
    )

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({_('Temsilci')})"

    def save(self, *args, **kwargs):
        if self.commission_rate is None or self.commission_rate == Decimal('0.00'):
            self.commission_rate = self._meta.get_field('commission_rate').default
        if self.alt_temsilci_komisyon_orani is None or self.alt_temsilci_komisyon_orani == Decimal('0.00'):
            self.alt_temsilci_komisyon_orani = self._meta.get_field('alt_temsilci_komisyon_orani').default
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _('Müşteri Temsilcisi')
        verbose_name_plural = _('Müşteri Temsilcileri')

    def get_alt_temsilci_kazanci(self):
        toplam_kazanc = Decimal('0.00')
        for alt_temsilci in self.alt_temsilciler.all():
            for musteri in alt_temsilci.assigned_clients.all():
                # Bu müşteriye ait işlemler üzerinden hesaplama yapılmalı
                islem_listesi = getattr(musteri, 'islem_set', None)
                if islem_listesi:
                    for islem in islem_listesi.all():
                        toplam_kazanc += islem.tutar * self.alt_temsilci_komisyon_orani
        return toplam_kazanc
