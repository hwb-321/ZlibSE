from django.urls import path
from user import views

urlpatterns = [
    path('login_user/', views.login_user, name='login_user'),
    path('logout_user/', views.logout_user, name='logout_user'),
    path('home/', views.home, name='home'),
    path('register_html/', views.register_html, name='register_html'),
    path('register_user/', views.register_user, name='register_user'),
]
