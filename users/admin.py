from django.contrib import admin
from .models import CustomUser, UserProfile, Language, Friendship, OTP,UserLanguage

# Register your models here.
admin.site.register(CustomUser)
admin.site.register(UserProfile)    
admin.site.register(Language)
admin.site.register(OTP)
admin.site.register(Friendship)
admin.site.register(UserLanguage)

