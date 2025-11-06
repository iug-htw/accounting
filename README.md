# 🧾 Accounting Learning Platform (HTW Berlin)

**Lernplattform zur Unterstützung von Studierenden beim Üben von Buchungssätzen im externen Rechnungswesen.**  
Entwickelt im Rahmen des *Curriculum Innovation Hub* an der **HTW Berlin**.

---

## 🎯 Projektbeschreibung

Die Anwendung ermöglicht Studierenden, in die Rolle der Gründer*innen eines fiktiven Startups zu schlüpfen und Geschäftsvorfälle selbst zu buchen.  
Sie erhalten automatisiertes Feedback – teilweise KI-generiert – und können ihre Buchungen in **Hauptbuch**, **GuV** und **Bilanz** nachvollziehen.

### Lehrende können:
- Aufgaben und Fallstudien (Unternehmen) erstellen  
- Kontenpläne verwalten  
- Studierende anlegen und Aufgaben zuweisen  
- Lernfortschritte und typische Fehler einsehen  

---

## ⚙️ Technische Grundlage

Das Projekt basiert auf **Django 5.1 (Python)** und nutzt:
- **HTML, CSS, JavaScript** für das Frontend  
- **SQLite** als lokale Datenbank  
- **Gunicorn + Nginx** für die Produktivumgebung  
- **Ollama API** für KI-basiertes Feedback  

---

## 🧩 Installation & Einrichtung (lokal)

### Repository klonen
```bash
git clone https://github.com/iug-htw/accounting.git
cd accounting
```

### Virtuelle Umgebung erstellen & aktivieren
```bash
python -m venv .env
source .env/bin/activate       # macOS/Linux
.env\Scripts\activate          # Windows
```

### Abhängigkeiten installieren
```bash
pip install -r requirements.txt
```

### Datenbank vorbereiten
```bash
python manage.py makemigrations
python manage.py migrate
```

### Admin-User
Login-Daten sind bei **Katharina Simbeck** erhältlich.

### Entwicklungsserver starten
```bash
python manage.py runserver
```

---

## 📁 Projektstruktur

| Ordner | Beschreibung |
|--------|---------------|
| `users` | Benutzerverwaltung (Studierende, Lehrende, Rollen, Login) |
| `posts` | Aufgaben, Buchungen, Feedback, Hauptbuch, Bilanz |
| `templates` | HTML-Vorlagen für die Benutzeroberfläche |
| `staticfiles` | CSS, JavaScript und Medien |
| `locale` | Sprachdateien (DE/EN) |

---

## 🔄 Typische Arbeitsweise

1. Virtuelle Umgebung aktivieren  
2. Feature-Branch erstellen  
   ```bash
   git checkout -b feature/dein-feature
   ```
3. Änderungen lokal testen  
4. Migrationen durchführen und prüfen  
5. Commit & Push an GitHub  
   ```bash
   git add .
   git commit -m "Feature: Neue Aufgabenlogik"
   git push origin feature/dein-feature
   ```

---

## 🌍 Deployment auf Server (HTW-VM)

### Verbindung & Setup
```bash
ssh wiuser@train.f4.htw-berlin.de
# Passwort → bei Katharina Simbeck
```

### Virtuelle Umgebung aktivieren
```bash
source env/bin/activate
```

### Änderungen aus Git übernehmen
```bash
git pull origin main
```

### Statische Dateien aktualisieren
```bash
python manage.py collectstatic --clear --noinput
```

### Services neustarten
```bash
sudo systemctl restart gunicorn
sudo systemctl restart nginx
```

---

## 🌐 Übersetzung

Die Anwendung ist **mehrsprachig (Deutsch/Englisch)**.  
Übersetzbare Texte sind mit `{% trans %}` in Templates markiert.

### Übersetzungen aktualisieren
```bash
django-admin makemessages -l en
python manage.py compilemessages
```

---

## 💾 Backup & Wartung

- Tägliches **Datenbank-Backup (Cronjob)**  
- Letzte **7 Sicherungen** unter `/backups`  
- Beispielskript:  
  ```
  individuelles-tempo/backup_db.sh
  ```

---

© 2025 Hochschule für Technik und Wirtschaft Berlin (HTW Berlin)  
Projekt im Rahmen des *Curriculum Innovation Hub*
