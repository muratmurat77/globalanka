from accounts.models import CustomUser
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView, DetailView, ListView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django import forms
from django.contrib.auth import get_user_model
# Müşteri temsilcisi için müşteri ekleme formu
class AgentAddClientForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ['username', 'first_name', 'last_name', 'email', 'phone']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
        }
# Müşteri temsilcisi kendi müşterisini ekleyebilsin
class AgentAddClientView(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, CreateView):
    model = CustomUser
    form_class = AgentAddClientForm
    template_name = 'accounts/agent_add_client.html'
    success_url = reverse_lazy('accounts:agent_client_management')
    success_message = "Müşteri başarıyla eklendi ve size atandı."

    def test_func(self):
        return self.request.user.user_type == 'agent'

    def form_valid(self, form):
        # Yeni müşteri oluşturuluyor
        user = form.save(commit=False)
        user.user_type = 'client'
        from django.utils.crypto import get_random_string
        random_password = get_random_string(10)
        user.set_password(random_password) # Şifreyi rastgele oluştur
        user.save()
        # Otomatik olarak ekleyen temsilciye ata
        agent_profile = self.request.user.agent_profile
        agent_profile.assigned_clients.add(user)
        agent_profile.save()
        return super().form_valid(form)
# accounts/views.py

from django.views.generic import CreateView, UpdateView, DetailView, ListView, TemplateView
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from .models import CustomUser, Expert, CustomerAgent
from .forms import SignUpForm, CustomUserUpdateForm
from django.db.models import ObjectDoesNotExist, Sum
from django.shortcuts import render, redirect 
from django.contrib import messages 

from django.utils import timezone
from datetime import timedelta

from appointments.models import Appointment
from payments.models import Payment

class CustomLoginView(SuccessMessageMixin, LoginView):
    """
    Özel giriş görünümü. Başarılı giriş sonrası mesaj gösterir ve varsayılan şablonu kullanır.
    """
    template_name = 'accounts/login.html'
    success_message = "Başarıyla giriş yaptınız!"
    extra_context = {
        'title': 'Giriş Yap'
    }

class SignUpView(SuccessMessageMixin, CreateView):
    """
    Yeni kullanıcı kaydı görünümü. Başarılı kayıt sonrası giriş sayfasına yönlendirir.
    """
    model = CustomUser
    form_class = SignUpForm
    template_name = 'accounts/signup.html'
    success_url = reverse_lazy('accounts:login')
    success_message = "Kaydınız başarıyla oluşturuldu! Giriş yapabilirsiniz."

class ProfileView(LoginRequiredMixin, UpdateView):
    """
    Kullanıcının kendi profil bilgilerini görüntülemesini ve güncellemesini sağlar.
    Kullanıcının rolüne göre (müşteri, uzman, temsilci, admin) ek profil bilgilerini gösterir.
    """
    model = CustomUser
    form_class = CustomUserUpdateForm
    template_name = 'accounts/profile.html'
    success_url = reverse_lazy('accounts:profile')
    success_message = "Profil bilgileriniz başarıyla güncellendi!"

    def get_object(self, queryset=None):
        """Güncellenecek CustomUser objesini döndürür (mevcut kullanıcı)."""
        return self.request.user

    def get_context_data(self, **kwargs):
        """Şablon için ek bağlam verileri (kullanıcı rolü ve ilgili profil bilgileri) sağlar."""
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context['is_client'] = False
        context['is_expert'] = False
        context['is_agent'] = False
        context['is_admin'] = False

        if user.user_type == 'client':
            context['is_client'] = True
            try:
                # Müşteriye atanmış temsilciyi bulur (eğer varsa)
                assigned_agent = user.agents.first() 
                context['assigned_agent'] = assigned_agent
            except ObjectDoesNotExist:
                context['assigned_agent'] = None
            except Exception as e:
                # Geliştirme ortamında print kullanmak yerine, üretimde Django'nun logging sistemini tercih edin.
                print(f"Müşteri temsilcisi bulunurken hata oluştu: {e}") 
                context['assigned_agent'] = None
                
        elif user.user_type == 'expert':
            context['is_expert'] = True
            try:
                context['expert_profile'] = user.expert_profile 
            except ObjectDoesNotExist:
                context['expert_profile'] = None
            except Exception as e:
                print(f"Uzman profili bulunurken hata oluştu: {e}")
                context['expert_profile'] = None

        elif user.user_type == 'agent':
            context['is_agent'] = True
            try:
                context['agent_profile'] = user.agent_profile
            except ObjectDoesNotExist:
                context['agent_profile'] = None
            except Exception as e:
                print(f"Temsilci profili bulunurken hata oluştu: {e}")
                context['agent_profile'] = None
                
        elif user.user_type == 'admin':
            context['is_admin'] = True

        return context


class AgentClientManagementView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Müşteri temsilcilerine atanan müşterileri ve onların yaklaşan randevularını listeler.
    Sadece 'agent' rolündeki kullanıcılar erişebilir.
    """
    template_name = 'accounts/agent_client_management.html'
    context_object_name = 'clients'
    paginate_by = 10 # Sayfalama ekleyebiliriz, eğer müşteri sayısı çok artarsa

    def test_func(self):
        """Kullanıcının 'agent' rolünde olup olmadığını kontrol eder."""
        return self.request.user.user_type == 'agent'
    
    def handle_no_permission(self):
        """Yetkisiz erişimde kullanıcıyı ana sayfaya yönlendirir ve hata mesajı gösterir."""
        messages.error(self.request, "Bu sayfayı görüntülemek için yetkiniz bulunmamaktadır.")
        return redirect(reverse_lazy('home')) 

    def get_queryset(self):
        """Mevcut temsilcinin atanmış müşterilerini getirir."""
        if self.request.user.user_type == 'agent':
            try:
                agent_profile = self.request.user.agent_profile
                return agent_profile.assigned_clients.all().order_by('first_name', 'last_name')
            except ObjectDoesNotExist:
                messages.warning(self.request, "Müşteri temsilcisi profiliniz bulunamadı veya atanmış müşteriniz yok.")
                return CustomUser.objects.none()
        return CustomUser.objects.none()

    def get_context_data(self, **kwargs):
        """Şablon için ek bağlam verileri (yaklaşan randevular) sağlar."""
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['title'] = 'Müşteri Yönetimi'

        if user.user_type == 'agent':
            try:
                agent_profile = user.agent_profile
                now = timezone.now()
                # Sonraki 7 gün içinde olan ve bu temsilcinin müşterilerine ait bekleyen veya onaylanmış randevular
                context['upcoming_appointments'] = Appointment.objects.filter(
                    client__in=agent_profile.assigned_clients.all(), # Temsilciye atanmış müşteriler
                    date__gte=now,
                    date__lt=now + timedelta(days=7), # Sonraki 7 gün içinde
                    status__in=['pending', 'confirmed'] # Sadece bekleyen veya onaylanmış randevular
                ).select_related('client', 'expert__user').order_by('date') # İlişkili objeleri önceden yükle
            except CustomerAgent.DoesNotExist:
                context['upcoming_appointments'] = []
            except Exception as e:
                # Hata ayıklama için bu tür print ifadeleri faydalıdır, ancak üretimde logging kullanılmalıdır.
                print(f"Yaklaşan randevular alınırken hata oluştu: {e}")
                context['upcoming_appointments'] = []
        else:
            context['upcoming_appointments'] = [] 

        return context

class ExpertDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    Uzmanların kendi panellerini görüntülemesini sağlar.
    Profil bilgileri, yaklaşan randevuları ve kazanılan komisyon özetini içerir.
    Sadece 'expert' veya 'admin' rolündeki kullanıcılar bu sayfaya erişebilir.
    """
    template_name = 'accounts/expert_dashboard.html' 

    def test_func(self):
        """Kullanıcının 'expert' veya 'admin' rolünde olup olmadığını kontrol eder."""
        return self.request.user.user_type == 'expert' or self.request.user.user_type == 'admin'

    def handle_no_permission(self):
        """Yetkisiz erişimde kullanıcıyı ana sayfaya yönlendirir ve hata mesajı gösterir."""
        messages.error(self.request, "Bu sayfaya erişim yetkiniz bulunmamaktadır.")
        return redirect(reverse_lazy('home'))

    def get_context_data(self, **kwargs):
        """Şablon için bağlam verileri (uzman profili, yaklaşan randevular, toplam komisyon) sağlar."""
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context['title'] = 'Uzman Paneli'

        if user.user_type == 'expert':
            try:
                expert_profile = user.expert_profile
                context['expert_profile'] = expert_profile
                
                now = timezone.now()
                local_now = timezone.localtime(now) # Yerel saat dilimine dönüştür

                # Uzmanın sonraki 30 gün içindeki bekleyen veya onaylanmış randevuları
                context['upcoming_appointments'] = Appointment.objects.filter(
                    expert=expert_profile,
                    date__gte=local_now, 
                    date__lt=local_now + timedelta(days=30), 
                    status__in=['pending', 'confirmed'] 
                ).select_related('client', 'agent__user').order_by('date')

                # Uzmanın toplam kazanılan komisyonunu Payment modelinden çekmek için
                # is_commission_calculated=True olan ödemelerdeki expert_commission toplamı
                total_commission = Payment.objects.filter(
                    appointment__expert=expert_profile,
                    is_commission_calculated=True 
                ).aggregate(Sum('expert_commission'))['expert_commission__sum'] or 0
                context['total_commission'] = total_commission
                
            except Expert.DoesNotExist:
                messages.warning(self.request, "Uzman profiliniz bulunamadı.")
                context['expert_profile'] = None
                context['upcoming_appointments'] = []
                context['total_commission'] = 0
            except Exception as e:
                print(f"Uzman paneli verileri yüklenirken bir hata oluştu: {e}") # Üretimde logging kullanın
                messages.error(self.request, f"Uzman paneli verileri yüklenirken bir hata oluştu: {e}")
                context['expert_profile'] = None
                context['upcoming_appointments'] = []
                context['total_commission'] = 0
        elif user.user_type == 'admin': # Adminler için genel bakış
            context['upcoming_appointments'] = Appointment.objects.filter(
                date__gte=timezone.localtime(timezone.now()), 
                date__lt=timezone.localtime(timezone.now()) + timedelta(days=30), 
                status__in=['pending', 'confirmed']
            ).select_related('expert__user', 'client', 'agent__user').order_by('date')
            context['total_commission'] = Payment.objects.aggregate(Sum('expert_commission'))['expert_commission__sum'] or 0 
        return context
