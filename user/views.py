import os
from datetime import timedelta

from captcha.helpers import captcha_image_url
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
import json
from captcha.models import CaptchaStore

from book.models import Book
from user.models import UserCollectedBook, UploadedBook


@csrf_exempt
def init_csrf(request):
    # 强制生成CSRF token
    get_token(request)
    return JsonResponse({'detail': 'CSRF cookie set'})


def generate_captcha(request):
    # 使用 CaptchaStore.generate_key() 方法生成新的验证码键
    captcha_key = CaptchaStore.generate_key()

    # 获取相应的图像 URL
    image_url = captcha_image_url(captcha_key)

    # 返回 JSON 响应
    return JsonResponse({
        'key': captcha_key,
        'image_url': image_url
    })


def login_user(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        captcha_key = request.POST.get('captcha_key')
        captcha_value = request.POST.get('captcha_value')

        # 检查验证码是否正确
        try:
            captcha = CaptchaStore.objects.get(response=captcha_value, hashkey=captcha_key)
            captcha.delete()  # 删除已经使用的验证码
        except CaptchaStore.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Invalid captcha'})

        # 检查用户是否已达到登录尝试限制
        login_attempts = request.session.get('login_attempts', 0)
        last_attempt_time = request.session.get('last_attempt_time', timezone.now())

        if login_attempts >= 5 and timezone.now() < last_attempt_time + timedelta(minutes=1):
            return JsonResponse({'success': False, 'error': 'Too many failed login attempts. Please try again later.'})

        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            request.session['login_attempts'] = 0  # 重置登录尝试次数
            return JsonResponse({'success': True})
        else:
            request.session['login_attempts'] = login_attempts + 1
            request.session['last_attempt_time'] = timezone.now()
            return JsonResponse({'success': False, 'error': 'Invalid credentials'})

    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def logout_user(request):
    logout(request)
    return JsonResponse({'success': True})


def register_user(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            captcha_key = data.get('captcha_key')
            captcha_value = data.get('captcha_value')

            # 验证验证码
            try:
                captcha = CaptchaStore.objects.get(hashkey=captcha_key)
                if not captcha.response == captcha_value.lower():
                    return JsonResponse({'success': False, 'message': '验证码错误'})
            except CaptchaStore.DoesNotExist:
                return JsonResponse({'success': False, 'message': '无效的验证码'})

            if User.objects.filter(username=data['username']).exists():
                return JsonResponse({'success': False, 'message': '用户名已存在'})

            user = User.objects.create(
                username=data['username'],
                email=data['email'],
                password=make_password(data['password'])
            )
            user.save()
            return JsonResponse({'success': True, 'message': '注册成功'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return JsonResponse({'success': False, 'message': '只支持 POST 请求'})


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


@login_required
@require_POST
def change_password(request):
    current_password = request.POST.get('current_password')
    new_password = request.POST.get('new_password')
    user = request.user

    # 确认当前密码是否正确
    if not user.check_password(current_password):
        return JsonResponse({'success': False, 'message': '当前密码不正确'}, status=400)

    # 设置新密码并保存用户对象
    user.set_password(new_password)
    user.save()

    # 更新会话以保持用户登录状态
    update_session_auth_hash(request, user)

    return JsonResponse({'success': True, 'message': '密码已更新'})
