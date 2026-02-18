from django.urls import path
from users import views
from pages import views2
app_name = "users"

urlpatterns = [
    path('signup/', views.signup, name="signup" ),
    path('',views.signin, name="signin"),
    path('signout/', views.signout, name='signout' ),
    path('check-auth/', views2.check_auth, name='check-auth'),
    path('password-reset/', views.reset_password, name="reset_password")
]
