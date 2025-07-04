from django.urls import path
from .views import *

urlpatterns = [
    path('login/', AdminLoginView.as_view(), name='admin_login'),
    path('token/refresh/', AdminTokenRefreshView.as_view(), name='admin_token_refresh'),
    # Admin User Management
    path('users/', AdminUserListView.as_view(), name='admin_user_list'),
    path('users/<int:user_id>/', AdminUserProfileDetailView.as_view(), name='admin_user_profile_detail'),
    path('users/<int:user_id>/status/', AdminUserStatusUpdateView.as_view(), name='admin_user_status_update'),
    
    #Admin Room Management
    path('rooms/', AdminRoomListView.as_view(), name='admin_room_list'),
    path('rooms/<int:room_id>/', AdminRoomDetailView.as_view(), name='admin_room_detail'),
    # ... other admin routes
    
    #utils urls
    path('languages/', LanguageListView.as_view(), name='admin_language_list'),
    path('room-types/', RoomTypeListView.as_view(), name='admin_room_type_list'),
    path('tags/', TagListView.as_view(), name='admin_tag_list'),
    
    #moderationReports
    path('reports/', AdminReportedRoomListView.as_view(), name='admin_reportedroom_list'),
    path('reports/<int:pk>/status/', AdminReportedRoomStatusUpdateView.as_view(), name='admin_reportedroom_status_update'),
]
