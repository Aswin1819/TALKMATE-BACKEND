from rest_framework import serializers
from users.models import CustomUser, UserProfile, Language, UserLanguage
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class AdminLoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['is_superuser'] = user.is_superuser
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        if not self.user.is_superuser:
            raise serializers.ValidationError("You are not authorized as an admin.")
        
        data.update({
            'user_id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'is_superuser': self.user.is_superuser
        })
        return data

class UserListSerializer(serializers.ModelSerializer):
    is_premium = serializers.BooleanField(source='userprofile.is_premium', read_only=True)
    avatar = serializers.URLField(source='userprofile.avatar', read_only=True)
    level = serializers.IntegerField(source='userprofile.level', read_only=True)
    status = serializers.CharField(source='userprofile.status', read_only=True)
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'is_active', 'is_verified', 'date_joined',
                  'is_premium', 'avatar', 'level', 'status']

class UserProfileDetailSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    is_verified = serializers.BooleanField(source='user.is_verified', read_only=True)
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    following_count = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    languages = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            'user_id', 'username', 'email', 'is_verified', 'date_joined',
            'unique_id', 'avatar', 'bio', 'status', 'is_premium', 'xp', 'level', 'streak',
            'total_speak_time', 'total_rooms_joined', 'is_online', 'last_seen',
            'following_count', 'followers_count', 'languages'
        ]

    def get_following_count(self, obj):
        return obj.following.count()

    def get_followers_count(self, obj):
        return obj.followers.count()

    def get_languages(self, obj):
        user_languages = UserLanguage.objects.filter(user_profile=obj)
        return [
            {
                'language': ul.language.name,
                'code': ul.language.code,
                'is_learning': ul.is_learning,
                'proficiency': ul.proficiency
            }
            for ul in user_languages
        ]
