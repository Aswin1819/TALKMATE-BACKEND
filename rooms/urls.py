from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TagViewSet, RoomTypeViewSet

router = DefaultRouter()
router.register('tags', TagViewSet, basename='tag')
router.register('roomtypes', RoomTypeViewSet, basename='roomtype')

urlpatterns = [
    path('', include(router.urls)),
]