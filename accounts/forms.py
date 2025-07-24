# accounts/forms.py
from django import forms
from django.contrib.auth.forms import (
    UserCreationForm,
    AuthenticationForm
)
from .models import CustomUser

class SignUpForm(UserCreationForm):
    """
    Yeni kullanıcı kaydı için kullanılan form.
    Django'nun varsayılan UserCreationForm'unu genişletir.
    """
    class Meta:
        model = CustomUser
        # UserCreationForm, 'password1' ve 'password2' alanlarını otomatik olarak ekler,
        # bu yüzden fields listesine dahil edilmelerine gerek yoktur.
        # Ancak, sizin mevcut kullanımınız da hata vermediği için bırakılabilir.
        fields = ('username', 'email', 'first_name', 'last_name', 'phone')
        labels = {
            'username': 'Kullanıcı Adı',
            'email': 'E-Posta',
            'first_name': 'Ad',
            'last_name': 'Soyad',
            'phone': 'Telefon'
        }
        # Bootstrap uyumluluğu için widget'lar eklenebilir,
        # ancak Crispy Forms kullanıyorsanız bu gerekli olmayabilir.
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Örn: 5xx xxx xxxx'})
        }

class CustomLoginForm(AuthenticationForm):
    """
    Kullanıcı giriş işlemi için kullanılan form.
    Django'nun varsayılan AuthenticationForm'unu genişletir.
    """
    # "Beni Hatırla" özelliği için özel bir alan eklenmiştir.
    remember_me = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Beni Hatırla'
    )

    # AuthenticationForm'un varsayılan alanlarına (username, password) Bootstrap sınıfı eklemek için
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['password'].widget.attrs.update({'class': 'form-control'})


class CustomUserUpdateForm(forms.ModelForm):
    """
    Kullanıcı profil bilgilerini güncellemek için kullanılan form.
    """
    class Meta:
        model = CustomUser
        # Kullanıcının profil sayfasında güncelleyebileceği alanlar.
        # Şifre veya kullanıcı tipi gibi hassas bilgiler burada güncellenmemelidir.
        fields = ['first_name', 'last_name', 'email', 'phone'] 
        labels = {
            'first_name': 'Ad',
            'last_name': 'Soyad',
            'email': 'E-Posta',
            'phone': 'Telefon',
        }
        widgets = {
            # Bootstrap stilini otomatik uygulamak için 'form-control' sınıfını ekliyoruz.
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Örn: 5xx xxx xxxx'}),
        }