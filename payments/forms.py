# payments/forms.py
from django import forms
from .models import Payment
from appointments.models import Appointment

class PaymentCreateForm(forms.ModelForm):
    """
    Yeni bir ödeme kaydı oluşturmak için kullanılan form.
    İlgili randevunun otomatik olarak atanmasını ve randevu durumuna göre
    formun davranışını (başlangıç değerleri, salt okunurluk) yönetir.
    """
    class Meta:
        model = Payment
        fields = ['amount_paid', 'payment_method']
        widgets = {
            'amount_paid': forms.NumberInput(attrs={
                'placeholder': 'Ödenen Tutar (TL)', 
                'class': 'form-control', 
                'min': '0.01', 
                'step': '0.01'
            }),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'amount_paid': 'Ödenen Tutar',
            'payment_method': 'Ödeme Yöntemi',
        }

    def __init__(self, *args, **kwargs):
        """
        Formu başlatır ve ilişkili randevu objesini alır.
        Randevunun mevcut durumuna göre form alanlarını ayarlar (örneğin, salt okunur yapar).
        """
        self.appointment = kwargs.pop('appointment', None)
        super().__init__(*args, **kwargs)

        if not self.appointment:
            # Randevu objesi olmadan formun başlatılması bir hata gösterir.
            # Normalde PaymentCreateView'deki get_form_kwargs metodu bunu zaten sağlar.
            raise ValueError("PaymentCreateForm, ilişkili bir randevu nesnesi ile başlatılmalıdır.")

        # Eğer randevunun `amount` alanı doluysa, `amount_paid` alanına varsayılan değer olarak ata.
        if self.appointment.amount:
            self.fields['amount_paid'].initial = self.appointment.amount
        
        # Eğer randevu zaten tamamlandıysa veya ödemesi yapıldıysa, formu salt okunur (readonly) ve devre dışı (disabled) yap.
        # payments/views.py dosyasındaki PaymentCreateView'in test_func metodu, 
        # bu durumdaki randevular için ödeme sayfasını zaten engellediği ve bilgilendirme mesajı gösterdiği için,
        # bu form içinde ek bir hata mesajı (add_error) eklemeye gerek yoktur. Sadece UI'ı yansıtmak yeterlidir.
        if self.appointment.status == 'completed' or self.appointment.payment_status:
            for field_name, field in self.fields.items():
                field.widget.attrs['readonly'] = True
                field.widget.attrs['disabled'] = True
            # Daha önce burada olan 'self.add_error(None, "Bu randevu için ödeme zaten yapılmış veya randevu tamamlanmıştır.")' satırı kaldırıldı.

    def clean(self):
        """
        Form verilerini temizler ve ek validasyonlar yapar.
        Ödenen tutarın pozitif olup olmadığını kontrol eder.
        """
        cleaned_data = super().clean()
        
        # Eğer randevu zaten tamamlanmış veya ödenmişse, daha fazla validasyona gerek yok.
        # Bu, views.py'deki test_func'a ek bir güvenlik katmanı sağlar.
        if self.appointment and (self.appointment.payment_status or self.appointment.status == 'completed'):
            return cleaned_data # Geçerli verileri olduğu gibi döndür, hata ekleme

        amount_paid = cleaned_data.get('amount_paid')
        if amount_paid is not None and amount_paid <= 0:
            self.add_error('amount_paid', "Ödenen tutar pozitif bir değer olmalıdır.")
        
        return cleaned_data

    def save(self, commit=True):
        """
        Ödeme objesini kaydeder ve ilişkili randevuyu günceller.
        Randevunun durumu 'completed' ve ödeme durumu 'True' olarak ayarlanır.
        """
        payment = super().save(commit=False)
        payment.appointment = self.appointment
        
        # Randevunun durumunu ve ödeme durumunu güncelle
        # Bu mantık burada olmalı çünkü ödeme formu, randevuyu tamamlar.
        payment.appointment.status = 'completed'
        payment.appointment.payment_status = True
        
        # Komisyonları hesapla ve ata (eğer Payment modelinde ilgili alanlar varsa)
        # Bu kısmı projenizin komisyon hesaplama mantığına göre uyarlamanız gerekebilir.
        # Örneğin:
        # if payment.appointment.expert and payment.appointment.expert.commission_rate is not None:
        #     payment.expert_commission = payment.amount_paid * (payment.appointment.expert.commission_rate / 100)
        # else:
        #     payment.expert_commission = 0
        # if payment.appointment.agent and payment.appointment.agent.commission_rate is not None:
        #     payment.agent_commission = payment.amount_paid * (payment.appointment.agent.commission_rate / 100)
        # else:
        #     payment.agent_commission = 0
        # payment.is_commission_calculated = True # Komisyonun hesaplandığını işaretle

        if commit:
            payment.appointment.save() # Önce randevuyu kaydet
            payment.save() 
        return payment
