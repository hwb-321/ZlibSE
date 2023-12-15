from django.urls import path
from user import views
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('login_user/', views.login_user, name='login_user'),
    path('logout_user/', views.logout_user, name='logout_user'),
    path('register_user', views.register_user, name='register_user'),
    path('init_csrf/', views.init_csrf, name='init_csrf'),
    path('check_session/', views.check_session, name='check_session'),
    path('favorites/', views.get_favorites, name='favorites'),
    path('add_to_favorites/<int:book_id>', views.add_to_favorites, name='add_to_favorites'),
    path('remove_from_favorites/<int:book_id>', views.remove_from_favorites, name='remove_from_favorites'),
    path('check_favorite/<int:book_id>', views.check_favorite, name='check_favorite'),
    path('get_upload_book_list', views.upload_book_list, name='get_upload_book_list'),
    path('delete_uploaded_book/<int:book_id>', views.delete_uploaded_book, name='delete_uploaded_book'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
