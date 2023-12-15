from django.db import models
import uuid
import os


def get_file_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('books/', filename)


def get_cover_image_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('covers/', filename)


class Book(models.Model):
    title = models.CharField(max_length=200)  # 书籍名称
    author = models.CharField(max_length=100)  # 作者
    isbn = models.CharField(max_length=20)  # ISBN号
    category = models.CharField(max_length=100)  # 种类
    year = models.IntegerField()  # 出版年份
    language = models.CharField(max_length=50)  # 语言
    file_type = models.CharField(max_length=50)  # 文件类型
    file_path = models.FileField(upload_to=get_file_path)  # 文件路径
    file_size = models.DecimalField(max_digits=10, decimal_places=2)  # 文件大小
    cover_image_path = models.ImageField(upload_to=get_cover_image_path)  # 封面图片路径

    def __str__(self):
        return self.title
