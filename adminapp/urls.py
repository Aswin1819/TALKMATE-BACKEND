from django.urls import path
from .views import AdminLoginView, AdminTokenRefreshView, AdminUserListView, AdminUserProfileDetailView, AdminUserStatusUpdateView

urlpatterns = [
    path('login/', AdminLoginView.as_view(), name='admin_login'),
    path('token/refresh/', AdminTokenRefreshView.as_view(), name='admin_token_refresh'),
    path('users/', AdminUserListView.as_view(), name='admin_user_list'),
    path('users/<int:user_id>/', AdminUserProfileDetailView.as_view(), name='admin_user_profile_detail'),
    path('users/<int:user_id>/status/', AdminUserStatusUpdateView.as_view(), name='admin_user_status_update'),
    # ... other admin routes
]
