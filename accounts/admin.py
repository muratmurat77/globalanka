from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Q

from .models import CustomUser, Expert, CustomerAgent


class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'user_type', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    list_filter = ('user_type', 'is_staff', 'is_active', 'is_superuser')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Kişisel Bilgiler', {'fields': ('first_name', 'last_name', 'email', 'phone', 'user_type')}),
        ('İzinler', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Önemli Tarihler', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'first_name', 'last_name', 'email', 'phone', 'user_type', 'password1', 'password2'),
        }),
    )


class ExpertAdmin(admin.ModelAdmin):
    list_display = ('user', 'specialization', 'commission_rate')
    search_fields = ('user__username', 'specialization')
    list_filter = ('specialization',)
    ordering = ('user__first_name',)


class AltTemsilciInline(admin.TabularInline):
    model = CustomerAgent
    fk_name = 'ust_temsilci'
    fields = ('user', 'commission_rate', 'alt_temsilci_komisyon_orani')
    readonly_fields = ('user',)
    extra = 0
    verbose_name = "Alt Temsilci"
    verbose_name_plural = "Alt Temsilciler"

    def has_add_permission(self, request, obj=None):
        return False  # Üst temsilci panelinden yeni alt temsilci eklenmesin

    def has_delete_permission(self, request, obj=None):
        return False  # Silinme de engellenebilir, istersen açabiliriz
    
    def toplam_alt_temsilci_kazanci(self, obj):
        toplam = obj.get_alt_temsilci_kazanci()
        return f"{toplam:.2f} ₺"
    toplam_alt_temsilci_kazanci.short_description = "Alt Temsilcilerden Kazanç"

class CustomerAgentAdmin(admin.ModelAdmin):
    list_display = ('user', 'commission_rate', 'alt_temsilci_komisyon_orani', 'ust_temsilci_adi', 'toplam_alt_temsilci_kazanci')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    list_filter = ('ust_temsilci',)
    filter_horizontal = ('assigned_clients',)
    inlines = [AltTemsilciInline]

    def ust_temsilci_adi(self, obj):
        return obj.ust_temsilci.user.get_full_name() if obj.ust_temsilci else "-"
    ust_temsilci_adi.short_description = "Üst Temsilci"

    def toplam_alt_temsilci_kazanci(self, obj):
        toplam = obj.get_alt_temsilci_kazanci()
        return f"{toplam:.2f} ₺"
    toplam_alt_temsilci_kazanci.short_description = "Alt Temsilcilerden Kazanç"

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "assigned_clients":
            agent_id = request.resolver_match.kwargs.get('object_id')
            all_client_users = CustomUser.objects.filter(user_type='client')

            if agent_id:
                current_agent_clients_pks = CustomerAgent.objects.get(pk=agent_id).assigned_clients.values_list('pk', flat=True)
                kwargs["queryset"] = CustomUser.objects.filter(
                    Q(pk__in=current_agent_clients_pks) | Q(agents__isnull=True),
                    user_type='client'
                ).distinct().order_by('first_name', 'last_name')
            else:
                kwargs["queryset"] = all_client_users.filter(agents__isnull=True).distinct().order_by('first_name', 'last_name')

        return super().formfield_for_manytomany(db_field, request, **kwargs)

    

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Expert, ExpertAdmin)
admin.site.register(CustomerAgent, CustomerAgentAdmin)
