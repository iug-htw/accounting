document.getElementById('menuButton').addEventListener('click', function() {
    var menu = document.getElementById('menu');
    if (menu.style.display === 'block') {
        menu.style.display = 'none';
    } else {
        menu.style.display = 'block';
    }
});

document.getElementById('loginForm').addEventListener('submit', function(e) {
    e.preventDefault();

    // Dummy-Daten für den Login-Vorgang
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    if (username === 'admin' && password === 'admin') {
        localStorage.setItem('loggedIn', true);
        alert('Login erfolgreich!');
        showLoggedInView();
    } else {
        alert('Falscher Benutzername oder Passwort!');
    }
});

function showLoggedInView() {
    document.getElementById('loginContainer').style.display = 'none';
    document.querySelector('.navigation_bar_top').style.display = 'flex';
    document.getElementById('logoutContainer').style.display = 'flex'; 
    document.querySelector('.menu_button').style.display = 'flex';// Zeigt den Logout-Button an

}

document.getElementById('logoutButton').addEventListener('click', function() {
    localStorage.removeItem('loggedIn');
    alert('Sie haben sich erfolgreich ausgeloggt!');
    window.location.reload(); // Seite neu laden, um den Login-Bildschirm anzuzeigen
});

function checkLoginStatus() {
    if (localStorage.getItem('loggedIn')) {
        showLoggedInView();
    } else {
        document.getElementById('loginContainer').style.display = 'block';
        document.querySelector('.navigation_bar_top').style.display = 'flex';
        document.querySelector('.welcome_section').style.display = 'none';
        document.getElementById('logoutContainer').style.display = 'none'; // Versteckt den Logout-Button
        document.querySelector('.menu_button').style.display = 'none';
    }
}

// Initialer Aufruf der Funktion, um den Login-Status zu prüfen
checkLoginStatus();
