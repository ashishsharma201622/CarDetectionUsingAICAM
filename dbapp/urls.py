from django.urls import path
from . import views
app_name = "number"

urlpatterns = [
    path("", views.MainView,name="main"),
    path("edit/<str:number>",views.EditNumber,name='edit'),
    path("delete/<str:number>",views.DeleteNumber,name='delete'),
    path("timei/",views.LocalView,name='timei'),
    path("timei_edit/<str:timei>",views.EditTimei,name='timei_edit'),
    path("timei_delete/<str:timei>",views.DeleteTimei,name='timei_delete'),
    path("log/", views.LogView, name='log'),

]