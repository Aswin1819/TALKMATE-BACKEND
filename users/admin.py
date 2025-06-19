from django.contrib import admin
from .models import *

# Register your models here.
admin.site.register(CustomUser)
admin.site.register(UserProfile)    
admin.site.register(Language)
admin.site.register(OTP)
admin.site.register(Friendship)
admin.site.register(UserLanguage)
admin.site.register(UserSettings)

