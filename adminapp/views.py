from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from users.models import CustomUser, UserProfile
from .serializers import AdminLoginSerializer, UserListSerializer, UserProfileDetailSerializer
from rest_framework.permissions import IsAuthenticated
from users.utils import set_auth_cookies, clear_auth_cookies
from django.shortcuts import get_object_or_404

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
