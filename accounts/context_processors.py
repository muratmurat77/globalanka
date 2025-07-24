# klinik_yonetim/accounts/context_processors.py

def user_roles(request):
    """
    Her isteğe kullanıcının rollerini ve profil bilgilerini ekleyen context processor.
    """
    user = request.user
    is_expert = False
    is_agent = False
    is_admin = False

    # Kullanıcı oturum açmışsa profillerini kontrol et
    if user.is_authenticated:
        # admin kontrolü
        if hasattr(user, 'user_type') and user.user_type == 'admin':
            is_admin = True

        # Expert profilini kontrol et (Expert modelinin CustomUser ile OneToOne ilişkisi varsa)
        # Eğer CustomUser modelinde 'expert_profile' isminde bir related_name yoksa, 
        # bunun yerine Expert.objects.filter(user=user).exists() gibi bir kontrol yapmanız gerekebilir.
        if hasattr(user, 'expert_profile') and user.expert_profile is not None:
            is_expert = True

        # CustomerAgent profilini kontrol et (CustomerAgent modelinin CustomUser ile OneToOne ilişkisi varsa)
        # Eğer CustomUser modelinde 'agent_profile' isminde bir related_name yoksa, 
        # bunun yerine CustomerAgent.objects.filter(user=user).exists() gibi bir kontrol yapmanız gerekebilir.
        if hasattr(user, 'agent_profile') and user.agent_profile is not None:
            is_agent = True

    return {
        'is_expert': is_expert,
        'is_agent': is_agent,
        'is_admin': is_admin,
    }