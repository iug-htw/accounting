from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render,redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from posts.models import Unternehmen,Absender, AufgabeDetail, Aufgabe_neu, NutzerAufgabe, Buchung, Aufgabenkategorie, Mail, Konto, Anfangsbestand, Kontenplan, Feedbackbereich
from posts.forms import  Aufgabe_neu_Form, AufgabenkategorieForm, UnternehmenForm, AufgabeBearbeitenForm, AufgabeDetailBearbeitenForm,KontoForm,AufgabeImportForm
from django.contrib import messages
import json, random, hashlib,openpyxl,threading,requests
from random import choice
from openpyxl import load_workbook
from django.urls import reverse
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.core.mail import send_mail
from django.db.models import Count, Q, F
from django.contrib.auth import get_user_model
from posts.absender import vornamen, nachnamen, straßen, staedte, plz, emailsuffix
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict
from django.utils.html import format_html
from django.views.decorators.http import require_GET
from decouple import config
from django.utils.translation import gettext as _
from django.db.models import Max