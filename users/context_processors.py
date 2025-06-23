from posts.models import Mail

def unread_mails_count(request):
    if request.user.is_authenticated:
        count = Mail.objects.filter(nutzer=request.user, status="nicht bearbeitet").count()
        return {'unread_mail_count': count}
    return {}