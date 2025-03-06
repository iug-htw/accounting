### Dokumentation und Progress-Log der Frontend- und CSS-Implementierung der Buchführungs-App *Individuelles Tempo*

Dieses Dokument dient als zentrale Anlaufstelle, um alle Veränderungen und Anpassungsschritte für das Frontend sowie die Implementierung des visuellen Prototyps zu dokumentieren und zu beschreiben. 
Es enthält zudem die nächsten **TODOs**, offene Fragen und festgehaltenes Feedback.

---

## **Entwickler**
- **Felix Bartl**: Realisator der App  
- **Ann-Jacqueline Kaldjob (Ann) (SHK)**: Unterstützung bei der Umsetzung des Frontend-Designs

---

## **Stand des Frontends**

### **Ausgangspunkt**
#### Prototyp Version C (Mockup, Dezember 2024)  
Der initiale Prototyp in Version C wurde in Mockup-Form entwickelt. Eine Implementierung in Code lag zu diesem Zeitpunkt noch nicht vor.  
**Referenzdatei:** [Prototype_Version_C.pdf](media/Prototype_Version_C.pdf)

---

### **Stand 1 (20. Januar 2025)**

1. **Homepage (http://localhost:8000/home/):**  
   - Erste Version der Startseite in Rohform teilweise nachgebaut.  
   - Elemente sind sichtbar, aber Weiterleitungsfunktionen fehlen noch.  
   - Zugriff nur durch manuelles Routing möglich (noch nicht über das Hauptinterface).

2. **Masterlayout (http://localhost:8000/layout/):**  
   - Erste Version des Masterlayouts erstellt.  
   - Grundstruktur für Navigation und Layout steht.


3. **Neue Dateien:**

#### Bilder unter `media/`:
- `securenet-logo.png` (Logo der App)
- `notification-alert-svgrepo-com.png` (Benachrichtigungssymbol)

#### HTML-Dateien unter `post/templates/posts/`:
- `home.html` (Homepage der App)
- `layout.html` (Grundlayout für die Seitenstruktur)

#### CSS-Dateien unter `static/css/`:
- `frontpage.css` (Stylesheet für die Homepage)
- `layout.css` (Stylesheet für das allgemeine Layout und Navigationselemente)

#### Views unter `young_wolf/views.py`:
- `def masterlayout(request)` Rendert beim request der HTML Seite die Route `post/master_layout`
- `def frontpage(request)` Rendert beim request der HTML Seite die Route `post/frontpage`

#### Neue Routen unter `young_wolf/urls.py`:
 #### Hinzugefügt: 
    path('layout/', views.masterlayout, name='master_layout'),

    path('home/', views.frontpage, name='frontpage'),
---

### **TODOs für Stand 1**
- Weiterentwicklung der Homepage:
  - **Responsive Design** für Laptop- und Monitoransichten optimieren.  
  - Logo- und Navigationselemente verfeinern.
  - UI knöpfe die richtig routen (Mock up)
  - Bei weten dummy werte
  - warnungsfenster z.B 
  - Logik für hauptbuch 
  - aufgaben erstellen anpassen
  - 

---

### Stand 2 (17.02)
- Masterlayout anpassungen
- Rechnungsansicht angepasst

## Stand 3 (19.02)
- Frontpage angepasst
- _Bilanz und GUV leichte Anpassungen aber noch änderungen und Feedback nötig
- hauptbuch angepasst

## **Start des Projekts: Virtuelle Umgebung und App**
Um die App zu starten, sind die folgenden Schritte erforderlich:

### **Virtuelle Umgebung (venv) erstellen und aktivieren**
#### Für Windows:
```bash
 venv\Scripts\activate
```

#### Für macOS/Linux:
```bash
 source venv/bin/activate
```

### ** App starten**
```bash
python manage.py runserver
```
- git push origin branch1  
---

