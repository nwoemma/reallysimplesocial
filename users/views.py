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
        
        context = {
            'username_error': '',
            'password_error': ''
        }
        
        if not username or not password:
            if not username:
                context['username_error'] = 'Username is required'
            if not password:
                context['password_error'] = 'Password is required'
            return render(request, 'users/signin.html', context)
            
        try:
            user = User.objects.get(username=username)
            if user.check_password(password):
                login(request, user)
                messages.success(request, 'Login Successful')
                return redirect('pages:new-order')
            else:
                context['password_error'] = 'Invalid password'
                return render(request, 'users/signin.html', context)
        except User.DoesNotExist:
            context['username_error'] = 'User with this username does not exist'
            return render(request, 'users/signin.html', context)
            
    return render(request, 'users/signin.html')


def signout(request):
    logout(request)
    return redirect('users:signin')
def reset_password(request):
    return render(request, 'users/password-reset.html')
