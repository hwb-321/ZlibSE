from django.shortcuts import redirect
from django.urls import reverse, resolve
from django.conf import settings

# myapp/middleware.py

from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings

# myapp/middleware.py

from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 获取登录页面的URL
        login_url = reverse('login_user')

        path = request.path_info
        if path.startswith('/user/register_html') or path.startswith('/user/register_user') or path.startswith(
                '/favicon.ico'):
            return self.get_response(request)

        # 检查用户是否已登录和请求的路径不是登录页面
        if not request.user.is_authenticated and not path.startswith(login_url):
            return redirect(settings.LOGIN_URL)

        response = self.get_response(request)
        return response
