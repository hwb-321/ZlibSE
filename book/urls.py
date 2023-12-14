from django.urls import path
from book import views

urlpatterns = [
    path('get_descriptions/<int:book_id>/', views.get_descriptions, name='get_descriptions'),
    path('download/<int:book_id>/', views.download_book, name='download_book'),
    path('upload_book/', views.upload_book, name='upload_book'),
    path('count/', views.count_book, name='count'),
    path('list/', views.list_book, name='list'),
    path('cover/<int:book_id>/', views.book_cover, name='cover'),
    path('get_descriptions/<int:book_id>/', views.get_descriptions, name='get_descriptions'),
    path('search/', views.book_search, name='book_search'),
]
