from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.contrib.auth.forms import UserCreationForm


def login_user(request):
    if request.method == 'POST':
        # 处理登录表单提交
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return JsonResponse({'success': True, 'redirect_url': reverse('home')})
        else:
            # 登录失败，可以添加错误处理
            print('登陆失败')
            return render(request, 'user/login_user.html', {'error': 'Invalid credentials'})
    else:
        # GET请求，显示登录表单
        return render(request, 'user/login_user.html')


@login_required
def logout_user(request):
    logout(request)
    return JsonResponse({'success': True, 'redirect_url': reverse('login_user')})


@login_required
def home(request):
    return render(request, 'user/home.html')


def register_html(request):
    return render(request, 'user/register_html.html')


def register_user(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        if not User.objects.filter(username=username).exists():
            User.objects.create_user(username=username, password=password)
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Username already exists'})
    return JsonResponse({'success': False, 'error': 'Invalid request'})
