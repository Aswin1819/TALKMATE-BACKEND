from .serializers import *
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Q
from users.models import Notification
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .pagination import AdminDefaultPagination
from rest_framework.permissions import IsAuthenticated
from users.utils import set_auth_cookies, clear_auth_cookies
from rest_framework.pagination import PageNumberPagination
from rest_framework import status, permissions,generics,viewsets
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rooms.models import Room, RoomParticipant, Message, Tag, RoomType,ReportedRoom
from users.models import CustomUser, UserProfile, Language, SubscriptionPlan,UserSubscription

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

        users = CustomUser.objects.filter(is_superuser=False).order_by('-date_joined')
        status_param = request.query_params.get('status')
        search_param = request.query_params.get('search')

        # Filtering by status
        if status_param == 'premium':
            users = users.filter(userprofile__is_premium=True)
        elif status_param == 'banned':
            users = users.filter(userprofile__status='banned')
        elif status_param == 'flagged':
            users = users.filter(userprofile__status='flagged')
        # else 'all' or None: no filter

        # Searching by username or email
        if search_param:
            users = users.filter(
                Q(username__icontains=search_param) |
                Q(email__icontains=search_param)
            )

        paginator = PageNumberPagination()
        paginator.page_size = 5 
        paginated_users = paginator.paginate_queryset(users, request)
        serializer = UserListSerializer(paginated_users, many=True)
        return paginator.get_paginated_response(serializer.data)

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

        rooms = Room.objects.filter(is_deleted=False).select_related('host', 'room_type', 'language').prefetch_related('participants', 'tags')

        # Filters
        search = request.query_params.get('search')
        language = request.query_params.get('language')
        room_type = request.query_params.get('type')
        status_param = request.query_params.get('status')

        if search:
            rooms = rooms.filter(
                Q(title__icontains=search) |
                Q(host__username__icontains=search)
            )
        if language and language != 'all':
            rooms = rooms.filter(language__name=language)
        if room_type and room_type != 'all':
            rooms = rooms.filter(room_type__name=room_type)
        if status_param and status_param != 'all':
            rooms = rooms.filter(status=status_param)

        paginator = PageNumberPagination()
        paginator.page_size = int(request.query_params.get('page_size', 5))
        paginated_rooms = paginator.paginate_queryset(rooms.order_by('-created_at'), request)
        serializer = RoomListSerializer(paginated_rooms, many=True)
        response = paginator.get_paginated_response(serializer.data)
        return response
    
    
    
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
    pagination_class = AdminDefaultPagination

    def get_queryset(self):
        # Only allow superusers
        if not self.request.user.is_superuser:
            return ReportedRoom.objects.none()
    
        queryset = ReportedRoom.objects.select_related('reported_by', 'reported_user','room').order_by('-timestamp')
        
        search = self.request.query_params.get('search')
        reason = self.request.query_params.get('reason')
        
        if search:
            queryset = queryset.filter(
                Q(reported_by__username__icontains=search) |
                Q(reported_user__username__icontains=search)|
                Q(room__title__icontains=search)|
                Q(reason__icontains=search)
            )
        if reason:
            queryset = queryset.filter(reason=reason)
        
        return queryset
    
        
        
        
        
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
        if status_value not in ['resolved', 'dismissed', 'pending','suspend']:
            return Response({"detail": "Invalid status."}, status=status.HTTP_400_BAD_REQUEST)
        
        if status_value == "suspend":
            user_profile = get_object_or_404(UserProfile,user=report.reported_user)
            user = user_profile.user
            user_profile.status = 'banned'
            user.is_active = False
            report.status = 'resolved'
            user_profile.save()
            user.save()
            report.save()
             
        else:            
            report.status = status_value
            report.save()
            
        # Create notification for the reporter
        reporter = report.reported_by
        reported_user = report.reported_user
        room = report.room
        status_value = status_value if status_value != 'suspend' else 'suspend'
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
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AdminDefaultPagination
    

class AdminUserSubscriptionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superuser:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        
        
        subs = UserSubscription.objects.select_related('user', 'plan').all().order_by('-start_date')
        
        paginator = AdminDefaultPagination()
        paginator_subs = paginator.paginate_queryset(subs,request)
        serializer = UserSubscriptionSerializer(paginator_subs, many=True)
        return paginator.get_paginated_response(serializer.data)

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

class AdminStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Unauthorized'}, status=403)
        total_users = CustomUser.objects.filter(is_superuser=False).count()
        active_rooms = Room.objects.filter(status='live', is_deleted=False).count()
        premium_users = UserProfile.objects.filter(is_premium=True).count()
        flagged_content = ReportedRoom.objects.filter(status='pending').count()
        today = timezone.now().date()

        # Monthly (last 12 months)
        months = []
        user_growth = []
        for i in range(11, -1, -1):
            month_start = (today.replace(day=1) - timedelta(days=30*i)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1)
            count = CustomUser.objects.filter(
                is_superuser=False,
                date_joined__gte=month_start,
                date_joined__lt=month_end
            ).count()
            months.append(month_start.strftime('%b %Y'))
            user_growth.append(count)

        # Weekly (last 6 weeks)
        weeks = []
        week_growth = []
        for i in range(5, -1, -1):
            week_start = today - timedelta(days=today.weekday() + 7*i)
            week_end = week_start + timedelta(days=7)
            count = CustomUser.objects.filter(
                is_superuser=False,
                date_joined__gte=week_start,
                date_joined__lt=week_end
            ).count()
            # Use ISO week number for label
            weeks.append(week_start.isocalendar()[1])
            week_growth.append(count)

        # Daily (last 31 days)
        days = []
        day_growth = []
        for i in range(30, -1, -1):
            day = today - timedelta(days=i)
            next_day = day + timedelta(days=1)
            count = CustomUser.objects.filter(
                is_superuser=False,
                date_joined__gte=day,
                date_joined__lt=next_day
            ).count()
            days.append(day.strftime('%Y-%m-%d'))
            day_growth.append(count)

        return Response({
            'total_users': total_users,
            'active_rooms': active_rooms,
            'premium_users': premium_users,
            'flagged_content': flagged_content,
            'user_growth': user_growth,
            'months': months,
            'week_growth': week_growth,
            'weeks': weeks,
            'day_growth': day_growth,
            'days': days,
        })

class AdminRecentActivityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Unauthorized'}, status=403)
        activities = []
        # Room creations
        for room in Room.objects.order_by('-created_at')[:5]:
            activities.append({
                'user': room.host.username if room.host else 'Unknown',
                'action': 'created a new room',
                'target': room.title,
                'time': room.created_at.strftime('%b %d, %H:%M')
            })
        # Reports
        for report in ReportedRoom.objects.order_by('-timestamp')[:5]:
            activities.append({
                'user': report.reported_by.username if report.reported_by else 'System',
                'action': 'reported',
                'target': f'message in {report.room.title}',
                'time': report.timestamp.strftime('%b %d, %H:%M')
            })
        # Premium upgrades
        for sub in UserSubscription.objects.order_by('-start_date')[:5]:
            activities.append({
                'user': sub.user.username,
                'action': 'upgraded to',
                'target': sub.plan.name,
                'time': sub.start_date.strftime('%b %d, %H:%M')
            })
        # Sort by time descending
        activities = sorted(activities, key=lambda x: x['time'], reverse=True)[:10]
        return Response({'recent_activity': activities})