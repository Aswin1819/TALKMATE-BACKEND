from django.contrib import admin
from .models import *

# Register your models here.
admin.site.register(Room)
admin.site.register(RoomType)
admin.site.register(Tag)
admin.site.register(RoomParticipant)
admin.site.register(Message)

admin.site.site_header = "Rooms Admin"