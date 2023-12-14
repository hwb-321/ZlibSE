from django.urls import path
from user import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('login_user/', views.login_user, name='login_user'),
    path('logout_user/', views.logout_user, name='logout_user'),
    path('register_user/', views.register_user, name='register_user'),
    path('init_csrf/', views.init_csrf, name='init_csrf'),
    path('check_session/', views.check_session, name='check_session')
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
