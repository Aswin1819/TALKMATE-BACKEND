from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser
from .models import Tag, RoomType
from .serializers import TagSerializer, RoomTypeSerializer

class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [IsAdminUser]

class RoomTypeViewSet(viewsets.ModelViewSet):
    queryset = RoomType.objects.all()
    serializer_class = RoomTypeSerializer
    permission_classes = [IsAdminUser]


