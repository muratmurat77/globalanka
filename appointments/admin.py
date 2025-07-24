# appointments/admin.py

from django.contrib import admin
from .models import Appointment, ExpertAvailability, ExpertHoliday 
from accounts.models import Expert, CustomerAgent, CustomUser # CustomerAgent ve CustomUser'ı da import edin

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    # 'service_type' alanı list_display'e eklendi
    list_display = ('id', 'expert', 'client', 'agent_display', 'service_type', 'formatted_date', 'status', 'payment_status') 
    
    # 'service_type' alanı list_filter'a eklendi
    list_filter = ('status', 'service_type', 'expert', 'agent', 'payment_status', 'date')
    
    search_fields = ('client__username', 'expert__user__username', 'expert__user__first_name', 'expert__user__last_name', 'notes') 
    
    actions = ['approve_appointments', 'cancel_appointments'] 
    date_hierarchy = 'date' 

    list_editable = ('status',) # Randevu durumu list üzerinden düzenlenebilsin

    # fieldsets alanından 'agent' kaldırıldı
    fieldsets = (
        (None, {
            'fields': ('client', 'expert', 'service_type', 'date', 'status', 'payment_status', 'amount', 'notes')
        }),
    )
    
    # 'agent' raw_id_fields'tan da kaldırıldı, çünkü manuel seçilmeyecek
    raw_id_fields = ('client', 'expert',) 

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Eğer randevu oluşturuluyorsa (obj is None) veya güncelleniyorsa
        # ve agent alanı formda görünüyorsa, gizlenecek veya readonly yapılacak.
        # Ancak fieldsets'ten kaldırdığımız için bu kontrol çok gerekli değil.
        # Eğer admin panelinde "agent" alanı farklı durumlarda gösterilmek isteniyorsa burada mantık kurulabilir.
        return form

    def save_model(self, request, obj, form, change):
        # Randevu kaydedilmeden önce veya güncellenirken agent alanını otomatik olarak atayalım
        if not obj.agent: # Eğer agent zaten atanmamışsa veya boş bırakılmışsa
            # Seçilen müşteriye atanmış bir temsilci bulmaya çalış
            # Not: Bir müşteriye birden fazla temsilci atanmışsa, ilk bulunan atanır.
            # Bu durumda, müşterinin CustomerAgent objesine ForegignKey ile bağlanması daha mantıklı olurdu.
            # Ancak sizin modeliniz ManyToMany olduğu için, ManyToMany'den ilkini alıyoruz.
            # Eğer bir müşterinin BİR temsilcisi varsa, CustomerAgent modelinde client'a ForeignKey yapmak daha iyidir.
            # Geçici çözüm olarak ManyToMany üzerinden ilk bulunan temsilciyi alıyoruz:
            try:
                # client objesi formdan alınmış CustomUser objesidir
                client_user = obj.client 
                
                # Bu müşteriye atanmış bir CustomerAgent var mı diye bakıyoruz
                # NOT: Eğer bir müşterinin birden fazla temsilcisi varsa, bu mantık ilk bulduğunu atar.
                # Genellikle bir müşterinin tek bir ana temsilcisi olur, bu durumda model yapınızda
                # müşteri tarafında CustomerAgent'a ForeignKey ilişkisi düşünmelisiniz.
                # Şimdilik ManyToMany üzerinden ilkini alıyoruz:
                assigned_agent = CustomerAgent.objects.filter(assigned_clients=client_user).first()
                if assigned_agent:
                    obj.agent = assigned_agent
                else:
                    # Hiçbir temsilci atanmamışsa, null bırakabiliriz.
                    # Ya da bir varsayılan temsilci atayabiliriz.
                    # Şimdilik boş kalmasına izin veriyoruz, çünkü modelde null=True.
                    pass 
            except CustomerAgent.DoesNotExist:
                # Müşterinin atanmış bir temsilcisi yoksa (eğer CustomUser'a ForeignKey olsaydı bu hata oluşurdu)
                pass 

        super().save_model(request, obj, form, change) # Modelin normal kaydetme işlemini çağır


    def agent_display(self, obj):
        # Admin listesinde agent'ın tam adını göstermek için metod
        if obj.agent:
            return obj.agent.user.get_full_name() or obj.agent.user.username
        return "Yok"
    agent_display.short_description = 'Atanan Temsilci'


    def approve_appointments(self, request, queryset):
        updated = queryset.filter(status__in=['pending', 'confirmed']).update(status='confirmed')
        self.message_user(request, f"{updated} adet randevu onaylandı.")
    approve_appointments.short_description = "Seçili randevuları onayla"
    
    def cancel_appointments(self, request, queryset):
        updated = queryset.filter(status__in=['pending', 'confirmed']).update(status='cancelled')
        self.message_user(request, f"{updated} adet randevu iptal edildi.")
    cancel_appointments.short_description = "Seçili randevuları iptal et"

    def formatted_date(self, obj):
        return obj.date.strftime("%d %B %Y %H:%M")
    formatted_date.short_description = 'Randevu Tarihi'

# --- Mevcut diğer admin kayıtlarınız (Değişiklik yok) ---

@admin.register(ExpertAvailability)
class ExpertAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('expert', 'get_day_of_week_display', 'start_time', 'end_time')
    list_filter = ('expert', 'day_of_week')
    search_fields = ('expert__user__username', 'expert__user__first_name', 'expert__user__last_name')
    ordering = ['expert__user__username', 'day_of_week', 'start_time']

@admin.register(ExpertHoliday)
class ExpertHolidayAdmin(admin.ModelAdmin):
    list_display = ('expert', 'start_date', 'end_date', 'description')
    list_filter = ('expert',)
    search_fields = ('expert__user__username', 'description')
    date_hierarchy = 'start_date'
    ordering = ['expert__user__username', 'start_date']