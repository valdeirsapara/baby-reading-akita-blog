from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator


@method_decorator(login_not_required, name='dispatch')
class LoginView(auth_views.LoginView):
    """Tela de login estilizada. Isenta do LoginRequiredMiddleware."""
    template_name = 'auth_app/login.html'
    redirect_authenticated_user = True
    extra_context = {'vue': 'AuthController'}


class LogoutView(auth_views.LogoutView):
    """Logout (aceita apenas POST). Depois volta para a tela de login."""
    next_page = reverse_lazy('auth_app:login')
