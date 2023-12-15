import os
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from django.utils.text import slugify

from user.models import UploadedBook
from .forms import BookForm
from .models import Book


def get_descriptions(request):
    pass


@login_required
def download_book(request, book_id):
    try:
        book = Book.objects.get(pk=book_id)
        file_path = book.file_path.path
        if not os.path.exists(file_path):
            raise Http404("文件不存在")

        # 提取原始文件扩展名
        _, file_extension = os.path.splitext(file_path)

        # 创建一个以书名为文件名的安全字符串
        safe_title = slugify(book.title)
        download_filename = f"{safe_title}{file_extension}"

        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=download_filename)
    except Book.DoesNotExist:
        raise Http404("书籍不存在")


@login_required
def upload_book(request):
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES)
        if form.is_valid():
            book = form.save(commit=False)
            book.file_type = form.cleaned_data.get('file_type', '')  # 获取文件类型
            file = request.FILES.get('file_path')
            if file:
                # 计算文件大小并转换为MB
                book.file_size = file.size / (1024 * 1024)
            book.save()

            # 记录上传信息
            UploadedBook.objects.create(user=request.user, book=book)

            return JsonResponse({'success': True, 'message': '上传成功'})
        else:
            return JsonResponse({'success': False, 'message': '上传失败', 'errors': form.errors})

    return JsonResponse({'success': False, 'message': '只支持POST请求'})


@login_required
def count_book(request):
    count = Book.objects.count()
    return JsonResponse({'count': count})


@login_required
def list_book(request):
    # 获取查询参数
    page = request.GET.get('page', 1)  # 默认为第1页
    pageSize = request.GET.get('pageSize', 10)  # 默认每页10条记录

    # 获取所有书籍并分页
    books = Book.objects.all()
    paginator = Paginator(books, pageSize)

    # 获取请求的页码的书籍
    try:
        books_page = paginator.page(page)
    except EmptyPage:
        return JsonResponse({'error': '页面不存在'}, status=404)

    # 将书籍数据转换为字典列表
    books_list = list(books_page.object_list.values())

    return JsonResponse({
        'page': page,
        'pageSize': pageSize,
        'totalPages': paginator.num_pages,
        'books': books_list
    })


@login_required
def book_cover(request, book_id):
    try:
        book = Book.objects.get(pk=book_id)
        cover_path = book.cover_image_path.path
        if not os.path.exists(cover_path):
            raise Http404("封面图片不存在")
        return FileResponse(open(cover_path, 'rb'), content_type='image/jpeg')  # 或相应的图片格式
    except Book.DoesNotExist:
        raise Http404("书籍不存在")


@login_required
def get_descriptions(request, book_id):
    try:
        book = Book.objects.get(pk=book_id)
        book_data = {
            'title': book.title,
            'author': book.author,
            'isbn': book.isbn,
            'category': book.category,
            'year': book.year,
            'language': book.language,
            'file_type': book.file_type,
            'file_path': book.file_path.url if book.file_path else '',  # 获取文件路径的 URL
            'file_size': book.file_size,
            'cover_image_image': book.cover_image_path.url if book.cover_image_path else '',  # 获取封面图片路径的 URL
        }
        return JsonResponse(book_data)
    except Book.DoesNotExist:
        raise Http404("书籍不存在")


@login_required
def book_search(request):
    query = request.GET.get('query', '')

    books = Book.objects.filter(
        Q(title__icontains=query) |
        Q(author__icontains=query) |
        Q(isbn__icontains=query) |
        Q(category__icontains=query) |
        Q(year__icontains=query) |
        Q(language__icontains=query) |
        Q(file_type__icontains=query)
    )

    books_list = list(books.values())

    return JsonResponse({
        'query': query,
        'books': books_list
    })
