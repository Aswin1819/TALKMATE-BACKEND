from rest_framework import status, permissions,generics,viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from users.models import CustomUser, UserProfile, Language, SubscriptionPlan,UserSubscription
from rooms.models import Room, RoomParticipant, Message, Tag, RoomType,ReportedRoom
from .serializers import *
from rest_framework.permissions import IsAuthenticated
from users.utils import set_auth_cookies, clear_auth_cookies
from django.shortcuts import get_object_or_404
from django.utils import timezone
from users.models import Notification
 

class AdminLoginView(TokenObtainPairView):
    serializer_class = AdminLoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_401_UNAUTHORIZED)

        validated_data = serializer.validated_data
        access_token = validated_data.get('access')
        refresh_token = validated_data.get('refresh')

        response = Response({
            'message': 'Admin login successful',
            'admin': {
                'user_id': validated_data.get('user_id'),
                'username': validated_data.get('username'),
                'email': validated_data.get('email'),
                'is_superuser': validated_data.get('is_superuser'),
            }
        }, status=status.HTTP_200_OK)

        set_auth_cookies(
            response,
            access_token,
            refresh_token,
            access_cookie='admin_access_token',
            refresh_cookie='admin_refresh_token'
        )
        return response

# For refresh:
class AdminTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        # Get refresh token from cookie if not in request.data
        if 'refresh' not in request.data:
            refresh_token = request.COOKIES.get('admin_refresh_token')
            if refresh_token:
                request.data['refresh'] = refresh_token
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            access_token = response.data.get('access')
            refresh_token = response.data.get('refresh')
            set_auth_cookies(
                response,
                access_token,
                refresh_token,
                access_cookie='admin_access_token',
                refresh_cookie='admin_refresh_token'
            )
        return response

class AdminUserListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superuser:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        users = CustomUser.objects.filter(is_superuser=False)
        serializer = UserListSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class AdminUserProfileDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        if not request.user.is_superuser:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        user_profile = get_object_or_404(UserProfile, user__id=user_id)
        serializer = UserProfileDetailSerializer(user_profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

class AdminUserStatusUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        if not request.user.is_superuser:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        user_profile = get_object_or_404(UserProfile, user__id=user_id)
        user = user_profile.user
        action = request.data.get('action')
        if action == 'banned':
            user_profile.status = 'banned'
            user.is_active = False
            user_profile.save()
            user.save()
            return Response({"detail": "User banned."}, status=status.HTTP_200_OK)
        elif action == 'active':
            user_profile.status = 'active'
            user.is_active = True
            user_profile.save()
            user.save()
            return Response({"detail": "User unbanned."}, status=status.HTTP_200_OK)
        else:
            return Response({"detail": "Invalid action."}, status=status.HTTP_400_BAD_REQUEST)


class AdminRoomListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superuser:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        rooms = Room.objects.filter(
            is_deleted=False
        ).select_related(
            'host', 'room_type', 'language'
        ).prefetch_related(
            'participants', 'tags'
        )
        serializer = RoomListSerializer(rooms, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    
    
class AdminRoomDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        if not request.user.is_superuser:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        room = get_object_or_404(
            Room.objects.select_related('host', 'room_type', 'language').prefetch_related('tags', 'participants'),
            id=room_id
        )
        serializer = RoomDetailSerializer(room)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, room_id):
        if not request.user.is_superuser:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        room = get_object_or_404(Room, id=room_id)
        room.is_deleted = True
        room.status = 'ended'
        room.ended_at = timezone.now()
        room.save()
        return Response({"detail": "Room deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
    
    def patch(self, request, room_id):
        if not request.user.is_superuser:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        room = get_object_or_404(Room, id=room_id)
        serializer = AdminRoomEditSerializer(room, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            # Return updated details
            detail_serializer = RoomDetailSerializer(room)
            return Response(detail_serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
    
    


class LanguageListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        languages = Language.objects.all()
        return Response([{'id': l.id, 'name': l.name} for l in languages])

class RoomTypeListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        types = RoomType.objects.all()
        return Response([{'id': t.id, 'name': t.name} for t in types])

class TagListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        tags = Tag.objects.all()
        return Response([{'id': tag.id, 'name': tag.name} for tag in tags])
    


class AdminReportedRoomListView(generics.ListAPIView):
    serializer_class = AdminReportedRoomSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only allow superusers
        if not self.request.user.is_superuser:
            return ReportedRoom.objects.none()
        return ReportedRoom.objects.select_related('reported_by', 'reported_user', 'room').order_by('-timestamp')

class AdminReportedRoomStatusUpdateView(generics.UpdateAPIView):
    serializer_class = AdminReportedRoomSerializer
    permission_classes = [IsAuthenticated]
    queryset = ReportedRoom.objects.all()
    lookup_field = 'pk'

    def patch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        report = self.get_object()
        status_value = request.data.get('status')
        if status_value not in ['resolved', 'dismissed', 'pending']:
            return Response({"detail": "Invalid status."}, status=status.HTTP_400_BAD_REQUEST)
        report.status = status_value
        report.save()
        # Create notification for the reporter
        reporter = report.reported_by
        reported_user = report.reported_user
        room = report.room
        status_display = status_value.capitalize()
        Notification.objects.create(
            user=reporter,
            type=Notification.NotificationType.REPORT,
            title=f"Your report has been {status_display}",
            message=f"Your report against user '{reported_user.username}' in room '{room.title}' has been {status_display.lower()} by an admin.",
            link=None
        )
        serializer = self.get_serializer(report)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    queryset = SubscriptionPlan.objects.filter(is_active=True)
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsAuthenticated]
    

class AdminUserSubscriptionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superuser:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        subs = UserSubscription.objects.select_related('user', 'plan').all()
        serializer = UserSubscriptionSerializer(subs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class AdminUserSubscriptionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        if not request.user.is_superuser:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        try:
            sub = UserSubscription.objects.select_related('user', 'plan').get(user__id=user_id)
        except UserSubscription.DoesNotExist:
            return Response({"detail": "Subscription not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = UserSubscriptionSerializer(sub)
        return Response(serializer.data, status=status.HTTP_200_OK)