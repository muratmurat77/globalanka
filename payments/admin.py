from django.contrib import admin
from .models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    # list_display: Admin listeleme sayfasında hangi sütunların gösterileceğini belirler
    list_display = (
        'appointment', 
        'amount_paid', 
        'payment_method', 
        'payment_date', 
        'expert_commission', # Komisyon alanlarının burada olduğundan emin olun
        'agent_commission',  # Komisyon alanlarının burada olduğundan emin olun
        'is_commission_calculated'
    )
    
    # list_filter: Admin listeleme sayfasında filtreleme seçeneklerini sunar
    list_filter = ('payment_method', 'payment_date', 'is_commission_calculated')
    
    # search_fields: Admin listeleme sayfasında arama yapabileceğiniz alanları belirler
    search_fields = (
        'appointment__client__first_name', 
        'appointment__client__last_name', 
        'amount_paid'
    )
    
    # readonly_fields: Admin panelinde sadece okunur olacak alanları belirler.
    # Komisyonlar otomatik hesaplandığı için genellikle buraya eklenirler.
    readonly_fields = (
        'expert_commission', 
        'agent_commission', 
        'payment_date', 
        'is_commission_calculated'
    )
    
    # raw_id_fields satırı kaldırıldı, böylece 'appointment' alanı normal açılır menü olarak görünecek.
    # raw_id_fields = ('appointment',) 

    # fieldsets: Admin panelinde ekleme/düzenleme formunun düzenini belirler.
    # Bu, alanları gruplamanıza ve isterseniz gizlemenize olanak tanır.
    fieldsets = (
        (None, {
            'fields': (
                'appointment', 
                'amount_paid', 
                'payment_method'
            )
        }),
        ('Komisyon ve Detaylar', {
            'fields': (
                'expert_commission', 
                'agent_commission', 
                'is_commission_calculated', 
                'payment_date'
            ),
            'classes': ('collapse',), # Bu bölümü varsayılan olarak gizler
        }),
    )

    # Django'nun save_model metodunu özelleştirme (eğer özel bir kaydetme mantığına ihtiyacınız varsa)
    # def save_model(self, request, obj, form, change):
    #     super().save_model(request, obj, form, change)
    #     # Eğer calculate_commissions sadece save metodu dışında çağrılıyorsa, burada ek bir işlem yapabilirsiniz.
    #     # Ancak bizim durumumuzda, modelin save() metodu zaten komisyonları hesaplıyor.