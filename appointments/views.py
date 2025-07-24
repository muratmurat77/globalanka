# appointments/views.py

from django.urls import reverse_lazy
from django.contrib import messages
from django.views.generic import CreateView, ListView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect, get_object_or_404
from django.db.models import Q 
from django.http import JsonResponse
from datetime import datetime, timedelta, date
from django.utils import timezone 
from django.views.decorators.http import require_POST 
from django.contrib.auth.decorators import login_required 
from django.contrib.messages.views import SuccessMessageMixin # SuccessMessageMixin import edildi

from .models import Appointment, ExpertAvailability, ExpertHoliday
from .forms import AppointmentForm
from accounts.models import CustomUser, Expert, CustomerAgent

# --- Randevu Oluşturma Görünümü ---
class AppointmentCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView): # SuccessMessageMixin eklendi
    """
    Yeni bir randevu oluşturmak için kullanılan görünüm.
    Müşteri, temsilci ve admin rolleri için randevu oluşturma yetkisi sağlar.
    Randevunun durumunu ve temsilci atamasını otomatik olarak ayarlar.
    """
    model = Appointment
    form_class = AppointmentForm
    template_name = 'appointments/create.html'
    success_url = reverse_lazy('appointments:list')
    success_message = "Randevunuz başarıyla oluşturuldu!" # Yeni ve doğru başarı mesajı

    def get_form_kwargs(self):
        """Forma mevcut kullanıcıyı gönderir."""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user 
        return kwargs

    def form_valid(self, form):
        """Form geçerli olduğunda randevuyu kaydeder ve ek atamalar yapar."""
        appointment = form.save(commit=False)
        user = self.request.user

        if user.user_type == 'client':
            # Müşteri ise, randevuyu kendisine atar ve atanmış bir temsilci varsa onu belirler.
            appointment.client = user
            assigned_agent = CustomerAgent.objects.filter(assigned_clients=user).first()
            if assigned_agent:
                appointment.agent = assigned_agent
            else:
                messages.warning(self.request, f"Size atanmış bir müşteri temsilcisi bulunamadı. Randevu temsilcisiz oluşturuldu.")
            
            appointment.status = 'pending'
            appointment.payment_status = False

        elif user.user_type == 'agent':
            # Temsilci ise, randevuyu kendi temsilci profiline atar.
            # Randevu formundan gelen müşteri (client) alanı için işlem yapılır.
            try:
                appointment.agent = user.agent_profile
            except CustomerAgent.DoesNotExist:
                messages.error(self.request, "Müşteri temsilcisi profiliniz bulunamadı. Randevu oluşturulamıyor.")
                return self.form_invalid(form)

            appointment.status = 'pending'
            appointment.payment_status = False
        
        elif user.user_type == 'admin':
            # Admin ise, formdaki değerleri kullanır. Müşteri atanmışsa temsilciyi de belirler.
            client = appointment.client
            if client:
                assigned_agent = CustomerAgent.objects.filter(assigned_clients=client).first()
                if assigned_agent:
                    appointment.agent = assigned_agent
                else:
                    messages.warning(self.request, f"Seçilen müşteriye ({client.get_full_name() or client.username}) atanmış bir temsilci bulunamadı. Randevu temsilcisiz oluşturuldu.")
            pass # Admin için varsayılan atama yok, formdan gelen değerler geçerlidir.

        self.object = appointment
        return super().form_valid(form)

    def dispatch(self, request, *args, **kwargs):
        """Yetkilendirme kontrolü yapar ve yetkisiz kullanıcıları yönlendirir."""
        if not request.user.is_authenticated:
            return self.handle_no_permission() 

        allowed_user_types = ['admin', 'agent', 'client']
        if request.user.user_type not in allowed_user_types:
            messages.error(request, "Randevu oluşturmak için yetkiniz bulunmamaktadır.")
            return redirect(reverse_lazy('home'))

        return super().dispatch(request, *args, **kwargs)

# --- Genel Randevu Listeleme Görünümü (Admin veya Genel Bakış İçin) ---
class AppointmentListView(LoginRequiredMixin, ListView):
    """
    Tüm randevuları listeler ve rol bazında filtreleme ve arama seçenekleri sunar.
    Genellikle Admin ve diğer yetkililer için genel bir bakış sağlar.
    """
    model = Appointment
    template_name = 'appointments/list.html' 
    context_object_name = 'object_list'
    paginate_by = 10 

    def get_queryset(self):
        """Randevu listesini kullanıcı rolüne ve GET parametrelerine göre filtreler."""
        queryset = Appointment.objects.select_related(
            'client', 
            'expert__user', 
            'agent__user' 
        ).order_by('-date') 

        user = self.request.user

        # Kullanıcı rolüne göre başlangıç filtrelemesi
        if user.user_type == 'client':
            queryset = queryset.filter(client=user)
        elif user.user_type == 'agent':
            try:
                agent_profile = user.agent_profile
                # Temsilcinin atandığı müşterilerin veya direkt kendi atandığı randevuları
                queryset = queryset.filter(
                    Q(client__agents=agent_profile) | 
                    Q(agent=agent_profile) 
                )
            except CustomerAgent.DoesNotExist:
                messages.warning(self.request, "Müşteri temsilcisi profiliniz bulunamadığı için randevu listesi boş olabilir.")
                return queryset.none()
        elif user.user_type == 'admin':
            pass # Admin tüm randevuları görür, ek rol tabanlı filtre yok
        elif user.user_type == 'expert':
            try:
                expert_profile = user.expert_profile
                queryset = queryset.filter(expert=expert_profile)
            except Expert.DoesNotExist:
                messages.warning(self.request, "Uzman profiliniz bulunamadığı için randevu listesi boş olabilir.")
                return queryset.none()
        
        # --- Ek Filtreleme MANTIĞI (GET parametrelerine göre) ---
        client_name = self.request.GET.get('client_name')
        selected_date = self.request.GET.get('date')
        status = self.request.GET.get('status') # Yeni filtre: Randevu durumu
        expert_filter_id = self.request.GET.get('expert_filter') # Yeni filtre: Uzman ID
        agent_filter_id = self.request.GET.get('agent_filter') # Yeni filtre: Temsilci ID
        service_type = self.request.GET.get('service_type') # Yeni filtre: Hizmet Tipi

        if client_name:
            queryset = queryset.filter(
                Q(client__first_name__icontains=client_name) | 
                Q(client__last_name__icontains=client_name) |
                Q(client__username__icontains=client_name)
            )
        
        if selected_date:
            try:
                date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
                queryset = queryset.filter(date__date=date_obj)
            except ValueError:
                messages.error(self.request, "Geçersiz tarih formatı. Lütfen YYYY-AA-GG formatını kullanın.")
        
        if status:
            queryset = queryset.filter(status=status)
            
        if expert_filter_id:
            queryset = queryset.filter(expert__id=expert_filter_id)
            
        if agent_filter_id:
            queryset = queryset.filter(agent__id=agent_filter_id)

        if service_type:
            queryset = queryset.filter(service_type=service_type)

        return queryset

    def get_context_data(self, **kwargs):
        """Şablon için ek bağlam verileri sağlar."""
        context = super().get_context_data(**kwargs)
        user_type = self.request.user.user_type

        context['show_client'] = user_type in ['admin', 'agent', 'expert'] 
        # Bu sütunlar genellikle genel listede gösterilir, ancak daha özel rollerde gizlenebilir
        context['show_agent_col'] = user_type in ['admin'] # Sadece Admin için temsilci sütununu göster
        context['show_expert_col'] = user_type in ['admin', 'agent', 'client'] # Admin, agent, client için uzman sütununu göster
        context['show_status_col'] = True 
        context['show_actions_col'] = user_type in ['admin', 'agent', 'expert']

        # Filtreleme formunda mevcut değerleri korumak için context'e ekle
        context['current_client_name'] = self.request.GET.get('client_name', '')
        context['current_date'] = self.request.GET.get('date', '')
        context['current_status'] = self.request.GET.get('status', '') # Yeni
        context['current_expert_filter'] = self.request.GET.get('expert_filter', '') # Yeni
        context['current_agent_filter'] = self.request.GET.get('agent_filter', '') # Yeni
        context['current_service_type'] = self.request.GET.get('service_type', '') # Yeni

        # Filtreleme dropdown'ları için seçenekler
        context['appointment_statuses'] = Appointment.STATUS_CHOICES
        context['experts'] = Expert.objects.all()
        context['agents'] = CustomerAgent.objects.all()
        context['service_choices'] = Appointment.SERVICE_CHOICES

        return context
    
# --- Randevu Güncelleme Görünümü ---
class AppointmentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Mevcut bir randevuyu güncellemek için kullanılan görünüm.
    Admin, atanmış temsilci, randevu sahibi müşteri veya randevu alınan uzman tarafından güncellenebilir.
    """
    model = Appointment
    form_class = AppointmentForm
    template_name = 'appointments/update.html'
    success_url = reverse_lazy('appointments:list')

    def get_form_kwargs(self):
        """Forma mevcut kullanıcıyı gönderir."""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user 
        return kwargs

    def form_valid(self, form):
        """Form geçerli olduğunda randevuyu kaydeder."""
        current_appointment = self.get_object() 

        # Admin olmayanlar için belirli alanların değiştirilmesini kısıtla
        if self.request.user.user_type != 'admin':
            form.instance.status = current_appointment.status
            form.instance.payment_status = current_appointment.payment_status
            form.instance.amount = current_appointment.amount
        else:
            # Admin randevu oluştururken temsilci seçilmemişse, mevcut temsilciyi koru
            if not form.instance.agent and current_appointment.agent:
                form.instance.agent = current_appointment.agent

        if form.has_changed():
            messages.success(
                self.request,
                f"Randevu başarıyla güncellendi! (Yeni tarih: {form.instance.date.strftime('%d %B %Y %H:%M')})"
            )
        else:
            messages.info(self.request, "Randevuda herhangi bir değişiklik yapılmadı.")

        return super().form_valid(form)

    def test_func(self):
        """Kullanıcının randevuyu güncelleme yetkisini kontrol eder."""
        appointment = self.get_object()
        user = self.request.user

        if user.user_type == 'admin':
            return True
        
        if user.user_type == 'agent':
            try:
                agent_profile = user.agent_profile
                # Temsilci, kendi atandığı randevuları VEYA müşterisi kendisine atanmışsa güncelleyebilir.
                return (appointment.agent == agent_profile) or \
                       (appointment.client in agent_profile.assigned_clients.all())
            except CustomerAgent.DoesNotExist:
                return False
            
        if user.user_type == 'client':
            return appointment.client == user
            
        if user.user_type == 'expert':
            return appointment.expert.user == user

        return False

    def dispatch(self, request, *args, **kwargs):
        """Yetkilendirme kontrolü yapar ve yetkisiz kullanıcıları yönlendirir."""
        if not request.user.is_authenticated:
            return self.handle_no_permission() 

        allowed_user_types = ['admin', 'agent', 'client', 'expert']
        if request.user.user_type not in allowed_user_types:
            messages.error(request, "Bu işlemi yapmaya yetkiniz bulunmamaktadır.")
            return redirect(reverse_lazy('home')) 

        return super().dispatch(request, *args, **kwargs)

# --- AJAX Görünümü: Müsait Randevu Saatlerini Getir ---
def get_available_appointment_slots(request):
    """
    Belirli bir uzman ve tarih için müsait randevu saatlerini döndürür.
    AJAX çağrıları ile kullanılır.
    """
    expert_id = request.GET.get('expert_id')
    selected_date_str = request.GET.get('date')

    APPOINTMENT_INTERVAL_MINUTES = 15

    if not expert_id or not selected_date_str:
        return JsonResponse({'error': 'Uzman kimliği ve tarih gerekli.'}, status=400)

    try:
        expert = get_object_or_404(Expert, id=expert_id)
        selected_date_dt = datetime.strptime(selected_date_str, '%Y-%m-%d').date()

    except (ValueError, Expert.DoesNotExist):
        return JsonResponse({'error': 'Geçersiz uzman veya tarih formatı.'}, status=400)

    if selected_date_dt < timezone.localdate(): 
        return JsonResponse({'available_slots': []})

    day_of_week = selected_date_dt.weekday() 
    expert_availabilities = ExpertAvailability.objects.filter(
        expert=expert,
        day_of_week=day_of_week
    ).order_by('start_time')

    if not expert_availabilities.exists():
        return JsonResponse({'available_slots': []}) 

    is_holiday = ExpertHoliday.objects.filter(
        expert=expert,
        start_date__lte=selected_date_dt,
        end_date__gte=selected_date_dt
    ).exists()

    if is_holiday:
        return JsonResponse({'available_slots': []})

    booked_appointments = Appointment.objects.filter(
        expert=expert,
        date__date=selected_date_dt,
        status__in=['confirmed', 'pending'] 
    ).order_by('date')

    booked_slots_datetime = set()
    for app in booked_appointments:
        app_start_aware = app.date.astimezone(timezone.get_current_timezone())
        app_end_aware = app_start_aware + timedelta(minutes=APPOINTMENT_INTERVAL_MINUTES) 

        current_slot_dt = app_start_aware
        while current_slot_dt < app_end_aware:
            booked_slots_datetime.add(current_slot_dt)
            current_slot_dt += timedelta(minutes=APPOINTMENT_INTERVAL_MINUTES) 

    available_slots_str = []
    current_datetime_aware = timezone.now()

    for availability in expert_availabilities:
        slot_start_dt_aware = datetime.combine(selected_date_dt, availability.start_time).replace(tzinfo=timezone.get_current_timezone())
        slot_end_dt_aware = datetime.combine(selected_date_dt, availability.end_time).replace(tzinfo=timezone.get_current_timezone())

        temp_slot_dt = slot_start_dt_aware
        while temp_slot_dt + timedelta(minutes=APPOINTMENT_INTERVAL_MINUTES) <= slot_end_dt_aware:
            if selected_date_dt == current_datetime_aware.date() and \
               temp_slot_dt < current_datetime_aware + timedelta(minutes=APPOINTMENT_INTERVAL_MINUTES):
                temp_slot_dt += timedelta(minutes=APPOINTMENT_INTERVAL_MINUTES) # 'a' karakteri buradan kaldırıldı
                continue

            if temp_slot_dt not in booked_slots_datetime:
                available_slots_str.append(temp_slot_dt.strftime('%H:%M'))
            
            temp_slot_dt += timedelta(minutes=APPOINTMENT_INTERVAL_MINUTES)

    available_slots_str.sort()

    return JsonResponse({'available_slots': available_slots_str})

# --- Randevu İptal Görünümü ---
def is_admin_or_agent_or_owner(user, appointment):
    """
    Kullanıcının belirli bir randevuyu iptal etme yetkisi olup olmadığını kontrol eder.
    Admin, atanmış temsilci veya randevu sahibi müşteri iptal edebilir.
    """
    if user.is_authenticated:
        if user.user_type == 'admin':
            return True
        
        if user.user_type == 'client' and appointment.client == user:
            return True
        
        if user.user_type == 'agent':
            try:
                agent_profile = user.agent_profile
                # Randevu bu temsilciye direkt atanmışsa VEYA randevunun müşterisi bu temsilciye atanmışsa
                if appointment.agent == agent_profile:
                    return True
                if agent_profile.assigned_clients.filter(pk=appointment.client.pk).exists():
                    return True
            except CustomerAgent.DoesNotExist:
                return False 
        
    return False 

@login_required
@require_POST
def cancel_appointment(request, pk):
    """Randevunun durumunu 'cancelled' olarak günceller."""
    appointment = get_object_or_404(Appointment, pk=pk)

    if not is_admin_or_agent_or_owner(request.user, appointment):
        messages.error(request, "Bu randevuyu iptal etme yetkiniz bulunmamaktadır.")
        return redirect('appointments:list')

    if appointment.status in ['pending', 'confirmed']:
        appointment.status = 'cancelled'
        appointment.save()
        messages.success(request, f"Randevu (Dr. {appointment.expert.user.get_full_name()} - {appointment.date.strftime('%d %B %Y %H:%M')}) başarıyla iptal edildi.")
    else:
        messages.warning(request, "Bu randevu zaten tamamlanmış veya iptal edilmiş olduğu için değiştirilemez.")
        
    return redirect('appointments:list')

# --- Müşteriye Özel Randevu Listeleme Görünümü ---
class ClientAppointmentListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Belirli bir müşteriye ait tüm randevuları listeler.
    Admin, müşterinin kendisi, ilgili temsilci veya randevu aldığı uzmanlar görebilir.
    """
    model = Appointment
    template_name = 'appointments/client_appointments_list.html' 
    context_object_name = 'client_appointments'
    paginate_by = 10

    def get_queryset(self):
        """URL'den gelen müşteri ID'sine göre randevuları filtreler."""
        client_pk = self.kwargs['client_pk']
        queryset = Appointment.objects.filter(
            client__pk=client_pk
        ).select_related(
            'client', 
            'expert__user', 
            'agent__user'
        ).order_by('-date')

        return queryset

    def get_context_data(self, **kwargs):
        """Şablon için ek bağlam verileri sağlar."""
        context = super().get_context_data(**kwargs)
        client_pk = self.kwargs['client_pk']
        context['target_client'] = get_object_or_404(CustomUser, pk=client_pk)
        context['title'] = f"{context['target_client'].get_full_name() or context['target_client'].username} Randevuları"
        context['show_client'] = False # Bu sayfada zaten tek müşterinin randevuları gösterildiği için müşteri sütunu gizlenir.
        return context

    def test_func(self):
        """Kullanıcının bu müşterinin randevularını görme yetkisini kontrol eder."""
        user = self.request.user
        client_pk = self.kwargs['client_pk']
        target_client = get_object_or_404(CustomUser, pk=client_pk)

        # Adminler her müşterinin randevularını görebilir
        if user.user_type == 'admin':
            return True
        
        # Temsilciler, kendi atanan müşterilerinin randevularını görebilir
        if user.user_type == 'agent':
            try:
                agent_profile = user.agent_profile
                return agent_profile.assigned_clients.filter(pk=client_pk).exists()
            except CustomerAgent.DoesNotExist:
                return False
        
        # Uzmanlar, bu müşterinin kendilerinden aldığı randevular varsa görebilir.
        if user.user_type == 'expert':
            return Appointment.objects.filter(expert__user=user, client=target_client).exists()
            
        # Müşteriler sadece kendi randevularını görebilir
        if user.user_type == 'client':
            return user.pk == client_pk
        
        return False 

    def handle_no_permission(self):
        """Yetkisiz erişimde kullanıcıyı uygun sayfaya yönlendirir."""
        messages.error(self.request, "Bu müşterinin randevularını görüntüleme yetkiniz bulunmamaktadır.")
        return redirect(reverse_lazy('appointments:list')) 


# --- YENİ GÖRÜNÜM: Uzmanların Kendi Randevularını Listelemesi ---
class ExpertAppointmentListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Uzmanların yalnızca kendilerine atanmış randevuları görmesini sağlar.
    Farklı randevu durumlarına göre filtreleme seçenekleri sunar.
    """
    model = Appointment
    template_name = 'appointments/expert_appointments_list.html' # Bu şablonu oluşturacağız
    context_object_name = 'expert_appointments'
    paginate_by = 15 # Uzmanlar için daha fazla randevu gösterebiliriz

    def get_queryset(self):
        user = self.request.user
        try:
            expert_profile = user.expert_profile
            queryset = Appointment.objects.filter(expert=expert_profile).select_related(
                'client', 
                'agent__user'
            ).order_by('-date')

            # Ek filtreleme: Duruma göre filtre
            status = self.request.GET.get('status')
            if status and status != 'all':
                queryset = queryset.filter(status=status)

            return queryset
        except Expert.DoesNotExist:
            messages.warning(self.request, "Uzman profiliniz bulunamadı. Lütfen bir uzman profili oluşturun.")
            return Appointment.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Dr. {self.request.user.get_full_name()} Randevuları"
        context['show_client'] = True # Uzman randevu listesinde müşteriyi göster
        context['show_agent_col'] = True # Temsilci bilgisini de göster
        context['show_expert_col'] = False # Kendisi olduğu için uzman sütununu gizle
        context['current_status'] = self.request.GET.get('status', 'all')
        context['appointment_statuses'] = [('all', 'Tümü')] + list(Appointment.STATUS_CHOICES) # 'Tümü' seçeneğini ekle
        return context

    def test_func(self):
        return self.request.user.user_type == 'expert' or self.request.user.user_type == 'admin' # Adminler de bu listeyi görebilir

    def handle_no_permission(self):
        messages.error(self.request, "Uzman randevularını görüntüleme yetkiniz bulunmamaktadır.")
        return redirect(reverse_lazy('home'))


# --- YENİ GÖRÜNÜM: Temsilcilerin Kendi Randevularını Listelemesi ---
class AgentAppointmentListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Temsilcilerin kendi atanan müşterileriyle ilgili randevuları görmesini sağlar.
    Farklı randevu durumlarına göre filtreleme seçenekleri sunar.
    """
    model = Appointment
    template_name = 'appointments/agent_appointments_list.html' # Bu şablonu oluşturacağız
    context_object_name = 'agent_appointments'
    paginate_by = 15 # Temsilciler için daha fazla randevu gösterebiliriz

    def get_queryset(self):
        user = self.request.user
        try:
            agent_profile = user.agent_profile
            queryset = Appointment.objects.filter(
                Q(client__agents=agent_profile) | 
                Q(agent=agent_profile) # Kendi direkt atadığı randevular
            ).select_related(
                'client', 
                'expert__user', 
                'agent__user'
            ).order_by('-date')

            # Ek filtreleme: Duruma göre filtre
            status = self.request.GET.get('status')
            if status and status != 'all':
                queryset = queryset.filter(status=status)
            
            # Ek filtreleme: Uzmana göre filtre (temsilci belirli bir uzmanın randevularını filtreleyebilir)
            expert_filter_id = self.request.GET.get('expert_filter')
            if expert_filter_id:
                queryset = queryset.filter(expert__id=expert_filter_id)

            return queryset
        except CustomerAgent.DoesNotExist:
            messages.warning(self.request, "Müşteri temsilcisi profiliniz bulunamadı. Randevu listesi boş olabilir.")
            return Appointment.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Temsilci Randevularınız ({self.request.user.get_full_name() or self.request.user.username})"
        context['show_client'] = True 
        context['show_expert_col'] = True 
        context['show_agent_col'] = False # Kendisi olduğu için temsilci sütununu gizle
        context['current_status'] = self.request.GET.get('status', 'all')
        context['current_expert_filter'] = self.request.GET.get('expert_filter', '')
        context['appointment_statuses'] = [('all', 'Tümü')] + list(Appointment.STATUS_CHOICES)
        context['experts'] = Expert.objects.all() # Temsilcinin uzmanlara göre filtrelemesi için
        return context

    def test_func(self):
        return self.request.user.user_type == 'agent' or self.request.user.user_type == 'admin'

    def handle_no_permission(self):
        messages.error(self.request, "Temsilci randevularını görüntüleme yetkiniz bulunmamaktadır.")
        return redirect(reverse_lazy('home'))
