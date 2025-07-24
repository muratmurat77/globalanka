# appointments/forms.py

from django import forms
from .models import Appointment, ExpertAvailability, ExpertHoliday 
from accounts.models import CustomUser, Expert, CustomerAgent
from django.utils import timezone
from datetime import datetime, timedelta 

class AppointmentForm(forms.ModelForm):
    """
    Randevu oluşturma ve güncelleme için kullanılan model formu.
    Kullanıcı rolüne göre (admin, agent, client) alanların görünürlüğünü, 
    queryset'lerini ve ilk değerlerini dinamik olarak ayarlar.
    Ayrıca randevu tarihi ve saati için detaylı validasyonlar içerir.
    """
    client = forms.ModelChoiceField(
        queryset=CustomUser.objects.none(), # Başlangıçta boş, __init__ içinde role göre doldurulacak
        label="Müşteri",
        required=True, 
        empty_label="--- Bir Müşteri Seçin ---", 
        widget=forms.Select(attrs={'class': 'form-select'}) 
    )

    expert = forms.ModelChoiceField(
        queryset=Expert.objects.all().select_related('user').order_by('user__first_name', 'user__last_name'),
        label="Doktor",
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    service_type = forms.ChoiceField(
        choices=Appointment.SERVICE_CHOICES,
        label="Uygulama / Hizmet Tipi",
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    date = forms.DateTimeField(
        label="Randevu Tarihi ve Saati",
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control datetimepicker-input'}),
        required=True 
    )

    status = forms.ChoiceField(
        choices=Appointment.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Durum",
        required=False, # Durum alanı zorunlu olmamalı, varsayılan değeri var
        initial='pending' # Varsayılan olarak 'beklemede'
    )
    
    payment_status = forms.BooleanField(
        label="Ödeme Durumu",
        required=False, # Ödeme durumu zorunlu değil
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = Appointment
        fields = ['client', 'expert', 'service_type', 'date', 'notes', 'status', 'payment_status', 'amount']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
        }

    def __init__(self, *args, user=None, **kwargs):
        """
        Formu başlatırken kullanıcının rolüne göre alanları dinamik olarak ayarlar.
        """
        self.user = user 
        super().__init__(*args, **kwargs)

        # Uzman seçeneğinin görünümünü düzenler (Doktorun tam adını gösterir)
        self.fields['expert'].label_from_instance = lambda obj: obj.get_display_name()
        
        # Admin olmayan (veya staff olmayan) kullanıcılar için bazı alanları gizler
        if self.user and self.user.user_type != 'admin' and not self.user.is_staff:
            self.fields['status'].widget = forms.HiddenInput()
            self.fields['status'].required = False
            self.fields['payment_status'].widget = forms.HiddenInput()
            self.fields['payment_status'].required = False
            self.fields['amount'].widget = forms.HiddenInput()
            self.fields['amount'].required = False

            # Eğer randevu güncelleniyorsa, gizli alanların ilk değerlerini mevcut randevudan alır
            if self.instance.pk:
                # `self.instance` varsa, yani bir mevcut randevu güncelleniyorsa
                # Gizli olan alanların ilk değerlerini (initial) ayarlarız ki, 
                # form kaydedildiğinde bu değerler kaybolmasın.
                self.fields['status'].initial = self.instance.status
                self.fields['payment_status'].initial = self.instance.payment_status
                self.fields['amount'].initial = self.instance.amount

        # Kullanıcı rolüne göre 'client' alanı queryset'ini ve widget'ını ayarlar
        if self.user:
            user_type = self.user.user_type

            if user_type == 'admin' or self.user.is_staff:
                # Adminler tüm müşterileri seçebilir
                self.fields['client'].queryset = CustomUser.objects.filter(user_type='client').order_by('first_name', 'last_name')
                self.fields['client'].label_from_instance = lambda obj: obj.get_full_name() or obj.username
            elif user_type == 'agent':
                # Temsilciler sadece kendilerine atanmış müşterileri seçebilir
                try:
                    agent_profile = self.user.agent_profile
                    if not agent_profile.assigned_clients.exists():
                        # Eğer temsilciye atanmış müşteri yoksa, alanı gizle
                        self.fields['client'].widget = forms.HiddenInput()
                        self.fields['client'].required = False
                        self.fields['client'].label = '' # Etiketi gizle
                        self.fields['client'].help_text = "Size atanmış hiçbir müşteri bulunmamaktadır."
                    else:
                        self.fields['client'].queryset = agent_profile.assigned_clients.order_by('first_name', 'last_name')
                        self.fields['client'].label_from_instance = lambda obj: obj.get_full_name() or obj.username
                except CustomerAgent.DoesNotExist:
                    # Eğer temsilci profilinin kendisi yoksa
                    self.fields['client'].widget = forms.HiddenInput()
                    self.fields['client'].required = False
                    self.fields['client'].label = '' 
                    self.fields['client'].help_text = "Müşteri temsilcisi profiliniz bulunamadı."
            elif user_type == 'client':
                # Müşteriler sadece kendileri için randevu oluşturabilir, bu yüzden müşteri alanını gizle ve varsayılan olarak kendini ata
                self.fields['client'].initial = self.user.pk 
                self.fields['client'].queryset = CustomUser.objects.filter(pk=self.user.pk) 
                self.fields['client'].widget = forms.HiddenInput() 
                self.fields['client'].required = False 
                self.fields['client'].label = '' 
            else: # Diğer kullanıcı tipleri (örn. Expert) için müşteri alanı gizli
                self.fields['client'].widget = forms.HiddenInput()
                self.fields['client'].required = False
                self.fields['client'].label = '' 
        
        # Eğer form bir mevcut objeyi (instance) güncelliyorsa ve client alanı görünürse, başlangıç değerini ayarla
        if self.instance and self.instance.pk:
            if not isinstance(self.fields['client'].widget, forms.HiddenInput):
                self.fields['client'].initial = self.instance.client
            self.fields['expert'].initial = self.instance.expert
            self.fields['service_type'].initial = self.instance.service_type
            if self.instance.date:
                # DateTimeInput için tarih formatı 'YYYY-MM-DDTHH:MM' olmalı
                self.fields['date'].initial = self.instance.date.strftime('%Y-%m-%dT%H:%M')
            self.fields['notes'].initial = self.instance.notes
            if self.instance.amount:
                self.fields['amount'].initial = self.instance.amount

    def clean_date(self):
        """
        Seçilen tarihin geçmiş bir tarih veya şu anki zamandan önceki bir zaman olup olmadığını kontrol eder.
        """
        selected_date = self.cleaned_data.get('date')
        
        if selected_date:
            # Geçmiş tarihler veya şu andan önceki anlar için hata kontrolü
            # Küçük bir gecikme payı (1 saniye) eklenerek tam şu anı geçersiz kılmaktan kaçınılır.
            if selected_date < timezone.now() - timedelta(seconds=1): 
                raise forms.ValidationError("Geçmiş bir tarih veya şu anki zamandan önceki bir zaman seçemezsiniz.")
        
        return selected_date

    def clean(self):
        """
        Formun tüm alanları temizlendikten sonra ek validasyonlar yapar:
        - Uzman müsaitliği
        - Uzman tatilleri/izinleri
        - Aynı uzmana aynı saate çakışan randevu olup olmadığı
        - Gerekli alanların doldurulup doldurulmadığı
        """
        cleaned_data = super().clean()
        expert = cleaned_data.get('expert')
        date = cleaned_data.get('date')
        client = cleaned_data.get('client')
        service_type = cleaned_data.get('service_type')

        # Tüm temel alanlar mevcutsa validasyona devam et
        if expert and date and client and service_type:
            selected_day_of_week = date.weekday() # Haftanın gününü sayı olarak alır (0=Pazartesi)
            selected_time = date.time()

            # 1. Uzman müsaitliği kontrolü
            availabilities = ExpertAvailability.objects.filter(
                expert=expert,
                day_of_week=selected_day_of_week,
                start_time__lte=selected_time, # Seçilen zaman başlangıç zamanından büyük veya eşit olmalı
                end_time__gt=selected_time     # Seçilen zaman bitiş zamanından küçük olmalı
            )
            if not availabilities.exists():
                self.add_error('date', "Uzman, seçilen gün ve saatte müsait değil. Lütfen farklı bir zaman seçin.")

            # 2. Uzman tatil/izin kontrolü
            holidays = ExpertHoliday.objects.filter(
                expert=expert,
                start_date__lte=date.date(), # Seçilen tarih tatil başlangıcından büyük veya eşit olmalı
                end_date__gte=date.date()    # Seçilen tarih tatil bitişinden küçük veya eşit olmalı
            )
            if holidays.exists():
                self.add_error('date', "Uzman, seçilen tarihte izinli veya tatildedir. Lütfen farklı bir tarih seçin.")

            # 3. Randevu çakışması kontrolü (aynı uzman, aynı tarih ve saat, 'beklemede' veya 'onaylandı' durumunda)
            query = Appointment.objects.filter(
                expert=expert, 
                date=date, 
                status__in=['confirmed', 'pending']
            )
            if self.instance and self.instance.pk: # Eğer mevcut bir randevu güncelleniyorsa, kendisini kontrol dışı bırak
                query = query.exclude(pk=self.instance.pk)
            
            if query.exists():
                self.add_error('date', "Bu uzmanın bu tarih ve saate zaten bir randevusu bulunmaktadır. Lütfen farklı bir saat seçiniz.")
        
        # Temel alanların boş olup olmadığı kontrolü (widget HiddenInput değilse)
        # Eğer alan gizliyse (kullanıcı tarafından girilmiyorsa) bu kontrolü yapmaya gerek yoktur.
        elif not client and not isinstance(self.fields['client'].widget, forms.HiddenInput):
            self.add_error('client', "Lütfen bir müşteri seçin.")
        
        elif not expert:
            self.add_error('expert', "Lütfen bir doktor seçin.")
            
        elif not date:
            self.add_error('date', "Lütfen randevu saatini seçin.")
        
        elif not service_type:
            self.add_error('service_type', "Lütfen bir hizmet tipi seçin.")

        return cleaned_data
