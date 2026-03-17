from django.shortcuts import render,redirect
from django.contrib.auth import authenticate, get_user_model,login,logout
from django.contrib import messages
from .forms import UserRegistion
User = get_user_model()
# Create your views here.
def signup(request):
    error_message = ""
    if request.method == "POST":
        print(request)
        print(request.POST.get('email'))
        form = UserRegistion(request.POST)
        print(form.errors)
        if form.is_valid():
            print(form.is_valid)
            user = form.save()
            print(f'{user.first_name} has been registered')
            return redirect('users:signin')
        else:
            error_message = form.errors
            return render(request, 'users/signup.html')
    else:
        form = UserRegistion()
    context={'error':error_message, 'form':form}
    return render(request, 'users/signup.html', context)

def signin(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        if not username or not password:
            print('no username or password')
            messages.error(request, 'Username and Password is required')
            return render(request, 'users/signin.html')
        try:
            user = User.objects.get(username=username)
            if user.check_password(password):
                login(request, user)
                print('login suceessfully')
                messages.success(request, 'Login Successful')
                return redirect('pages:new-order')
            else:
                messages.error(request, 'User is not unauthorized check your username and password')
                return render(request, 'users/sigin.html')
        except User.DoesNotExist:
            messages.error(request, 'The User with this email does not exist')
            return render(request, 'users/signin.html')
    return render(request, 'users/signin.html')

def signout(request):
    logout(request)
    return redirect('users:signin')
def reset_password(request):
    return render(request, 'users/password-reset.html')
