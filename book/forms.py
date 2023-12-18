from django import forms
from .models import Book
from django.core.exceptions import ValidationError


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ['title', 'author', 'isbn', 'category', 'year', 'language', 'file_path', 'cover_image_path']

    def clean_file_path(self):
        file = self.cleaned_data.get('file_path', False)
        if file:
            if file.size > 1024 * 1024 * 1024:  # 1GB限制
                raise ValidationError("文件大小不能超过1GB")

            file_type = file.name.split('.')[-1]
            self.cleaned_data['file_type'] = file_type
            return file
        else:
            raise ValidationError("没有上传文件")
