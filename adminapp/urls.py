from django.urls import path
from .views import AdminLoginView, AdminTokenRefreshView, AdminUserListView

urlpatterns = [
    path('login/', AdminLoginView.as_view(), name='admin_login'),
    path('token/refresh/', AdminTokenRefreshView.as_view(), name='admin_token_refresh'),
    path('users/', AdminUserListView.as_view(), name='admin_user_list'),
    # ... other admin routes
]
