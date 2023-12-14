from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt


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
