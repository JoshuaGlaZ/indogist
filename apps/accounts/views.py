from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import UserRegisterForm, UserUpdateForm
from apps.summarizer.models import Summary


def register(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('summarizer:home')

    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            messages.success(
                request, f'Account created for {username}! You can now log in.')
            login(request, user)
            return redirect('summarizer:home')
    else:
        form = UserRegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


@login_required
def profile(request):
    """User profile view with statistics"""
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)

        if u_form.is_valid():
            u_form.save()
            messages.success(request, 'Your profile has been updated!')
            return redirect('accounts:profile')
    else:
        u_form = UserUpdateForm(instance=request.user)

    total_summaries = Summary.objects.filter(user=request.user).count()
    context = {
        'u_form': u_form,
        'total_summaries': total_summaries,
    }

    return render(request, 'accounts/profile.html', context)