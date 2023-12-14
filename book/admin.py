from django.contrib import admin
from .models import Book


class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'isbn')  # 在列表页显示的字段
    search_fields = ('title', 'author')  # 添加搜索框


admin.site.register(Book, BookAdmin)
