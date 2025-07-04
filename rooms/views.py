# rooms/views.py
from rest_framework import generics, status,viewsets
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from .models import Room, RoomParticipant, Message, Tag, RoomType
from .serializers import (
    RoomSerializer, CreateRoomSerializer, RoomParticipantSerializer,
    MessageSerializer, TagSerializer, RoomTypeSerializer,ReportedRoomSerializer
)

class LiveRoomsListView(generics.ListAPIView):
    """
    Get all live rooms visible to users
    """
    serializer_class = RoomSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Room.objects.filter(
            status='live',
            is_private=False,
            is_deleted=False
        ).select_related('host', 'room_type', 'language').prefetch_related('tags')
        
        # Filter by language if provided
        language = self.request.query_params.get('language')
        if language:
            queryset = queryset.filter(language_id=language)
        
        # Filter by room type if provided
        room_type = self.request.query_params.get('room_type')
        if room_type:
            queryset = queryset.filter(room_type_id=room_type)
        
        # Search by title
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )
        
        return queryset.order_by('-created_at')



class CreateRoomView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        create_serializer = CreateRoomSerializer(data=request.data)
        create_serializer.is_valid(raise_exception=True)

        # Save Room with additional fields
        room = create_serializer.save(
            host=request.user,
            started_at=timezone.now(),
            status='live'
        )

        # Add host as participant
        RoomParticipant.objects.create(
            user=request.user,
            room=room,
            role='host'
        )

        # Now return the full room data
        response_serializer = RoomSerializer(room)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)



class RoomDetailView(generics.RetrieveAPIView):
    """
    Get room details
    """
    serializer_class = RoomSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        room_id = self.kwargs['room_id']
        return get_object_or_404(Room, id=room_id, status='live')

class JoinRoomView(generics.CreateAPIView):
    """
    Join a room (for private rooms with password)
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, room_id):
        room = get_object_or_404(Room, id=room_id, status='live')
        password = request.data.get('password')
        
        # Check if room is private and password is required
        if room.is_private and room.password != password:
            return Response(
                {'error': 'Invalid password'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check max participants
        current_participants = room.participants.filter(left_at__isnull=True).count()
        if current_participants >= room.max_participants:
            return Response(
                {'error': 'Room is full'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if user is already in room
        existing_participant = RoomParticipant.objects.filter(
            user=request.user,
            room=room,
            left_at__isnull=True
        ).exists()
        
        if existing_participant:
            return Response(
                {'message': 'Already in room'},
                status=status.HTTP_200_OK
            )
        
        return Response(
            {'message': 'Can join room', 'room_id': room_id},
            status=status.HTTP_200_OK
        )

class LeaveRoomView(generics.CreateAPIView):
    """
    Leave a room
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, room_id):
        try:
            participant = RoomParticipant.objects.get(
                user=request.user,
                room_id=room_id,
                # left_at__isnull=True
            )
            participant.left_at = timezone.now()
            participant.save()
            
            return Response(
                {'message': 'Left room successfully'},
                status=status.HTTP_200_OK
            )
        except RoomParticipant.DoesNotExist:
            return Response(
                {'error': 'Not in this room'},
                status=status.HTTP_400_BAD_REQUEST
            )

class RoomParticipantsView(generics.ListAPIView):
    """
    Get room participants
    """
    serializer_class = RoomParticipantSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        room_id = self.kwargs['room_id']
        return RoomParticipant.objects.filter(
            room_id=room_id,
            left_at__isnull=True
        ).select_related('user')

class RoomMessagesView(generics.ListAPIView):
    """
    Get room messages
    """
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        room_id = self.kwargs['room_id']
        return Message.objects.filter(
            room_id=room_id,
            is_deleted=False
        ).select_related('user').order_by('-sent_at')[:50]

class MyRoomsView(generics.ListAPIView):
    """
    Get user's hosted rooms
    """
    serializer_class = RoomSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Room.objects.filter(
            host=self.request.user
        ).order_by('-created_at')

class EndRoomView(generics.UpdateAPIView):
    """
    End a room (host only)
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, room_id):
        room = get_object_or_404(Room, id=room_id, host=request.user)
        
        if room.status != 'live':
            return Response(
                {'error': 'Room is not live'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        room.status = 'ended'
        room.ended_at = timezone.now()
        room.save()
        
        return Response(
            {'message': 'Room ended successfully'},
            status=status.HTTP_200_OK
        )

class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [IsAuthenticated]

class RoomTypeViewSet(viewsets.ModelViewSet):
    queryset = RoomType.objects.all()
    serializer_class = RoomTypeSerializer
    permission_classes = [IsAuthenticated]


class ReportUserView(generics.CreateAPIView):
    serializer_class = ReportedRoomSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        room_id = self.kwargs['room_id']
        reported_user_id = self.kwargs['user_id']
        serializer.save(
            room=Room.objects.get(id=room_id),
            reported_by=self.request.user,
            reported_user_id=reported_user_id,
            status='pending'
        )
    