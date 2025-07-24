# payments/views.py

from django.urls import reverse_lazy
from django.contrib import messages
from django.views.generic import CreateView, ListView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Sum, Q 
from django.http import JsonResponse
from datetime import datetime, timedelta, date
from django.utils import timezone 
from django.views.decorators.http import require_POST 
from django.contrib.auth.decorators import login_required, user_passes_test 
from django.contrib.messages.views import SuccessMessageMixin 
from django.db.models.functions import TruncMonth 
from decimal import Decimal 

from .models import Payment
from .forms import PaymentCreateForm
from appointments.models import Appointment
from accounts.models import Expert, CustomerAgent, CustomUser 

# --- Randevu İçin Ödeme Kaydetme Görünümü ---
class PaymentCreateView(LoginRequiredMixin, UserPassesTestMixin, SuccessMessageMixin, CreateView):
    """
    Belirli bir randevu için yeni bir ödeme kaydı oluşturur.
    Randevunun durumunu 'completed' ve ödeme durumunu 'True' olarak günceller.
    Sadece admin, ilgili temsilci veya ilgili uzman bu işlemi yapabilir.
    """
    model = Payment
    form_class = PaymentCreateForm
    template_name = 'payments/create_payment.html'
    context_object_name = 'payment'
    success_message = "Ödeme başarıyla kaydedildi ve randevu tamamlandı." 

    def get_success_url(self):
        """Başarılı ödeme sonrası yönlendirilecek URL'yi döndürür."""
        return reverse_lazy('appointments:list') 

    def get_form_kwargs(self):
        """Forma randevu objesini kwargs olarak gönderir."""
        kwargs = super().get_form_kwargs()
        appointment_pk = self.kwargs.get('pk')
        self.appointment = get_object_or_404(Appointment, pk=appointment_pk)
        kwargs['appointment'] = self.appointment 
        return kwargs

    def get_context_data(self, **kwargs):
        """Şablona randevu objesi ve formun salt okunur olup olmadığı bilgisini gönderir."""
        context = super().get_context_data(**kwargs)
        context['appointment'] = self.appointment 
        
        # Eğer randevu zaten tamamlandıysa veya ödendiyse, formu salt okunur yapar
        if self.appointment.status == 'completed' or self.appointment.payment_status:
            context['form_readonly'] = True
        else:
            context['form_readonly'] = False
        
        return context

    def form_valid(self, form):
        """
        Form geçerli olduğunda ödeme objesini kaydeder.
        PaymentCreateForm'un save metodu, Appointment objesini de güncelleyecektir.
        """
        return super().form_valid(form)
    
    def form_invalid(self, form):
        """Form geçerli olmadığında hata mesajı gösterir ve formu tekrar render eder."""
        messages.error(self.request, "Ödeme kaydedilirken bir hata oluştu. Lütfen formu kontrol edin.")
        return self.render_to_response(self.get_context_data(form=form))

    def test_func(self):
        """
        Kullanıcının bu işlemi yapmaya yetkisi olup olmadığını kontrol eder.
        Sadece admin, ilgili temsilci veya ilgili uzman bu işlemi yapabilir.
        Ayrıca, sadece tamamlanmamış/ödenmemiş randevular için işlem yapılabilir.
        """
        appointment_pk = self.kwargs.get('pk')
        appointment = get_object_or_404(Appointment, pk=appointment_pk)
        user = self.request.user
        
        can_access = False
        if user.user_type == 'admin':
            can_access = True
        # Kullanıcının agent_profile'ı varsa ve randevuyla ilgiliyse
        elif hasattr(user, 'agent_profile') and user.agent_profile:
            agent_profile = user.agent_profile
            if appointment.agent == agent_profile or \
               agent_profile.assigned_clients.filter(pk=appointment.client.pk).exists():
                can_access = True
        # Kullanıcının expert_profile'ı varsa ve randevuyla ilgiliyse
        elif hasattr(user, 'expert_profile') and user.expert_profile:
            # appointment.expert null olabilir, bu yüzden kontrol etmek önemli
            if appointment.expert and appointment.expert.user == user: 
                can_access = True
        
        # Eğer randevu zaten tamamlandıysa veya ödendiyse, yetkisini engelle
        if appointment.status == 'completed' or appointment.payment_status:
            messages.info(self.request, "Bu randevu zaten tamamlanmış ve ödemesi alınmıştır.")
            return False # Yetkilendirme başarısız
        
        return can_access

    def dispatch(self, request, *args, **kwargs):
        """Yetkilendirme kontrolü yapar ve yetkisiz kullanıcıları uygun sayfaya yönlendirir."""
        if not request.user.is_authenticated:
            return self.handle_no_permission() 

        return super().dispatch(request, *args, **kwargs)

# --- Tüm Ödemeleri Listeleme Görünümü (Admin İçin) ---
class PaymentListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Adminin sistemdeki tüm ödeme kayıtlarını filtreleyip görüntülemesini sağlar.
    Toplam gelir ve komisyon özetlerini de sunar.
    """
    model = Payment
    template_name = 'payments/list.html'
    context_object_name = 'payments'
    paginate_by = 20

    def get_queryset(self):
        """Ödeme listesini filtreleme parametrelerine göre döndürür."""
        queryset = super().get_queryset().select_related(
            'appointment__client',
            'appointment__expert__user', 
            'appointment__agent__user'
        ).order_by('-payment_date')
        
        # Filtreleme parametrelerini al
        expert_id = self.request.GET.get('expert')
        agent_id = self.request.GET.get('agent')
        service_type = self.request.GET.get('service_type')
        selected_month = self.request.GET.get('month') 
        selected_year = self.request.GET.get('year') 
        
        # Filtreleri uygula
        if expert_id:
            queryset = queryset.filter(appointment__expert__id=expert_id)
        if agent_id:
            queryset = queryset.filter(appointment__agent__id=agent_id)
        if service_type:
            queryset = queryset.filter(appointment__service_type=service_type)
        if selected_month: 
            queryset = queryset.filter(payment_date__month=selected_month)
        if selected_year:
            queryset = queryset.filter(payment_date__year=selected_year)

        return queryset

    def get_context_data(self, **kwargs):
        """Şablon için ek bağlam verileri (filtre seçenekleri ve toplamlar) sağlar."""
        context = super().get_context_data(**kwargs)
        context['experts'] = Expert.objects.all()
        context['agents'] = CustomerAgent.objects.all()
        context['service_choices'] = Appointment.SERVICE_CHOICES 



                # views.py içindeki PaymentListView.get_context_data fonksiyonunun sonuna ekle:
        if self.request.GET.get('agent'):
            try:
                agent_id = int(self.request.GET.get('agent'))
                parent_agent = CustomerAgent.objects.get(pk=agent_id)

                total_share_from_sub_agents = Decimal('0.00')
                for sub_agent in parent_agent.alt_temsilciler.all():
                    sub_agent_payments = Payment.objects.filter(
                        Q(appointment__agent=sub_agent) | Q(appointment__client__agents=sub_agent),
                        is_commission_calculated=True
                    )

                    for payment in sub_agent_payments:
                        total_share_from_sub_agents += payment.amount_paid * (parent_agent.alt_temsilci_komisyon_orani / Decimal('100'))
                context['total_sub_agent_commission'] = total_share_from_sub_agents
            except (CustomerAgent.DoesNotExist, ValueError):
                context['total_sub_agent_commission'] = Decimal('0.00')
        else:
            context['total_sub_agent_commission'] = None

        
        # Mevcut filtre değerlerini şablona göndererek formda korunmasını sağlar
        context['current_expert'] = self.request.GET.get('expert', '')
        context['current_agent'] = self.request.GET.get('agent', '')
        context['current_service_type'] = self.request.GET.get('service_type', '')
        context['current_month'] = self.request.GET.get('month', '') 
        context['current_year'] = self.request.GET.get('year', '')

        # Ay ve Yıl seçeneklerini oluştur
        months = [
            (1, 'Ocak'), (2, 'Şubat'), (3, 'Mart'), (4, 'Nisan'),
            (5, 'Mayıs'), (6, 'Haziran'), (7, 'Temmuz'), (8, 'Ağustos'),
            (9, 'Eylül'), (10, 'Ekim'), (11, 'Kasım'), (12, 'Aralık')
        ]
        context['months'] = months

        current_year = timezone.now().year
        years = [(y, str(y)) for y in range(current_year, current_year - 5, -1)]
        context['years'] = years
        
        # Toplam tutar ve komisyonları hesapla (geçerli queryset üzerinden)
        total_paid_amount = self.get_queryset().aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00') 
        total_expert_commission = self.get_queryset().aggregate(Sum('expert_commission'))['expert_commission__sum'] or Decimal('0.00') 
        total_agent_commission = self.get_queryset().aggregate(Sum('agent_commission'))['agent_commission__sum'] or Decimal('0.00') 

        context['total_paid_amount'] = total_paid_amount
        context['total_expert_commission'] = total_expert_commission
        context['total_agent_commission'] = total_agent_commission

        return context

    def test_func(self):
        """Sadece 'admin' rolündeki kullanıcıların bu sayfaya erişmesine izin verir."""
        return self.request.user.user_type == 'admin' 

# --- Uzman Komisyonlarını Listeleme Görünümü ---
class ExpertCommissionListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Uzmanların yalnızca kendilerine ait kazandıkları komisyonları görmesini sağlar.
    Adminlerin de bu listeyi görüntülemesine izin verir.
    """
    model = Payment
    template_name = 'payments/expert_commissions.html'
    context_object_name = 'commissions'
    paginate_by = 20

    def get_queryset(self):
        """Mevcut uzmanın komisyon ödemelerini döndürür."""
        user = self.request.user
        try:
            # Adminler tüm uzmanların komisyonlarını görebilir
            if user.user_type == 'admin':
                queryset = Payment.objects.filter(is_commission_calculated=True)
            # Kullanıcının expert_profile'ı varsa kendi komisyonlarını görsün
            elif hasattr(user, 'expert_profile') and user.expert_profile is not None: 
                expert_profile = user.expert_profile
                queryset = Payment.objects.filter(
                    appointment__expert=expert_profile,
                    is_commission_calculated=True 
                )
            else: # Expert profili yoksa veya yetkili değilse boş küme döndür (should not happen if test_func is correct)
                messages.warning(self.request, "Uzman profiliniz bulunamadı veya yetkiniz yok.")
                return Payment.objects.none()

            queryset = queryset.select_related('appointment__client', 'appointment__expert__user').order_by('-payment_date')
            return queryset
        except Expert.DoesNotExist:
            messages.warning(self.request, "Uzman profiliniz bulunamadı. Lütfen bir uzman profili oluşturun.")
            return Payment.objects.none()
        except Exception as e: # Diğer olası hataları yakalamak için genel bir except
            messages.error(self.request, f"Komisyonlar yüklenirken bir hata oluştu: {e}")
            return Payment.objects.none()


    def get_context_data(self, **kwargs):
        """Şablon için ek bağlam verileri (toplam komisyon) sağlar."""
        context = super().get_context_data(**kwargs)
        user = self.request.user
        total_commission = Decimal('0.00') # Başlangıç değeri

        # Toplam komisyonu, sadece kullanıcının kendi komisyonları üzerinden hesapla (admin değilse)
        # veya admin ise tüm expert komisyonlarını al.
        if user.user_type == 'admin':
            total_commission = self.get_queryset().aggregate(Sum('expert_commission'))['expert_commission__sum'] or Decimal('0.00')
        elif hasattr(user, 'expert_profile') and user.expert_profile is not None:
             total_commission = Payment.objects.filter(
                 appointment__expert=user.expert_profile,
                 is_commission_calculated=True
            ).aggregate(Sum('expert_commission'))['expert_commission__sum'] or Decimal('0.00')
        # else durumu için total_commission zaten Decimal('0.00') olarak ayarlandı.

        context['total_commission'] = total_commission
        context['title'] = f"Komisyonlarım ({self.request.user.get_full_name() or self.request.user.username})"
        return context

    def test_func(self):
        """
        Sadece 'admin' rolündeki kullanıcıların veya bir 'expert_profile'a sahip kullanıcıların
        bu sayfaya erişmesine izin verir. user_type'a bağlılık kaldırıldı.
        """
        user = self.request.user
        # Kullanıcı admin ise veya bir Expert profiline sahipse erişime izin ver
        return user.user_type == 'admin' or (hasattr(user, 'expert_profile') and user.expert_profile is not None)

# --- Temsilci Komisyonlarını Listeleme Görünümü ---
class AgentCommissionListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Temsilcilerin kendi atanan müşterileriyle ilgili randevuların komisyonlarını
    veya doğrudan kendilerine atanmış randevuların komisyonlarını görmesini sağlar.
    Adminlerin de bu listeyi görüntülemesine izin verir.
    """
    model = Payment
    template_name = 'payments/agent_commissions.html'
    context_object_name = 'commissions'
    paginate_by = 20

    def get_queryset(self):
        """Mevcut temsilcinin komisyon ödemelerini döndürür."""
        user = self.request.user
        try:
            if user.user_type == 'admin': # Adminler tüm temsilci komisyonlarını görebilir
                queryset = Payment.objects.filter(is_commission_calculated=True)
            # Kullanıcının agent_profile'ı varsa kendi komisyonlarını görsün
            elif hasattr(user, 'agent_profile') and user.agent_profile is not None: 
                agent_profile = user.agent_profile
                queryset = Payment.objects.filter(
                    Q(appointment__agent=agent_profile) | 
                    Q(appointment__client__agents=agent_profile), # Temsilcinin atanmış müşterilerine ait randevular
                    is_commission_calculated=True 
                )
            else: # Agent profili yoksa veya yetkili değilse boş küme döndür (should not happen if test_func is correct)
                messages.warning(self.request, "Müşteri temsilcisi profiliniz bulunamadı veya yetkiniz yok.")
                return Payment.objects.none()

            # Sorgu sonuçlarında mükerrer kayıtları önlemek için distinct() kullanın
            queryset = queryset.select_related('appointment__client', 'appointment__expert__user', 'appointment__agent__user').distinct().order_by('-payment_date')
            return queryset
        except CustomerAgent.DoesNotExist:
            messages.warning(self.request, "Müşteri temsilcisi profiliniz bulunamadı. Randevu listesi boş olabilir.")
            return Payment.objects.none()
        except Exception as e: # Diğer olası hataları yakalamak için genel bir except
            messages.error(self.request, f"Komisyonlar yüklenirken bir hata oluştu: {e}")
            return Payment.objects.none()


    def get_context_data(self, **kwargs):
        """Şablon için ek bağlam verileri (toplam komisyon) sağlar."""
        context = super().get_context_data(**kwargs)
        user = self.request.user
        total_commission = Decimal('0.00') # Başlangıç değeri

        # Toplam komisyonu, sadece kullanıcının kendi komisyonları üzerinden hesapla (admin değilse)
        # veya admin ise tüm agent komisyonlarını al.
        if user.user_type == 'admin':
            total_commission = self.get_queryset().aggregate(Sum('agent_commission'))['agent_commission__sum'] or Decimal('0.00')
        elif hasattr(user, 'agent_profile') and user.agent_profile is not None:
            total_commission = Payment.objects.filter(
                Q(appointment__agent=user.agent_profile) |
                Q(appointment__client__agents=user.agent_profile),
                is_commission_calculated=True
            ).aggregate(Sum('agent_commission'))['agent_commission__sum'] or Decimal('0.00')
        # else durumu için total_commission zaten Decimal('0.00') olarak ayarlandı.

        context['total_commission'] = total_commission
        context['title'] = f"Gelirlerim ({self.request.user.get_full_name() or self.request.user.username})"
        return context

    def test_func(self):
        """
        Sadece 'admin' rolündeki kullanıcıların veya bir 'agent_profile'a sahip kullanıcıların
        bu sayfaya erişmesine izin verir. user_type'a bağlılık kaldırıldı.
        """
        user = self.request.user
        # Kullanıcı admin ise veya bir CustomerAgent profiline sahipse erişime izin ver
        return user.user_type == 'admin' or (hasattr(user, 'agent_profile') and user.agent_profile is not None)

# --- Aylık Özet Görünümü (Admin İçin) ---
class MonthlySummaryView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Adminin aylık bazda toplam ödenen tutarları, uzman ve temsilci komisyonlarını
    ve kliniğin net kazancını görmesini sağlar.
    Bu görünüme uzman ve temsilciye göre filtreleme eklendi.
    """
    model = Payment
    template_name = 'payments/monthly_summary.html'
    context_object_name = 'monthly_data'

    def get_queryset(self):
        """
        Ay bazında ödeme özetlerini hesaplar ve döndürür.
        Filtreleme parametrelerini (uzman, temsilci) uygular.
        """
        # İlk olarak, genel queryset'i alalım
        queryset = Payment.objects.all()

        

        # Filtreleme parametrelerini al
        expert_id = self.request.GET.get('expert')
        agent_id = self.request.GET.get('agent')

        # Filtreleri uygula
        if expert_id:
            queryset = queryset.filter(appointment__expert__id=expert_id)
        if agent_id:
            queryset = queryset.filter(appointment__agent__id=agent_id)

        # Ardından, filtrelenmiş queryset üzerinden aylık özetleri grupla
        monthly_summary = queryset.annotate(
            month=TruncMonth('payment_date') 
        ).values('month').annotate(
            total_amount_paid=Sum('amount_paid'),
            total_expert_commission=Sum('expert_commission'),
            total_agent_commission=Sum('agent_commission')
        ).order_by('-month') 

        # Her bir aylık veri için 'net_profit' (net kar) hesaplamasını yapıyoruz
        for item in monthly_summary:
            item['net_profit'] = item['total_amount_paid'] - item['total_expert_commission'] - item['total_agent_commission']
        
        return monthly_summary

    def get_context_data(self, **kwargs):
        """Şablon için ek bağlam verileri (başlık, filtre seçenekleri) sağlar."""
        context = super().get_context_data(**kwargs)
        context['title'] = "Aylık Finansal Özet"

        # Filtreleme için uzman ve temsilci listelerini ekle
        context['experts'] = Expert.objects.all()
        context['agents'] = CustomerAgent.objects.all()

        # Mevcut filtre değerlerini şablona göndererek formda korunmasını sağlar
        context['current_expert'] = self.request.GET.get('expert', '')
        context['current_agent'] = self.request.GET.get('agent', '')
        
        return context

    def test_func(self):
        """Sadece 'admin' rolündeki kullanıcıların bu sayfaya erişmesine izin verir."""
        return self.request.user.user_type == 'admin' 

# --- Müşteri Temsilcisi Alt Temsilci Gelirleri Görünümü ---
def is_customer_agent(user):
    """Kullanıcının CustomerAgent rolünde olup olmadığını kontrol eder."""
    # Sadece user_type 'agent' olan ve agent_profile'ı olan kullanıcılar erişebilir.
    return user.is_authenticated and user.user_type == 'agent' and hasattr(user, 'agent_profile') and user.agent_profile is not None

@login_required
@user_passes_test(is_customer_agent, login_url=reverse_lazy('accounts:login')) # Yetkilendirme başarısız olursa login sayfasına yönlendir
def agent_sub_agent_revenue_dashboard(request): 
    """
    Giriş yapmış olan müşteri temsilcisinin kendi ve alt temsilci gelirlerini gösteren dashboard.
    """
    current_agent = get_object_or_404(CustomerAgent, user=request.user)
    
    # 1. Temsilcinin doğrudan kazancını hesapla
    # Kendi atadığı müşterilerin veya kendisine atanan randevuların komisyonları
    direkt_gelir = Payment.objects.filter(
        Q(appointment__agent=current_agent) |
        Q(appointment__client__agents=current_agent),
        is_commission_calculated=True
    ).aggregate(Sum('agent_commission'))['agent_commission__sum'] or Decimal('0.00')

    # 2. Alt temsilcilerden gelen kazancı hesapla (toplam) ve detaylı listeyi oluştur
    detailed_sub_agents_data = []
    total_sub_agent_revenue_for_current_agent = Decimal('0.00')

    # Doğru sorgu: current_agent objesi üzerinden 'alt_temsilciler' related_name'ini kullanarak
    # kendisine bağlı alt temsilcileri çekiyoruz.
    sub_agents_queryset = current_agent.alt_temsilciler.all() 

    for sub_agent in sub_agents_queryset:
        # Her bir alt temsilcinin kendi doğrudan kazancını hesapla
        sub_agent_own_commission = Payment.objects.filter(
            Q(appointment__agent=sub_agent) |
            Q(appointment__client__agents=sub_agent),
            is_commission_calculated=True
        ).aggregate(Sum('agent_commission'))['agent_commission__sum'] or Decimal('0.00')
        
        # Bu alt temsilcinin kazancından mevcut üst temsilciye (current_agent) düşen payı hesapla
        # Komisyon oranı yüzde ise /100 ile bölünmeli
        share_from_this_sub_agent = sub_agent_own_commission * (current_agent.alt_temsilci_komisyon_orani / Decimal('100'))
        
        total_sub_agent_revenue_for_current_agent += share_from_this_sub_agent

        detailed_sub_agents_data.append({
            'user': sub_agent.user,
            'sub_agent_profile': sub_agent, # Alt temsilcinin profil objesi
            'own_earnings': sub_agent_own_commission, # Alt temsilcinin doğrudan kendi kazancı
            'share_for_parent_agent': share_from_this_sub_agent, # Bu alt temsilciden üst temsilciye düşen pay
        })

    # 4. Toplam geliri hesapla
    toplam_gelir = direkt_gelir + total_sub_agent_revenue_for_current_agent

    context = {
        'current_agent': current_agent,
        'direkt_gelir': direkt_gelir,
        'alt_gelir': total_sub_agent_revenue_for_current_agent, # Yeni hesaplanan toplam
        'toplam_gelir': toplam_gelir,
        'alt_temsilciler_data': detailed_sub_agents_data, # Context değişken adını biraz değiştirdim karışıklığı önlemek için
        'title': 'Alt Temsilci Gelirleri Özeti' # Başlığı güncelledim
    }
    return render(request, 'payments/agent_income_summary.html', context)