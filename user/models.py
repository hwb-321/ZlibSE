from django.db import models
from django.contrib.auth.models import User

from book.models import Book


class UserCollectedBook(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)


class UploadedBook(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_books')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='uploaders')
    uploaded_at = models.DateTimeField(auto_now_add=True)
