
from django.urls import path
from .views import AdminLoginView, AdminUserListView

urlpatterns = [
    path('login/', AdminLoginView.as_view(), name='admin_login'),
    path('users/', AdminUserListView.as_view(), name='admin_user_list'),
]
