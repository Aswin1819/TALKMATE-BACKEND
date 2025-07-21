import re
from .models import *
from django.db.models import Q
from datetime import timedelta,date
from rooms.models import UserActivity
from rest_framework import serializers
from django.utils.timesince import timesince
from .utils import upload_avatar_to_cloudinary
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import make_password
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer



class CustomUserSerializer(serializers.ModelSerializer):
    profile_summary = serializers.SerializerMethodField()
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'is_verified', 'password', 'profile_summary']
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True}
        }

    def get_profile_summary(self, obj):
        try:
            profile = obj.userprofile
            friends_count = Friendship.objects.filter(
                (Q(from_user=obj) | Q(to_user=obj)) & Q(status='accepted')
            ).count()
            return {
                'avatar': profile.avatar,
                'level': profile.level,
                'is_premium':profile.is_premium,
                'followers': profile.followers.count(),
                'following': profile.following.count(),
                'friends': friends_count,
            }
        except UserProfile.DoesNotExist:
            return None

    def validate_username(self,value):
            if not re.match(r'^[A-Za-z]+( [A-Za-z]+)*$', value):
                raise serializers.ValidationError("Username must contain only letters and spaces between words.")
            return value
    
    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)


class GoogleLoginSerializer(serializers.Serializer):
    user = serializers.HiddenField(default=None)
    
    def validate(self,attrs):
        user = self.context['user']
        
        if not user.is_active:
            raise serializers.ValidationError('Your account has been deactivated')
        if not user.is_verified:
            raise serializers.ValidationError('Your email is not verifeid')
        if user.is_superuser:
            raise serializers.ValidationError('Superusers cannot log in this way')
        
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        avatar = None
        followers_count = 0
        following_count = 0
        friends_count = 0
        level = 0
        
        try:
            profile=user.userprofile
            avatar=profile.avatar
            level=profile.level
            is_premium=profile.is_premium
            followers_count=profile.followers.count()
            following_count=profile.following.count()
            friends_count=Friendship.objects.filter(
                (Q(from_user=user) | Q(to_user=user)) & Q(status='accepted')
            ).count()
        except UserProfile.DoesNotExist:
            pass
        
        return {
            'access':access_token,
            'refresh':refresh_token,
            'user': {
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'is_verified': user.is_verified,
                'is_premium': is_premium,
                'avatar': avatar,
                'level': level,
                'followers_count': followers_count,
                'following_count': following_count,
                'friends_count': friends_count,
            }
        }
        




        
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['email'] = user.email
        token['username'] = user.username
        token['user_id'] = user.id
        token['is_verified'] = user.is_verified
        return token

    def validate(self, attrs):
        try:
            data = super().validate(attrs)
        except Exception as e:
            raise AuthenticationFailed("Invalid credentials provided.")

        # Additional user validation
        if not self.user.is_verified:
            raise AuthenticationFailed("Email is not verified. Please verify your account.")
        
        if not self.user.is_active:
            raise AuthenticationFailed("Your account has been blocked by the admin.")
        
        if self.user.is_superuser:
            raise AuthenticationFailed("Superusers cannot log in through this endpoint.")

        # Get avatar from UserProfile
        avatar = None
        is_premium = None
        followers_count = 0
        following_count = 0
        friends_count = 0
        level = 0
        try:
            profile = self.user.userprofile
            avatar = profile.avatar
            level = profile.level
            is_premium = profile.is_premium
            followers_count = profile.followers.count()
            following_count = profile.following.count()
            friends_count = Friendship.objects.filter(
                (Q(from_user=self.user) | Q(to_user=self.user)) & Q(status='accepted')
            ).count()
        except UserProfile.DoesNotExist:
            print("UserProfile does not exist for user:", self.user.id)

        data.update({
            'user': {
                'user_id': self.user.id,
                'username': self.user.username,
                'email': self.user.email,
                'is_verified': self.user.is_verified,
                'is_premium':is_premium,
                'avatar': avatar,
                'level': level,
                'followers_count': followers_count,
                'following_count': following_count,
                'friends_count': friends_count,
            }
        })
        return data
    
class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = ['id','name','code']
    
    def validate_name(self, value):
        if self.instance:
            if Language.objects.filter(name__iexact=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError("Language with this name already exists")
        else:
            if Language.objects.filter(name__iexact=value).exists():
                raise serializers.ValidationError("Language with this name already exists")
        return value
        
        
class UserLanguageSerializer(serializers.ModelSerializer):
    language = LanguageSerializer()
    
    class Meta:
        model = UserLanguage
        fields = ['id', 'language', 'is_learning', 'proficiency']

        
class UserProfileSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer(read_only=True)
    native_languages = serializers.SerializerMethodField()
    learning_languages = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    friends_count = serializers.SerializerMethodField()
    last_seen_display = serializers.SerializerMethodField()
    date_joined = serializers.SerializerMethodField(source='user.date_joined')
    subscription = serializers.SerializerMethodField()
    current_streak = serializers.SerializerMethodField()
    daily_xp = serializers.SerializerMethodField()
    weekly_practice_hours = serializers.SerializerMethodField()
    class Meta:
        model = UserProfile
        fields = [
            'id', 'user', 'unique_id', 'avatar', 'bio', 'native_languages',
            'learning_languages', 'status', 'is_premium', 'xp', 'level', 'streak',
            'total_speak_time', 'total_rooms_joined', 'is_online', 'last_seen', 
            'last_seen_display', 'following', 'followers_count', 'following_count',
            'friends_count','date_joined','subscription','current_streak','daily_xp',
            'weekly_practice_hours'
        ]
    def get_followers_count(self, obj):
        return obj.followers.count()
    
    def get_following_count(self, obj):
        return obj.following.count()

    def get_friends_count(self, obj):
        return obj.following.filter(following=obj).distinct().count()
    
    def get_last_seen_display(self, obj):
        if obj.last_seen:
            return timesince(obj.last_seen) + "ago"
        return "Never"
    def get_native_languages(self, obj):
        langs = obj.userlanguage_set.filter(is_learning=False)
        return UserLanguageSerializer(langs, many=True).data

    def get_learning_languages(self, obj):
        langs = obj.userlanguage_set.filter(is_learning=True)
        return UserLanguageSerializer(langs, many=True).data
    
    def get_date_joined(self, obj):
        return obj.user.date_joined if obj.user and hasattr(obj.user, 'date_joined') else None
    
    def get_subscription(self,obj):
        try:
            sub = obj.user.subscription
            return UserSubscriptionSerializer(sub).data
        except UserSubscription.DoesNotExist:
            return None
    
    def get_current_streak(self, obj):
        user = obj.user
        today = date.today()
        streak = 0
        for i in range(0, 100):  # reasonable max streak
            day = today - timedelta(days=i)
            if UserActivity.objects.filter(user=user, date=day).exists():
                streak += 1
            else:
                if i == 0:
                    continue  # allow for today being inactive so far
                break
        return streak

    def get_daily_xp(self, obj):
        user = obj.user
        today = date.today()
        activity = UserActivity.objects.filter(user=user, date=today).first()
        return activity.xp_earned if activity else 0

    def get_weekly_practice_hours(self, obj):
        user = obj.user
        today = date.today()
        week_ago = today - timedelta(days=6)
        activities = UserActivity.objects.filter(user=user, date__gte=week_ago, date__lte=today)
        total_minutes = sum(a.practice_minutes for a in activities)
        print("total_minutes:",total_minutes)
        return round(total_minutes / 60, 1)
    
    
class OTPSerializer(serializers.ModelSerializer):
    class Meta:
        model = OTP
        fields = ['id','user','code','created_at','expires_at']
        read_only_fields = ['created_at']
        
        
class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            user = CustomUser.objects.get(email=value)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")

        if user.is_verified:
            raise serializers.ValidationError("User is already verified.")

        self.context['user'] = user
        return value
        




class PasswordResetOTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)

    def validate(self, data):
        email = data.get('email')
        code = data.get('code')
        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("User not found.")

        try:
            otp_obj = OTP.objects.filter(user=user, code=code, is_used=False).latest('created_at')
        except OTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP.")

        if otp_obj.is_expired():
            raise serializers.ValidationError("OTP expired.")

        data['user'] = user
        data['otp_obj'] = otp_obj
        return data

class PasswordResetResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            user = CustomUser.objects.get(email=value)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("User not found.")
        self.context['user'] = user
        return value
    
    
class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)

    def validate(self, data):
        email = data.get('email')
        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("User not found.")

        data['user'] = user
        return data

    def save(self):
        user = self.validated_data['user']
        password = self.validated_data['password']
        user.set_password(password)
        user.save()
        return user


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(required=False, allow_null=True)
    bio = serializers.CharField(required=False, allow_blank=True)
    native_languages = serializers.ListField(child=serializers.DictField(), required=False)
    learning_languages = serializers.ListField(child=serializers.DictField(), required=False)

    class Meta:
        model = UserProfile
        fields = ['avatar', 'bio', 'native_languages', 'learning_languages']

    def update(self, instance, validated_data):
        print("=== UserProfileUpdateSerializer.update called ===")
        print("Validated data:", validated_data)
        avatar_file = validated_data.pop('avatar', None)
        if avatar_file:
            avatar_url = upload_avatar_to_cloudinary(avatar_file)
            print("Cloudinary returned URL:", avatar_url)
            instance.avatar = avatar_url

        # Update bio
        bio = validated_data.pop('bio', None)
        if bio is not None:
            instance.bio = bio

        # Update native languages
        native_langs = validated_data.pop('native_languages', None)
        if native_langs is not None:
            instance.userlanguage_set.filter(is_learning=False).delete()
            for lang in native_langs:
                UserLanguage.objects.create(
                    user_profile=instance,
                    language_id=lang['language'],
                    is_learning=False,
                    proficiency=lang['proficiency']
                )

        # Update learning languages
        learning_langs = validated_data.pop('learning_languages', None)
        if learning_langs is not None:
            instance.userlanguage_set.filter(is_learning=True).delete()
            for lang in learning_langs:
                UserLanguage.objects.create(
                    user_profile=instance,
                    language_id=lang['language'],
                    is_learning=True,
                    proficiency=lang['proficiency']
                )

        instance.save()
        print("Instance after save. Avatar URL:", instance.avatar)
        return instance



class UserSettingsSerializer(serializers.ModelSerializer):
    language_name = serializers.CharField(source='language.name', read_only=True)
    language_code = serializers.CharField(source='language.code', read_only=True)
    is_google_login = serializers.BooleanField(source='user.is_google_login', read_only=True)
    
    class Meta:
        model = UserSettings
        fields = [
            'id',
            'dark_mode',
            'email_notifications', 
            'practice_reminders',
            'room_interest_notifications',
            'browser_notifications',
            'public_profile',
            'show_online_status',
            'language',
            'language_name',
            'language_code',
            'timezone',
            'is_google_login'
        ]
        
    def validate(self, data):
        if not data.get('email_notifications', True):
            data['practice_reminders'] = False
            data['room_interest_notifications'] = False
        return data
    

class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    confirm_password = serializers.CharField(required=True)
    
    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value
    
    def validate_new_password(self, value):
        try:
            validate_password(value, self.context['request'].user)
        except ValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value
    
    def validate(self, data):
        user = self.context['request'].user
        if getattr(user,'is_google_login',False):
            raise serializers.ValidationError("Password change is not allowed for google login users")
        
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("New passwords do not match.")
        
        if data['current_password'] == data['new_password']:
            raise serializers.ValidationError("New password must be different from current password.")
        
        return data
    
    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user

class NotificationSerializer(serializers.ModelSerializer):
    time = serializers.SerializerMethodField()
    class Meta:
        model = Notification
        fields = ['id', 'type', 'title', 'message', 'is_read', 'created_at', 'link', 'time']

    def get_time(self, obj):
        return timesince(obj.created_at) + ' ago'
    


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ['id', 'name', 'price', 'duration_days', 'features', 'is_active']

class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer()
    class Meta:
        model = UserSubscription
        fields = ['plan', 'start_date', 'end_date', 'is_active', 'payment_id', 'payment_status']
        
class SubscriptionPlanMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ['id', 'name', 'price']  # only return necessary fields


class UserSubscriptionHistorySerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanMiniSerializer()  # nested serializer
    
    class Meta:
        model = UserSubscriptionHistory
        fields = ['id', 'plan', 'start_date', 'end_date', 'payment_id', 'payment_status']


class FollowersProfileSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='users.username',read_only="True")
    class Meta:
        model = UserProfile
        fields = ['id','avatar','level']


class FollowListSerializer(serializers.ModelSerializer):
    followers = UserProfileSerializer(many=True,read_only=True)
    following = UserProfileSerializer(many=True,read_only=True)

    class Meta:
        model = UserProfile
        fields = ['followers','following']
        
class FollowCardSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()
    relationship_state = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            'id',            # profile id
            'unique_id',     # short code / uuid
            'avatar',
            'level',
            'is_online',
            'is_premium',
            'username',
            'relationship_state',
        ]

    def _viewer(self):
        return self.context.get('viewer_profile')

    def get_username(self, obj):
        user = getattr(obj, 'user', None)
        return user.username if user else obj.unique_id

    def get_relationship_state(self, obj):
        viewer = self._viewer()
        if not viewer:
            return 'none'
        following = viewer.is_following(obj)      # viewer follows obj?
        follower = viewer.is_followed_by(obj)     # obj follows viewer?
        if following and follower:
            return 'friend'
        if following:
            return 'following'
        if follower:
            return 'follower'
        return 'none'

        
class SocialActionResponseSerializer(serializers.Serializer):
    target_profile_id = serializers.IntegerField()
    target_user_id = serializers.IntegerField()
    relationship_state = serializers.ChoiceField(choices=['none','follower','following','friend'])
    is_following = serializers.BooleanField()
    is_follower = serializers.BooleanField()
    message = serializers.CharField()

    @staticmethod
    def build(*, viewer_profile, target_profile, message):
        is_following = viewer_profile.is_following(target_profile)
        is_follower = viewer_profile.is_followed_by(target_profile)
        if is_following and is_follower:
            rel = 'friend'
        elif is_following:
            rel = 'following'
        elif is_follower:
            rel = 'follower'
        else:
            rel = 'none'
        payload = {
            'target_profile_id': target_profile.id,
            'target_user_id': target_profile.user_id,
            'relationship_state': rel,
            'is_following': is_following,
            'is_follower': is_follower,
            'message': message,
        }
        return SocialActionResponseSerializer(payload).data