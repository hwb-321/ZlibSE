from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from book.models import Book
from user.models import UserCollectedBook, UploadedBook


@csrf_exempt
def init_csrf(request):
    # 强制生成CSRF token
    get_token(request)
    return JsonResponse({'detail': 'CSRF cookie set'})


def login_user(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Invalid credentials'})
    else:
        return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def logout_user(request):
    logout(request)
    return JsonResponse({'success': True})


def register_user(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        if not User.objects.filter(username=username).exists():
            User.objects.create_user(username=username, password=password)
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Username already exists'})
    else:
        return JsonResponse({'success': False, 'error': 'Invalid request'})


@csrf_exempt
def check_session(request):
    if request.user.is_authenticated:
        return JsonResponse({'isLoggedIn': True})
    else:
        return JsonResponse({'isLoggedIn': False})


@login_required
@require_http_methods(["POST"])
def add_to_favorites(request, book_id):
    user = request.user

    try:
        # 确保书籍存在
        book = Book.objects.get(pk=book_id)

        # 检查用户是否已经收藏了这本书
        if UserCollectedBook.objects.filter(user=user, book=book).exists():
            return JsonResponse({'success': False, 'message': '已经收藏过这本书'})

        # 创建新的收藏记录
        UserCollectedBook.objects.create(user=user, book=book)

        return JsonResponse({'success': True, 'message': '书籍收藏成功'})
    except ObjectDoesNotExist:
        return JsonResponse({'success': False, 'message': '书籍不存在'}, status=404)


@login_required
def remove_from_favorites(request, book_id):
    user = request.user
    try:
        book = Book.objects.get(pk=book_id)
        favorite = UserCollectedBook.objects.filter(user=user, book=book)
        if favorite.exists():
            favorite.delete()
            return JsonResponse({'success': True, 'message': '已取消收藏'})
        else:
            return JsonResponse({'success': False, 'message': '书籍未收藏'})
    except Book.DoesNotExist:
        return JsonResponse({'success': False, 'message': '书籍不存在'}, status=404)


@login_required
def check_favorite(request, book_id):
    user = request.user
    try:
        book = Book.objects.get(pk=book_id)
        is_favorited = UserCollectedBook.objects.filter(user=user, book=book).exists()
        return JsonResponse({'isFavorited': is_favorited})
    except Book.DoesNotExist:
        return JsonResponse({'success': False, 'message': '书籍不存在'}, status=404)


@login_required
def get_favorites(request):
    user = request.user

    # 查询当前用户收藏的书籍
    collected_books = UserCollectedBook.objects.filter(user=user).select_related('book')

    # 获取收藏书籍的详细信息，包括 id
    books_list = [
        {
            'id': collected_book.book.id,
            'title': collected_book.book.title,
            'author': collected_book.book.author,
            'isbn': collected_book.book.isbn,
            'category': collected_book.book.category,
            'year': collected_book.book.year,
            'language': collected_book.book.language,
            'file_type': collected_book.book.file_type,
            'file_path': collected_book.book.file_path.url if collected_book.book.file_path else '',
            'file_size': collected_book.book.file_size,
            'cover_image_path': collected_book.book.cover_image_path.url if collected_book.book.cover_image_path else ''
        }
        for collected_book in collected_books
    ]

    return JsonResponse({'favorites': books_list})


@login_required
def upload_book_list(request):
    user = request.user

    # 查询当前用户上传的所有书籍的记录
    uploaded_books_records = UploadedBook.objects.filter(user=user).select_related('book')

    # 构造书籍详细信息列表
    books_list = [
        {
            'id': record.book.id,
            'title': record.book.title,
            'author': record.book.author,
            'isbn': record.book.isbn,
            'category': record.book.category,
            'year': record.book.year,
            'language': record.book.language,
            'file_type': record.book.file_type,
            'file_path': record.book.file_path.url if record.book.file_path else '',
            'file_size': record.book.file_size,
            'cover_image_path': record.book.cover_image_path.url if record.book.cover_image_path else ''
        }
        for record in uploaded_books_records
    ]

    return JsonResponse({'uploadedBooks': books_list})


@login_required
def delete_uploaded_book(request, book_id):
    user = request.user

    # 获取与用户和书籍相关联的 UploadedBook 记录
    uploaded_book = get_object_or_404(UploadedBook, user=user, book_id=book_id)

    # 获取 Book 实例
    book = uploaded_book.book

    # 检查并删除文件
    if book.file_path and os.path.exists(book.file_path.path):
        book.file_path.delete(save=False)
    if book.cover_image_path and os.path.exists(book.cover_image_path.path):
        book.cover_image_path.delete(save=False)

    # 删除 UploadedBook 记录和 Book 记录
    uploaded_book.delete()
    book.delete()

    return JsonResponse({'success': True, 'message': '书籍及相关文件已删除'})
