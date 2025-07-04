from django.urls import path,include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('tags', views.TagViewSet, basename='tags')
router.register('roomtypes', views.RoomTypeViewSet, basename='roomtypes')
urlpatterns = [
    # Room Management
    path('live/', views.LiveRoomsListView.as_view(), name='live-rooms'),
    path('create/', views.CreateRoomView.as_view(), name='create-room'),
    path('<int:room_id>/', views.RoomDetailView.as_view(), name='room-detail'),
    path('<int:room_id>/join/', views.JoinRoomView.as_view(), name='join-room'),
    path('<int:room_id>/leave/', views.LeaveRoomView.as_view(), name='leave-room'),
    path('<int:room_id>/end/', views.EndRoomView.as_view(), name='end-room'),
    
    # Room Data
    path('<int:room_id>/participants/', views.RoomParticipantsView.as_view(), name='room-participants'),
    path('<int:room_id>/messages/', views.RoomMessagesView.as_view(), name='room-messages'),
    
    # User Rooms
    path('my-rooms/', views.MyRoomsView.as_view(), name='my-rooms'),
    path('<int:room_id>/report/<int:user_id>/', views.ReportUserView.as_view(), name='report-user'),
    
    # Utility
    path('', include(router.urls)),  # Include the router URLs for tags and room types
]