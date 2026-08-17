"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView
from django.views.static import serve as static_serve

# SPA 入口：直接渲染 Vue 构建产物 frontend_dist/index.html
# ensure_csrf_cookie：确保加载 SPA 时下发 csrftoken cookie，
# 供 axios 在 POST/PUT/DELETE 时回传 X-CSRFToken，避免 DRF CSRF 403。
spa_view = ensure_csrf_cookie(TemplateView.as_view(template_name='index.html'))

urlpatterns = [
    # 前端管理员页面：显式交由 Vue Router 处理，避免被 Django admin 前缀抢先匹配。
    # 仅覆盖已知 SPA 页面，/admin/ 本身与其余后台路径仍走 Django admin。
    path('admin/users', spa_view, name='admin-users-spa'),
    path('admin/users/', spa_view),
    path('admin/payments', spa_view, name='admin-payments-spa'),
    path('admin/payments/', spa_view),
    path('admin/', admin.site.urls),
    path('api/design/', include('design.urls')),
    path('api/users/', include('users.urls')),
    path('api/payments/', include('payments.urls')),
    # 前端首页
    path('', spa_view, name='spa'),
    # 客户端路由回落：非 admin/api/static/media 的路径都交给 Vue Router
    re_path(r'^(?!admin/|api/|static/|media/).*$', spa_view),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif settings.SERVE_MEDIA_FILES:
    # 生成的效果图存在 MEDIA_ROOT。没有 nginx 兜底时（单容器直跑），
    # 由 Django 托管 /media/，否则 DEBUG=False 下前端拿到的图片链接会 404。
    # 注意 django.conf.urls.static.static() 在 DEBUG=False 时返回空列表，这里直接挂 serve。
    urlpatterns += [
        re_path(
            r'^media/(?P<path>.*)$',
            static_serve,
            {'document_root': settings.MEDIA_ROOT},
        ),
    ]
