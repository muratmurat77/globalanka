# appointments/middleware.py
from django.shortcuts import redirect
from django.http import JsonResponse # JsonResponse'ı import edin
from django.urls import reverse # reverse fonksiyonunu import edin

class AppointmentCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Eğer kullanıcı giriş yapmışsa ve staff değilse (yani bir client, agent, expert ise)
        if request.user.is_authenticated and not request.user.is_staff:
            # Eğer kullanıcı bir client ise ve doğrulanmamışsa
            if hasattr(request.user, 'client_profile') and not request.user.client_profile.is_verified:
                
                # İsteğin AJAX olup olmadığını kontrol et
                # Genellikle jQuery, Axios gibi kütüphaneler bu başlığı ekler.
                # JavaScript'te fetch API kullanıyorsanız, X-Requested-With başlığını manuel eklemeniz gerekebilir
                # veya farklı bir yöntemle AJAX isteğini belirlemeniz gerekebilir.
                is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

                # Eğer AJAX isteği ise, HTML yerine JSON hata mesajı döndür
                if is_ajax:
                    return JsonResponse(
                        {'error': 'Profiliniz doğrulanmamış. Lütfen profilinizi tamamlayın.'},
                        status=403 # Forbidden (Yasak) veya 401 Unauthorized (Yetkisiz) olabilir
                    )
                else:
                    # Normal bir sayfa isteği ise yönlendirme yap
                    # complete_profile URL'sinin adını reverse ile alıyoruz
                    return redirect(reverse('complete_profile')) 
        
        return self.get_response(request)

