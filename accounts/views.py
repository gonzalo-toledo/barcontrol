from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views import View
from .forms import LoginForm


class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('upload_invoice')
        form = LoginForm()
        return render(
            request,
            'accounts/login.html',
            {
                "form": form
            }
        )
    def post (self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]

            user = authenticate(  #authtenticate verifica si el usuario existe pero no lo loguea
                request, 
                username=username, 
                password=password
            )
            
            if user is not None: #se usa None porque si no existe el usuario devuelve None
                login(request, user) #loguea al usuario
                return redirect('upload_invoice')
            else:
                messages.error(request, "Usuario o contraseña incorrectos")
                
        return render(request, 
            "accounts/login.html", 
            {"form": form}) 


class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect('login')