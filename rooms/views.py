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
from .models import Room, RoomParticipant, Message, Tag, RoomType,UserActivity
from .serializers import (
    RoomSerializer, CreateRoomSerializer, RoomParticipantSerializer,
    MessageSerializer, TagSerializer, RoomTypeSerializer,ReportedRoomSerializer
)
from datetime import timedelta

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
        if RoomParticipant.objects.filter(user=request.user, left_at__isnull=True).exists():
            return Response({'error': 'Leave your current room first.'}, status=403)

        create_serializer = CreateRoomSerializer(data=request.data)
        create_serializer.is_valid(raise_exception=True)

        # Save Room with additional fields
        room = create_serializer.save(
            host=request.user,
            started_at=timezone.now(),
            status='live'
        )

        # Add host as participant
        RoomParticipant.objects.update_or_create(
            user=request.user,
            room=room,
            defaults={'role': 'host'}
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

class JoinRoomView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        room = get_object_or_404(Room, id=room_id, status='live')

        # Enforce password check for private rooms
        if room.is_private:
            password = request.data.get('password')
            if not password or not room.check_password(password):
                return Response({'error': 'Invalid password'}, status=403)

        # Check if user is already in any active room
        active_room_participant = RoomParticipant.objects.filter(user=request.user, left_at__isnull=True).first()
        if active_room_participant:
            if active_room_participant.room_id == room.id:
                return Response({'message': 'Already in this room'}, status=200)
            else:
                return Response({'error': 'Already in another room. Leave it first.'}, status=403)

        # Rejoining logic: revive old participant if exists
        participant, created = RoomParticipant.objects.get_or_create(
            user=request.user,
            room=room,
            defaults={'role': 'participant'}
        )
        if not created:
            participant.left_at = None  # Reset left_at to "rejoin"
            participant.save()

        return Response({'message': 'Joined room successfully'}, status=200)


class LeaveRoomView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, room_id):
        try:
            print("Inside try")
            participant = RoomParticipant.objects.get(
                user=request.user,
                room_id=room_id,
                left_at__isnull=True
            )
            print("After participant")
            now = timezone.now()
            participant.left_at = now
            participant.save()

            # Calculate session duration
            session_duration = (participant.left_at - participant.joined_at)
            minutes = int(session_duration.total_seconds() // 60)
            if minutes < 1:
                minutes = 1

            # Update user profile
            profile = request.user.userprofile
            profile.total_speak_time = (profile.total_speak_time or timedelta()) + timedelta(minutes=minutes)
            profile.xp += minutes * 20
            profile.level = profile.xp // 1000 + 1
            profile.save()

            # Log daily activity for streaks and stats
            today = now.date()
            activity, _ = UserActivity.objects.get_or_create(user=request.user, date=today)
            activity.xp_earned += minutes * 20
            activity.practice_minutes += minutes
            print("PracticeMinutes:",activity.practice_minutes)
            activity.save()
            print("till activity executed")

            return Response({'message': 'Left room, stats updated.'})
        except RoomParticipant.DoesNotExist:
            print("error in leave room view")
            return Response({'error': 'Not in room.'}, status=400)

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
